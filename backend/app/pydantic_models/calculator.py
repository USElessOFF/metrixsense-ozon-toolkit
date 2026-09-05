"""Модели калькулятора плановой юнит-экономики"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CalculatorRequest(BaseModel):
    """Запрос расчёта плановой юнит-экономики"""

    mode: Literal["existing", "manual"] = Field(
        default="manual",
        description="existing — товар на Ozon (данные из API по sku); manual — новинка, всё вручную.",
    )
    sku: int | None = Field(default=None, description="SKU товара (обязателен для existing).")
    purchase_price: float = Field(..., gt=0, description="Закупочная цена за единицу, ₽.")
    sale_price: float | None = Field(
        default=None, gt=0,
        description="Цена продажи, ₽. existing: берётся из API, если не задана.",
    )
    commission_percent: float | None = Field(
        default=None, ge=0, le=100,
        description="Комиссия Ozon, % (manual; existing берётся из API).",
    )
    logistics_cost: float | None = Field(
        default=None, ge=0,
        description="Логистика за единицу, ₽ (manual; existing — из API, фоллбэк на настройку).",
    )
    acquiring_percent: float | None = Field(
        default=None, ge=0, le=100,
        description="Эквайринг, % (manual; existing берётся из API).",
    )
    ad_budget_percent: float | None = Field(
        default=None, ge=0,
        description="Реклама, % от выручки (переопределяет настройку магазина).",
    )

    @model_validator(mode="after")
    def _validate_mode(self) -> "CalculatorRequest":
        if self.mode == "existing" and self.sku is None:
            raise ValueError("sku is required for existing mode")
        return self


class CalculatorCostLine(BaseModel):
    """Строка расходов в разборе калькулятора"""

    name: str = Field(..., description="Название расхода.")
    amount: float = Field(..., description="Сумма, ₽ на единицу.")
    source: str = Field(default="manual", description="Источник значения: api / manual / settings.")


class CalculatorResult(BaseModel):
    """Результат расчёта плановой юнит-экономики"""

    mode: str = Field(..., description="Режим расчёта.")
    sku: int | None = Field(default=None, description="SKU (existing).")
    revenue: float = Field(..., description="Выручка за единицу, ₽.")
    cost_lines: list[CalculatorCostLine] = Field(default_factory=list, description="Разбор расходов.")
    total_costs: float = Field(..., description="Сумма расходов, ₽.")
    pre_tax_profit: float = Field(..., description="Прибыль до налога, ₽.")
    tax: float = Field(..., description="Налог, ₽.")
    tax_system: str = Field(..., description="Налоговая система.")
    profit: float = Field(..., description="Чистая прибыль за единицу, ₽.")
    margin_percent: float = Field(..., description="Маржа, % от выручки.")
    markup_percent: float = Field(..., description="Наценка, % от закупки.")
    warnings: list[str] = Field(default_factory=list)
