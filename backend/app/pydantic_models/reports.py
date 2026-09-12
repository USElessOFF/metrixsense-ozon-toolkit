"""Схемы запросов и ответов отчётов"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    """Запрос на формирование полного аналитического отчёта"""

    date_from: str = Field(..., description="Start date in %Y-%m-%d format")
    date_to: str = Field(..., description="End date in %Y-%m-%d format")

class CreatedReportResponse(BaseModel):
    """Созданный отчёт"""

    request_uuid: str = Field(..., description="Report request UUID")
    status: str = Field(..., description="pending | in_progress | completed | failed")


class ReportStatusResponse(BaseModel):
    """Статус формирования отчёта"""

    request_uuid: str = Field(..., description="Report request UUID")
    status: str = Field(..., description="pending | in_progress | completed | failed")
    info: str | None = Field(default=None, description="Additional info or error message")
    created_at: datetime | None = None
    updated_at: datetime | None = None
    date_from: datetime | None = Field(default=None, description="Period start of the report request")
    date_to: datetime | None = Field(default=None, description="Period end of the report request")


class ProductCardsRequest(BaseModel):
    """Запрос секции карточек товаров (опциональный список SKU)"""

    sku: list[int | str] | None = Field(
        default=None,
        description="Список SKU. Пусто/None — все товары продавца из /v3/product/list.",
    )
