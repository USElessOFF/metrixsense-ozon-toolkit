"""Схемы запросов и ответов настроек"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    tax_system: str = Field(default="usn_6", description="Система налогообложения")
    ad_budget_percent: float = Field(default=5.0, ge=0, le=100, description="Бюджет на рекламу, % от выручки")
    logistics_cost: float = Field(default=150.0, ge=0, description="Средняя стоимость логистики за заказ, ₽")
    cost_price_share: float = Field(
        default=0.5, ge=0, le=1,
        description="Оценка себестоимости как доля от цены продажи (Ozon API не отдаёт закупочную цену)",
    )
    fbo: bool = Field(default=False, description="FBO (true) или FBS (false)")
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SettingsUpdate(BaseModel):
    tax_system: str | None = Field(default=None, description="Система налогообложения")
    ad_budget_percent: float | None = Field(default=None, ge=0, le=100, description="Бюджет на рекламу, % от выручки")
    logistics_cost: float | None = Field(default=None, ge=0, description="Средняя стоимость логистики за заказ, ₽")
    cost_price_share: float | None = Field(
        default=None, ge=0, le=1,
        description="Оценка себестоимости как доля от цены продажи",
    )
    fbo: bool | None = Field(default=None, description="FBO (true) или FBS (false)")
