"""Pydantic-модели ответов разделённых секций отчётов.

Используются как response_model в роутерах /api/reports/sections/*:
фронтенд получает документированную в OpenAPI схему, а не сырые dict.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SectionMeta(BaseModel):
    """Общие поля любой секции"""

    model_config = ConfigDict(protected_namespaces=())

    section: str = Field(..., description="Идентификатор секции.")
    generated_at: datetime = Field(..., description="Момент генерации (UTC).")
    row_count: int = Field(..., ge=0, description="Количество строк в data.")
    warnings: list[str] = Field(
        default_factory=list,
        description="Замечания о точности расчёта (фоллбэки на настройки и т.п.).",
    )


class PricesCommissionsRow(BaseModel):
    """Строка секции цен и комиссий (/v5/product/info/prices)"""

    model_config = ConfigDict(protected_namespaces=())

    product_id: int | None = Field(default=None, description="ID товара Ozon.")
    offer_id: str | None = Field(default=None, description="Артикул продавца.")
    price: float | None = Field(default=None, description="Текущая цена, ₽.")
    old_price: float | None = Field(default=None, description="Цена до скидки, ₽.")
    min_price: float | None = Field(default=None, description="Минимальная цена, ₽.")
    marketing_price: float | None = Field(default=None, description="Цена с учётом акций Ozon, ₽.")
    commission_fbo_percent: float | None = Field(default=None, description="Комиссия за продажу FBO, %.")
    commission_fbs_percent: float | None = Field(default=None, description="Комиссия за продажу FBS, %.")
    acquiring_percent: float | None = Field(default=None, description="Эквайринг, %.")
    logistics_fbo_range: str | None = Field(default=None, description="Логистика FBO, ₽ (мин–макс).")
    logistics_fbs_first_mile_range: str | None = Field(
        default=None, description="Первая миля FBS, ₽ (мин–макс)."
    )
    delivery_fbo: float | None = Field(default=None, description="Доставка до покупателя FBO, ₽.")
    return_flow_fbo: float | None = Field(default=None, description="Возвратный поток FBO, ₽.")
    volume_weight_l: float | None = Field(default=None, description="Объёмный вес, л.")


class PricesCommissionsSectionResponse(SectionMeta):
    """Ответ секции «Цены и комиссии»"""

    data: list[PricesCommissionsRow] = Field(default_factory=list)


class ProductCardRow(BaseModel):
    """Строка секции карточек товаров (/v3/product/info/list + локальные габариты)"""

    model_config = ConfigDict(protected_namespaces=())

    sku: int | None = Field(default=None, description="SKU товара.")
    name: str | None = Field(default=None, description="Название товара.")
    offer_id: str | None = Field(default=None, description="Артикул продавца.")
    price: float | None = Field(default=None, description="Цена карточки, ₽.")
    old_price: float | None = Field(default=None, description="Старая цена, ₽.")
    min_price: float | None = Field(default=None, description="Мин. цена, ₽.")
    volume_weight_l: float | None = Field(default=None, description="Объёмный вес, л (из API).")
    commission_fbo_percent: float | None = Field(default=None, description="Комиссия FBO, %.")
    commission_fbs_percent: float | None = Field(default=None, description="Комиссия FBS, %.")
    delivery_fbo: float | None = Field(default=None, description="Доставка FBO, ₽.")
    return_fbo: float | None = Field(default=None, description="Возврат FBO, ₽.")
    local_length_mm: int | None = Field(default=None, description="Длина, мм (локальный справочник).")
    local_width_mm: int | None = Field(default=None, description="Ширина, мм (локальный справочник).")
    local_height_mm: int | None = Field(default=None, description="Высота, мм (локальный справочник).")
    local_weight_g: int | None = Field(default=None, description="Вес, г (локальный справочник).")
    local_volume_l: float | None = Field(default=None, description="Габаритный объём L×W×H, л.")
    oversize: bool | None = Field(
        default=None, description="Крупногабарит: сторона > 500 мм (иная тарифная зона Ozon)."
    )


class ProductCardsSectionResponse(SectionMeta):
    """Ответ секции «Карточки товаров»"""

    data: list[ProductCardRow] = Field(default_factory=list)


class FinanceExpenseRow(BaseModel):
    """Строка секции финансовых начислений (/v3/finance/transaction/list)"""

    model_config = ConfigDict(protected_namespaces=())

    sku: int | None = Field(default=None, description="SKU товара.")
    sale_commission: float | None = Field(default=None, description="Комиссия за продажу, ₽ (факт).")
    delivery: float | None = Field(default=None, description="Доставка, ₽ (факт).")
    return_delivery: float | None = Field(default=None, description="Возвратная доставка, ₽ (факт).")
    services: float | None = Field(default=None, description="Услуги Ozon, ₽ (факт).")
    accruals_for_sale: float | None = Field(default=None, description="Начислено за продажи, ₽ (факт).")
    actual_logistics_per_unit: float | None = Field(
        default=None, description="Фактическая логистика на единицу, ₽."
    )


class FinanceExpensesSectionResponse(SectionMeta):
    """Ответ секции «Финансовые начисления»"""

    date_from: str = Field(..., description="Начало периода (YYYY-MM-DD).")
    date_to: str = Field(..., description="Конец периода (YYYY-MM-DD).")
    totals: dict[str, Any] = Field(
        default_factory=dict, description="Итоги периода (/v3/finance/transaction/totals)."
    )
    data: list[FinanceExpenseRow] = Field(default_factory=list)


class SellerRatingRow(BaseModel):
    """Строка секции рейтинга продавца (/v1/rating/summary)"""

    group_name: str | None = Field(default=None, description="Группа рейтинга.")
    rating_type: str | None = Field(default=None, description="Тип рейтинга.")
    score: float | None = Field(default=None, description="Текущий балл.")
    description: str | None = Field(default=None, description="Описание.")


class SellerRatingSectionResponse(SectionMeta):
    """Ответ секции «Рейтинг продавца»"""

    data: list[SellerRatingRow] = Field(default_factory=list)



class StockPlanningRow(BaseModel):
    """Строка секции планирования поставок (/v1/analytics/turnover/stocks)"""

    model_config = ConfigDict(protected_namespaces=())

    sku: int | None = Field(default=None, description="SKU товара.")
    name: str | None = Field(default=None, description="Название товара.")
    offer_id: str | None = Field(default=None, description="Артикул продавца.")
    current_stock: int | None = Field(default=None, description="Текущий остаток, шт.")
    ads: float | None = Field(default=None, description="Среднесуточные продажи за 60 дней, шт/день.")
    days_of_stock: float | None = Field(default=None, description="Дней запаса (текущий остаток / ADS).")
    idc: float | None = Field(default=None, description="Индекс достаточности Ozon, дней.")
    idc_grade: str | None = Field(default=None, description="Оценка достаточности Ozon.")
    turnover: float | None = Field(default=None, description="Оборачиваемость Ozon, дней.")
    recommended_stock: float | None = Field(default=None, description="Рекомендуемая поставка, шт.")
    needs_reorder: bool = Field(default=False, description="Нужна поставка: остатка < заданного порога дней.")


class StockPlanningSectionResponse(SectionMeta):
    """Ответ секции «Планирование поставок»"""

    target_days: int = Field(default=30, description="Целевой запас, дней (настройка).")
    critical_days: int = Field(default=14, description="Порог критического запаса, дней.")
    data: list[StockPlanningRow] = Field(default_factory=list)



class SearchQueryRow(BaseModel):
    """Строка секции поисковых фраз (/v1/analytics/product-queries)"""

    model_config = ConfigDict(protected_namespaces=())

    phrase: str | None = Field(default=None, description="Поисковая фраза.")
    sku: int | None = Field(default=None, description="SKU товара.")
    offer_id: str | None = Field(default=None, description="Артикул продавца.")
    category: str | None = Field(default=None, description="Категория запроса.")
    gmv: float | None = Field(default=None, description="Доход по запросу, ₽.")
    position: float | None = Field(default=None, description="Средняя позиция товара в поиске.")
    unique_search_users: int | None = Field(default=None, description="Уникальные пользователи поиска.")
    unique_view_users: int | None = Field(default=None, description="Уникальные пользователи карточки.")
    view_conversion: float | None = Field(default=None, description="Конверсия из поиска в карточку, %.")


class SearchQueriesSectionResponse(SectionMeta):
    """Ответ секции «Поисковые фразы»"""

    date_from: str = Field(..., description="Начало периода (YYYY-MM-DD).")
    date_to: str = Field(..., description="Конец периода (YYYY-MM-DD).")
    data: list[SearchQueryRow] = Field(default_factory=list)


class OnboardingStatusResponse(BaseModel):
    """Статус онбординга: только факты из БД, без внешних вызовов"""

    seller_api: dict[str, Any] = Field(..., description="{required, configured}.")
    performance_api: dict[str, Any] = Field(..., description="{required, configured}.")
    unit_economics_settings: dict[str, Any] = Field(
        ..., description="Текущие настройки юнит-экономики и признак is_default."
    )
    ready_for_report: bool = Field(..., description="Seller-ключи сохранены — отчёт можно создать.")
    next_steps: list[str] = Field(default_factory=list, description="Что осталось настроить.")


class CheckConnectionRequest(BaseModel):
    """Какие подключения проверить (POST /api/onboarding/check-connection)"""

    seller: bool = Field(default=True, description="Проверить Seller API ключи.")
    performance: bool = Field(default=True, description="Проверить Performance API ключи.")


class CheckConnectionResponse(BaseModel):
    """Результат реальной проверки подключений"""

    seller_connected: bool | None = Field(
        default=None, description="Seller API доступен (None — не проверялся)."
    )
    performance_connected: bool | None = Field(
        default=None, description="Performance API доступен (None — не проверялся/не настроен)."
    )
