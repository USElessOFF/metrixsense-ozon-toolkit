"""Модели поиска аналогов товаров (TF-IDF по названиям)"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnalogItem(BaseModel):
    """Аналог товара: сходство и цена"""

    sku: int = Field(..., description="SKU аналога.")
    name: str = Field(..., description="Название аналога.")
    offer_id: str | None = Field(default=None, description="Артикул продавца.")
    similarity: float = Field(..., description="Косинусная близость названия, 0..1.")
    price: float | None = Field(default=None, description="Цена аналога, ₽ (из /v5/prices).")


class AnalogsResponse(BaseModel):
    """Ответ поиска аналогов для SKU"""

    sku: int = Field(..., description="SKU исходного товара.")
    name: str | None = Field(default=None, description="Название исходного товара.")
    total_catalog: int = Field(..., description="Размер каталога, по которому искали.")
    analogs: list[AnalogItem] = Field(default_factory=list, description="Топ похожих товаров.")
