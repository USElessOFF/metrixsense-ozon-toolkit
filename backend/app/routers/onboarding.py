"""Онбординг: чек-лист данных после регистрации"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends

from backend.app.adapters.metrix_adapter import MetrixAdapter
from backend.app.depends.db import get_metrix_adapter_for_user
from backend.app.ozon_performance import OzonPerformanceClient
from backend.app.ozon_seller import OzonSellerClient
from backend.app.services.sync_scheduler import trigger_initial_sync
from backend.app.pydantic_models.report_sections import (
    CheckConnectionRequest,
    CheckConnectionResponse,
    OnboardingStatusResponse,
)

logger = structlog.get_logger(__name__)

# Значения настроек, при которых они считаются дефолтными
_DEFAULT_TAX_SYSTEM = "usn_6"
_DEFAULT_LOGISTICS_COST = 150.0
_DEFAULT_COST_PRICE_SHARE = 0.5


def get_onboarding_router() -> APIRouter:
    router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

    @router.get("/status", response_model=OnboardingStatusResponse)
    async def get_onboarding_status(
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> OnboardingStatusResponse:
        """Чек-лист готовности: только БД, без внешних вызовов"""
        secrets = await db.get_secrets()
        seller_configured = bool(secrets and secrets.seller_client_id and secrets.seller_api_key)
        performance_configured = bool(
            secrets and secrets.performance_client_id and secrets.performance_secret
        )

        settings = await db.get_settings()
        is_default = (
            settings.tax_system == _DEFAULT_TAX_SYSTEM
            and settings.logistics_cost == _DEFAULT_LOGISTICS_COST
            and settings.cost_price_share == _DEFAULT_COST_PRICE_SHARE
        )

        next_steps: list[str] = []
        if not seller_configured:
            next_steps.append("Сохраните Seller API ключи (/api/secrets)")
        if not performance_configured:
            next_steps.append(
                "Опционально: добавьте Performance API ключи для рекламных данных"
            )
        if is_default:
            next_steps.append(
                "Сверьте настройки юнит-экономики: налог, логистику, себестоимость (/api/settings)"
            )

        return OnboardingStatusResponse(
            seller_api={
                "required": True,
                "configured": seller_configured,
            },
            performance_api={
                "required": False,
                "configured": performance_configured,
            },
            unit_economics_settings={
                "required": True,
                "tax_system": settings.tax_system,
                "ad_budget_percent": settings.ad_budget_percent,
                "logistics_cost": settings.logistics_cost,
                "cost_price_share": settings.cost_price_share,
                "fbo": settings.fbo,
                "is_default": is_default,
            },
            ready_for_report=seller_configured,
            next_steps=next_steps,
        )

    @router.post("/check-connection", response_model=CheckConnectionResponse)
    async def check_connection(
        body: CheckConnectionRequest,
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> CheckConnectionResponse:
        """Реальная проверка ключей Ozon (внешние запросы)"""
        secrets = await db.get_secrets()
        seller_connected: bool | None = None
        performance_connected: bool | None = None

        has_seller = bool(
            secrets and secrets.seller_client_id and secrets.seller_api_key
        )
        has_performance = bool(
            secrets and secrets.performance_client_id and secrets.performance_secret
        )

        seller = None
        performance = None
        try:
            if body.seller and has_seller:
                seller = OzonSellerClient(
                    secrets.seller_client_id or "", secrets.seller_api_key or ""
                )
                try:
                    seller_connected = await seller.check_connection()
                except Exception as e:  # noqa: BLE001
                    logger.warning("Onboarding seller check failed", error=str(e))
                    seller_connected = False

            if body.performance and has_performance:
                performance = OzonPerformanceClient(
                    client_id=secrets.performance_client_id or "",
                    client_secret=secrets.performance_secret or "",
                )
                try:
                    performance_connected = await performance.check_connection()
                except Exception as e:  # noqa: BLE001
                    logger.warning("Onboarding performance check failed", error=str(e))
                    performance_connected = False
        finally:
            if seller is not None:
                await seller.close()
            if performance is not None:
                await performance.close()

        if seller_connected or performance_connected:
            await trigger_initial_sync()

        return CheckConnectionResponse(
            seller_connected=seller_connected,
            performance_connected=performance_connected,
        )

    return router
