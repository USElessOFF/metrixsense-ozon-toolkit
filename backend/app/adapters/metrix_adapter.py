"""CRUD для всех моделей приложения"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.exceptions import SettingsError
from backend.app.models.analytics_cache import AnalyticsCache
from backend.app.models.ozon_secrets import OzonSecrets
from backend.app.security import DecryptedSecrets, decrypt, encrypt
from backend.app.models.product_dimensions import ProductDimensions
from backend.app.models.report_request import ReportRequestOzon, ReportType
from backend.app.models.user_settings import UserSettings
from backend.app.tax import SUPPORTED_TAX_SYSTEMS

from .base import BaseAdapter

logger = structlog.get_logger(__name__)


class MetrixAdapter(BaseAdapter):
    """Адаптер, привязанный к пользователю"""

    def __init__(self, session: AsyncSession, user_id: int):
        self.session = session
        self.user_id = user_id
        super().__init__(self.session)

    async def get_settings(self) -> UserSettings:
        result = await self.session.execute(
            select(UserSettings).where(UserSettings.user_id == self.user_id)
        )
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = UserSettings(user_id=self.user_id)
            await self.create_object(settings)
        return settings

    async def update_settings(self, data: dict[str, Any]) -> UserSettings:
        current = await self.get_settings()
        allowed_fields = {"tax_system", "ad_budget_percent", "logistics_cost", "cost_price_share", "fbo"}
        update_data = {k: v for k, v in data.items() if k in allowed_fields and v is not None}
        if not update_data:
            raise SettingsError("No valid settings fields provided")
        # Налог валидируем сразу — без тихих фоллбэков
        tax_system = update_data.get("tax_system")
        if tax_system is not None and tax_system not in SUPPORTED_TAX_SYSTEMS:
            raise SettingsError(
                f"Unsupported tax system: {tax_system!r}. "
                f"Поддерживаются: {sorted(SUPPORTED_TAX_SYSTEMS)}"
            )
        return await self.update_object(current, update_data)

    async def _get_secrets_orm(self) -> OzonSecrets | None:
        result = await self.session.execute(
            select(OzonSecrets).where(OzonSecrets.user_id == self.user_id)
        )
        return result.scalar_one_or_none()

    async def get_secrets(self) -> DecryptedSecrets | None:
        orm = await self._get_secrets_orm()
        if orm is None:
            return None
        return DecryptedSecrets(
            seller_client_id=decrypt(orm.seller_client_id),
            seller_api_key=decrypt(orm.seller_api_key),
            performance_client_id=decrypt(orm.performance_client_id),
            performance_secret=decrypt(orm.performance_secret),
        )

    async def update_secrets(self, data: dict[str, Any]) -> OzonSecrets:
        current = await self._get_secrets_orm()
        allowed_fields = {"seller_client_id", "seller_api_key", "performance_client_id", "performance_secret"}
        encrypted_data = {k: encrypt(v) for k, v in data.items() if k in allowed_fields}

        if current is None:
            new_secrets = OzonSecrets(user_id=self.user_id, **encrypted_data)
            return await self.create_object(new_secrets)

        return await self.update_object(current, encrypted_data)

    async def clear_secrets(self) -> None:
        current = await self._get_secrets_orm()
        if current:
            await self.delete_object(current)

    async def create_report_request(self, date_from: datetime, date_to: datetime, report_type: ReportType) -> ReportRequestOzon:
        report_request = ReportRequestOzon(
            user_id=self.user_id,
            date_from=date_from,
            date_to=date_to,
            type=report_type
        )
        return await self.create_object(report_request)

    async def get_report_request(self, request_uuid: str) -> ReportRequestOzon | None:
        result = await self.session.execute(
            select(ReportRequestOzon).where(
                ReportRequestOzon.user_id == self.user_id,
                ReportRequestOzon.request_uuid == request_uuid,
            )
        )
        return result.scalar_one_or_none()

    async def update_report_status(
        self, request_uuid: str, status: str, info: str | None = None
    ) -> ReportRequestOzon | None:
        request = await self.get_report_request(request_uuid)
        if request is None:
            return None
        update_data: dict[str, Any] = {"status": status}
        if info is not None:
            update_data["info"] = info
        return await self.update_object(request, update_data)

    async def get_cache(self, cache_key: str) -> str | None:
        result = await self.session.execute(
            select(AnalyticsCache).where(AnalyticsCache.cache_key == cache_key)
        )
        cache_entry = result.scalar_one_or_none()
        if cache_entry is None:
            return None
        if cache_entry.expires_at is not None:
            expires_at = cache_entry.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(tz=timezone.utc):
                await self.delete_object(cache_entry)
                return None
        return cache_entry.data_json

    async def set_cache(
        self,
        cache_key: str,
        data: str | dict[str, Any],
        ttl: timedelta | None = None,
    ) -> None:
        data_json = (
            data
            if isinstance(data, str)
            else json.dumps(data, ensure_ascii=False, default=str)
        )
        expires_at = (
            datetime.now(tz=timezone.utc) + ttl if ttl is not None else None
        )
        result = await self.session.execute(
            select(AnalyticsCache).where(AnalyticsCache.cache_key == cache_key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.data_json = data_json
            existing.expires_at = expires_at
            await self.session.merge(existing)
            await self.session.commit()
        else:
            await self.create_object(
                AnalyticsCache(cache_key=cache_key, data_json=data_json, expires_at=expires_at)
            )

    async def upsert_product_dimensions(self, items: list[dict[str, Any]]) -> list[ProductDimensions]:
        """Bulk upsert габаритов по (user_id, sku)"""
        from backend.app.exceptions import SettingsError

        if not items:
            raise SettingsError("No product dimensions provided")

        saved: list[ProductDimensions] = []
        for item in items:
            sku = item.get("sku")
            if sku is None:
                raise SettingsError("Each item must contain 'sku'")
            result = await self.session.execute(
                select(ProductDimensions).where(
                    ProductDimensions.user_id == self.user_id,
                    ProductDimensions.sku == int(sku),
                )
            )
            row = result.scalar_one_or_none()
            payload = {
                key: value
                for key, value in item.items()
                if key in {"length_mm", "width_mm", "height_mm", "weight_g"}
            }
            if row is None:
                row = ProductDimensions(user_id=self.user_id, sku=int(sku), **payload)
                saved.append(await self.create_object(row))
            else:
                saved.append(await self.update_object(row, payload))
        return saved

    async def get_product_dimensions(
        self, skus: list[int] | None = None
    ) -> dict[int, ProductDimensions]:
        """Габариты по SKU; список SKU — фильтром"""
        stmt = select(ProductDimensions).where(ProductDimensions.user_id == self.user_id)
        if skus:
            stmt = stmt.where(ProductDimensions.sku.in_([int(s) for s in skus]))  # noqa: E501
        result = await self.session.execute(stmt)
        return {row.sku: row for row in result.scalars().all()}

    async def clear_product_dimensions(self) -> None:
        result = await self.session.execute(
            select(ProductDimensions).where(ProductDimensions.user_id == self.user_id)
        )
        for row in result.scalars().all():
            await self.delete_object(row)
