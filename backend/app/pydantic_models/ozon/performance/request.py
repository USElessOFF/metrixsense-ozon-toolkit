"""Модели запросов Performance API (на основе swagger_performance.json v2.0)"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_serializer

from backend.app.pydantic_models.ozon.commons import OzonBaseModel

from .enums import (
    AdvObjectType,
    CampaignState,
    MarketplaceID,
    PaymentTypeRate,
    StatisticsGroupBy,
)


def _to_rfc3339_start(v: str) -> str:
    """Нормализация начальной даты в RFC 3339 (начало дня UTC)"""
    if isinstance(v, datetime):
        return v.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z" # type: ignore
    return v


def _to_rfc3339_end(v: str) -> str:
    """Нормализация конечной даты в RFC 3339 (конец дня UTC)"""
    if isinstance(v, datetime):
        return v.replace(hour=23, minute=59, second=59, microsecond=0).isoformat() + "Z" # type: ignore
    return v


class CampaignQueryParams(OzonBaseModel):
    """GET /api/client/campaign — параметры списка кампаний"""

    campaign_ids: list[str] | None = Field(
        default=None,
        alias="campaignIds",
        description="Список идентификаторов кампаний. Если пусто — все кампании.",
    )
    adv_object_type: AdvObjectType | None = Field(
        default=None,
        alias="advObjectType",
        description="Тип рекламируемой кампании.",
    )
    state: CampaignState | None = Field(
        default=None,
        description="Состояние кампании.",
    )

    def to_query_params(self) -> dict[str, Any]:
        """Сериализация в query-параметры (списки — через запятую)"""
        params: dict[str, Any] = {}
        if self.campaign_ids:
            params["campaignIds"] = ",".join(self.campaign_ids)
        if self.adv_object_type is not None:
            params["advObjectType"] = self.adv_object_type.value
        if self.state is not None:
            params["state"] = self.state.value
        return params


class StatisticsRequest(OzonBaseModel):
    """POST /api/client/statistics — асинхронный отчёт по кампаниям (CSV/ZIP).

    Поддерживаются оба формата периода:
    - ``date_from``/``date_to`` — ГГГГ-ММ-ДД;
    - ``from_``/``to`` — RFC 3339 (с нормализацией datetime → начало/конец дня).
    """

    model_config = ConfigDict(populate_by_name=True)

    campaigns: list[str] = Field(
        ...,
        description="Идентификаторы кампаний: CSV — если одна, ZIP — если несколько.",
    )
    date_from: str | None = Field(
        default=None,
        alias="dateFrom",
        description="Начальная дата периода отчёта в формате ГГГГ-ММ-ДД.",
    )
    date_to: str | None = Field(
        default=None,
        alias="dateTo",
        description="Конечная дата периода отчёта в формате ГГГГ-ММ-ДД.",
    )
    from_: str | None = Field(
        default=None,
        alias="from",
        description="Начальная дата периода отчёта в формате RFC 3339 (максимум 62 дня).",
    )
    to: str | None = Field(
        default=None,
        description="Конечная дата периода отчёта в формате RFC 3339 (максимум 62 дня).",
    )
    group_by: StatisticsGroupBy = Field(
        default=StatisticsGroupBy.NO_GROUP_BY,
        alias="groupBy",
        description="Группировка данных по времени.",
    )

    normalize_from = field_validator("from_", mode="before")(_to_rfc3339_start)
    normalize_to = field_validator("to", mode="before")(_to_rfc3339_end)

    @model_serializer(mode="wrap")
    def _serialize(
        self,
        handler: Callable[[Any], dict[str, Any]]
    ) -> dict[str, Any | str]:
        data = handler(self)
        return {
            key: (value.value if isinstance(value, StatisticsGroupBy) else value)
            for key, value in data.items()
            if value is not None
        }


class StatisticsVideobannerRequest(OzonBaseModel):
    """POST /api/client/statistics/videobanner — отчёт по видеобаннерам"""

    campaigns: list[str] = Field(..., description="Идентификаторы видеобаннерных кампаний.")
    date_from: str  | None = Field(default=None, alias="dateFrom")
    date_to: str  | None = Field(default=None, alias="dateTo")
    group_by: StatisticsGroupBy = Field(default=StatisticsGroupBy.NO_GROUP_BY, alias="groupBy")


class StatisticsAttributionRequest(OzonBaseModel):
    """POST /api/client/statistics/search-promo/attribution — отчёт по заказам (продвижение в поиске)"""

    campaigns: list[str] = Field(..., description="Идентификаторы кампаний продвижения в поиске.")
    from_: str  | None = Field(default=None, alias="from", description="Начало периода (RFC 3339).")
    to: str  | None = Field(default=None, description="Конец периода (RFC 3339).")
    date_from: str  | None = Field(default=None, alias="dateFrom")
    date_to: str  | None = Field(default=None, alias="dateTo")

    normalize_from = field_validator("from_", mode="before")(_to_rfc3339_start)
    normalize_to = field_validator("to", mode="before")(_to_rfc3339_end)


class SearchPromoReportRequest(OzonBaseModel):
    """POST /api/client/statistic/{orders|products}/generate — отчёты продвижения в поиске"""

    from_: str = Field(..., alias="from", description="Начало периода (RFC 3339).")
    to: str = Field(..., description="Конец периода (RFC 3339).")

    normalize_from = field_validator("from_", mode="before")(_to_rfc3339_start)
    normalize_to = field_validator("to", mode="before")(_to_rfc3339_end)


class VendorStatisticsRequest(OzonBaseModel):
    """POST /api/client/statistics/vendor — статистика по внешнему трафику продавцов"""

    campaigns: list[str] = Field(..., description="Идентификаторы кампаний внешнего трафика.")
    date_from: str  | None = Field(default=None, alias="dateFrom")
    date_to: str  | None = Field(default=None, alias="dateTo")
    group_by: StatisticsGroupBy = Field(default=StatisticsGroupBy.NO_GROUP_BY, alias="groupBy")


class DailyStatsQueryParams(OzonBaseModel):
    """GET /api/client/statistics/daily — параметры дневной статистики"""

    campaign_ids: list[str] | None = Field(
        default=None,
        alias="campaignIds",
        description="Список идентификаторов кампаний.",
    )
    date_from: str | None = Field(
        default=None,
        alias="dateFrom",
        description="Начало периода в формате ГГГГ-ММ-ДД. Без дат — последние 7 дней.",
    )
    date_to: str | None = Field(
        default=None,
        alias="dateTo",
        description="Конец периода в формате ГГГГ-ММ-ДД. Без дат — последние 7 дней.",
    )

    def to_query_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if self.campaign_ids:
            params["campaignIds"] = ",".join(self.campaign_ids)
        if self.date_from is not None:
            params["dateFrom"] = self.date_from
        if self.date_to is not None:
            params["dateTo"] = self.date_to
        return params


class BidBySKURequest(OzonBaseModel):
    """POST /api/client/min/sku — минимальные ставки по SKU (до 200 идентификаторов)"""

    marketplace_id: MarketplaceID | None = Field(default=None, alias="marketplaceId")
    payment_type: PaymentTypeRate | None = Field(default=None, alias="paymentType")
    sku: list[str] | None = Field(
        default=None,
        description="Идентификаторы товара: SKU или Ozon ID.",
    )


class CampaignPeriodStatsQueryParams(DailyStatsQueryParams):
    """GET /api/client/statistics — параметры статистики за период"""

    group_by: StatisticsGroupBy | None = Field(
        default=None,
        alias="groupBy",
        description="Группировка данных по времени: DATE, START_OF_WEEK, START_OF_MONTH.",
    )

    def to_query_params(self) -> dict[str, Any]:
        params = super().to_query_params()
        if self.group_by is not None:
            params["groupBy"] = self.group_by.value
        return params


class ExpenseStatsQueryParams(DailyStatsQueryParams):
    """GET /api/client/statistics/expense — параметры ежедневных расходов"""


class ReportFormat(StrEnum):
    """Формат файла отчёта (CSV по умолчанию, JSON по запросу)"""

    CSV = "csv"
    JSON = "json"
