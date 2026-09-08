"""Модели агрегированных действий по магазину (Top-N)"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.pydantic_models.report_sections import SectionMeta


class TopActionItem(BaseModel):
    """Одно агрегированное действие"""

    action_type: str = Field(..., description="restock / dead_stock / high_costs / search_no_sales.")
    title: str = Field(..., description="Человекочитаемый заголовок действия.")
    priority: str = Field(..., description="critical / high / medium / low.")
    sku_count: int = Field(..., description="Сколько SKU затронуто.")
    skus: list[int] = Field(default_factory=list, description="Затронутые SKU (первые 20).")
    impact: str = Field(..., description="Краткая оценка последствий/объёма.")
    details: dict[str, Any] = Field(default_factory=dict, description="Сырые данные для UI.")


class TopActionsRequest(BaseModel):
    """Запрос топ-действий (даты включают анализ поисковых фраз)"""

    date_from: str | None = Field(default=None, description="YYYY-MM-DD (опционально).")
    date_to: str | None = Field(default=None, description="YYYY-MM-DD (опционально).")


class TopActionsResponse(SectionMeta):
    """Ответ: ранжированный список действий"""

    actions: list[TopActionItem] = Field(default_factory=list)
