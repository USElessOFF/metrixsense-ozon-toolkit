"""Настройки"""

from backend.app.adapters.metrix_adapter import MetrixAdapter
from backend.app.depends.db import get_metrix_adapter_for_user
from backend.app.exceptions import SettingsError
from backend.app.pydantic_models.settings import SettingsResponse, SettingsUpdate
from fastapi import APIRouter, Depends, HTTPException, status


def get_settings_router() -> APIRouter:
    router = APIRouter(prefix="/api", tags=["settings"])

    @router.get("/settings", response_model=SettingsResponse)
    async def get_settings(db: MetrixAdapter = Depends(get_metrix_adapter_for_user)):  # noqa: B008
        """Настройки текущего пользователя"""
        settings = await db.get_settings()
        return SettingsResponse(
            tax_system=settings.tax_system,
            ad_budget_percent=settings.ad_budget_percent,
            logistics_cost=settings.logistics_cost,
            cost_price_share=settings.cost_price_share,
            fbo=settings.fbo,
            created_at=settings.created_at,
            updated_at=settings.updated_at,
        )

    @router.post("/settings", response_model=SettingsResponse)
    async def create_settings(data: SettingsUpdate, db: MetrixAdapter = Depends(get_metrix_adapter_for_user)):  # noqa: B008
        """Создать или обновить настройки пользователя"""
        try:
            settings = await db.update_settings(data.model_dump(exclude_none=True))
        except SettingsError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
        return SettingsResponse(
            tax_system=settings.tax_system,
            ad_budget_percent=settings.ad_budget_percent,
            logistics_cost=settings.logistics_cost,
            cost_price_share=settings.cost_price_share,
            fbo=settings.fbo,
            created_at=settings.created_at,
            updated_at=settings.updated_at,
        )

    @router.put("/settings", response_model=SettingsResponse)
    async def update_settings(data: SettingsUpdate, db: MetrixAdapter = Depends(get_metrix_adapter_for_user)):  # noqa: B008
        """Обновить настройки пользователя"""
        try:
            settings = await db.update_settings(data.model_dump(exclude_none=True))
        except SettingsError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
        return SettingsResponse(
            tax_system=settings.tax_system,
            ad_budget_percent=settings.ad_budget_percent,
            logistics_cost=settings.logistics_cost,
            cost_price_share=settings.cost_price_share,
            fbo=settings.fbo,
            created_at=settings.created_at,
            updated_at=settings.updated_at,
        )

    return router
