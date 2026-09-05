"""Модели запросов Seller API (на основе swagger_saller.json v2.1)"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import Field, field_validator, model_validator

from backend.app.pydantic_models.ozon.commons import OzonBaseModel

from .enums import (
    AnalyticsDimension,
    AnalyticsFilterOp,
    AnalyticsMetric,
    AnalyticsSortOrder,
    FbpFilter,
    ItemTag,
    PostingSortDir,
    ProductQueriesSortBy,
    ProductQueriesSortDir,
    RatingType,
    ReviewSortDir,
    ReviewStatus,
    SellerReportType,
    TransactionType,
    TurnoverGrade,
    Visibility,
)


def _to_date_str(v: datetime | str) -> str:
    """Приведение datetime к формату ГГГГ-ММ-ДД"""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    return v


def _to_iso_str(v: datetime | str) -> str:
    """Приведение datetime к ISO 8601 строке"""
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _to_rfc3339_ozon(v: datetime | str) -> str:
    """Нормализация datetime к RFC 3339 для /v3/finance/transaction/list.

    Ozon требует формат ``YYYY-MM-DDTHH:mm:ss.sssZ`` (миллисекунды + ``Z``),
    а не ``+00:00`` от :func:`datetime.isoformat`.
    """
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        else:
            v = v.astimezone(timezone.utc)
        return v.strftime("%Y-%m-%dT%H:%M:%S.") + f"{v.microsecond // 1000:03d}Z"
    return v


class ProductListRequestFilter(OzonBaseModel):
    """Фильтр списка товаров (/v3/product/list)"""

    offer_id: list[str] | None = Field(
        default=None,
        description="Фильтр по параметру ``offer_id``. Можно передавать список значений.",
    )
    product_id: list[int] | None = Field(
        default=None,
        description="Фильтр по параметру ``product_id``. Можно передавать список значений.",
    )
    visibility: Visibility = Field(
        default=Visibility.ALL,
        description="Фильтр по видимости товара.",
    )


class ProductListRequest(OzonBaseModel):
    """POST /v3/product/list — список товаров с пагинацией.

    Для получения следующей страницы передайте ``last_id`` из предыдущего ответа.
    """

    filter_: ProductListRequestFilter = Field(
        default_factory=ProductListRequestFilter,
        alias="filter",
        description="Параметры фильтрации товаров.",
    )
    last_id: str = Field(
        default="",
        description="Идентификатор последнего значения на странице. Пусто при первом запросе.",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Количество значений на странице: 1–1000.",
    )


class AnalyticsDataFilter(OzonBaseModel):
    """Фильтр в аналитическом запросе (/v1/analytics/data)"""

    key: str = Field(
        ...,
        description="Параметр фильтрации (dimension или metric, кроме ``brand``).",
    )
    op: AnalyticsFilterOp = Field(
        default=AnalyticsFilterOp.EQ,
        description="Операция сравнения: EQ/GT/GTE/LT/LTE.",
    )
    value: str = Field(..., description="Значение для сравнения.")


class AnalyticsSort(OzonBaseModel):
    """Сортировка аналитического отчёта"""

    key: AnalyticsMetric = Field(..., description="Метрика для сортировки.")
    order: AnalyticsSortOrder = Field(default=AnalyticsSortOrder.ASC, description="ASC/DESC.")


class AnalyticsDataRequest(OzonBaseModel):
    """POST /v1/analytics/data — аналитика по товарам с группировкой.

    Без Premium-подписки доступны только данные за последние 3 месяца
    и базовые метрики ``revenue``, ``ordered_units``.
    """

    date_from: str = Field(..., description="Дата начала периода, ГГГГ-ММ-ДД.")
    date_to: str = Field(..., description="Дата окончания периода, ГГГГ-ММ-ДД.")
    dimension: list[AnalyticsDimension | str] = Field(
        ...,
        description="Группировка данных в отчёте.",
    )
    metrics: list[AnalyticsMetric | str] = Field(
        default=[AnalyticsMetric.UNKNOWN],
        description="Список метрик (до 14 штук).",
    )
    filters: list[AnalyticsDataFilter] | None = Field(
        default=None,
        description="Фильтры запроса.",
    )
    limit: int = Field(
        default=1000,
        ge=1,
        le=1000,
        description="Количество значений в ответе: 1–1000.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Количество элементов, которое будет пропущено в ответе.",
    )
    sort: list[AnalyticsSort] | None = Field(
        default=None,
        description="Настройки сортировки отчёта.",
    )

    normalize_from = field_validator("date_from", mode="before")(_to_date_str)
    normalize_to = field_validator("date_to", mode="before")(_to_date_str)

    @field_validator("metrics", mode="after")
    @classmethod
    def metrics_limit_and_enum(cls, v: list[AnalyticsMetric | str]) -> list[str]:
        """Не более 14 метрик; значения приводятся к enum-строкам"""
        if len(v) > 14:
            raise ValueError("Метрик должно быть не более 14.")
        return [m.value if isinstance(m, AnalyticsMetric) else str(m) for m in v]

    @field_validator("dimension", mode="after")
    @classmethod
    def dimension_to_enum(cls, v: list[AnalyticsDimension | str]) -> list[str]:
        """Измерения приводятся к enum-строкам"""
        return [d.value if isinstance(d, AnalyticsDimension) else str(d) for d in v]


class AnalyticsStocksRequest(OzonBaseModel):
    """POST /v1/analytics/stocks — аналитика остатков на складах.

    Данные обновляются ежедневно в 05:00 UTC.
    """

    skus: list[str | int] = Field(..., description="Идентификаторы товаров (максимум 100).")
    cluster_ids: list[int] | None = None
    item_tags: list[ItemTag] | None = None
    turnover_grades: list[TurnoverGrade] | None = None
    warehouse_ids: list[int] | None = None

    @field_validator("skus", mode="after")
    @classmethod
    def skus_limit(cls, v: list[str | int]) -> list[str]:
        if not v:
            raise ValueError("Нужно передать хотя бы один SKU.")
        if len(v) > 100:
            raise ValueError("Максимум 100 SKU в одном запросе.")
        return [str(s) for s in v]


class RatingHistoryRequest(OzonBaseModel):
    """POST /v1/rating/history — история рейтингов продавца за период.

    Поддерживаются значения из :class:`RatingType`. Для штрафных баллов
    Premium укажите ``with_premium_scores=True``.
    """

    date_from: datetime | str = Field(..., description="Начало периода (ISO 8601).")
    date_to: datetime | str = Field(..., description="Конец периода (ISO 8601).")
    ratings: list[RatingType | str] = Field(..., description="Список типов рейтингов.")
    with_premium_scores: bool = Field(
        default=False,
        description="Включить информацию о штрафных баллах Premium.",
    )

    normalize_from = field_validator("date_from", mode="before")(_to_iso_str)
    normalize_to = field_validator("date_to", mode="before")(_to_iso_str)

    @field_validator("ratings", mode="after")
    @classmethod
    def ratings_to_str(cls, v: list[RatingType | str]) -> list[str]:
        return [r.value if isinstance(r, RatingType) else str(r) for r in v]


class ProductQueriesRequest(OzonBaseModel):
    """POST /v1/analytics/product-queries — аналитика поисковых запросов.

    Показывает, какие поисковые фразы приводят к показам и продажам товаров.
    Максимум 1000 SKU в одном запросе.
    """

    date_from: str = Field(..., description="Начало периода (ISO 8601, date-time).")
    date_to: str = Field(..., description="Конец периода (ISO 8601, date-time).")
    skus: list[int | str] = Field(..., description="Список SKU (до 1000).")
    page: int = Field(default=1, description="Номер страницы.")
    page_size: int = Field(default=100, le=1000, description="Количество запросов на странице.")
    sort_by: ProductQueriesSortBy | None = Field(default=None, description="Поле сортировки.")
    sort_dir: ProductQueriesSortDir | None = Field(default=None, description="Направление сортировки.")

    normalize_from = field_validator("date_from", mode="before")(_to_iso_str)
    normalize_to = field_validator("date_to", mode="before")(_to_iso_str)

    @field_validator("skus", mode="after")
    @classmethod
    def skus_to_str(cls, v: list[int | str]) -> list[str]:
        return [str(s) for s in v]


class TurnoverStocksRequest(OzonBaseModel):
    """POST /v1/analytics/turnover/stocks — оборачиваемость остатков (бета).

    Позволяет анализировать скорость продаж товаров со склада.
    Метод может не отдавать все карточки — есть ограничения.
    """

    skus: list[int | str] = Field(..., description="Список SKU для анализа оборачиваемости.")

    @field_validator("skus", mode="after")
    @classmethod
    def skus_to_str(cls, v: list[int | str]) -> list[str]:
        return [str(s) for s in v]


def _sku_list_to_str(v: list[int | str], max_len: int | None = None) -> list[str]:
    """Приведение списка SKU к строкам с опциональной проверкой лимита"""
    result = [str(s) for s in v]
    if max_len is not None and len(result) > max_len:
        raise ValueError(f"Максимум {max_len} SKU в одном запросе.")
    return result


class ProductQueriesDetailsRequest(OzonBaseModel):
    """POST /v1/analytics/product-queries/details — детализация по запросам товара.

    Показывает позицию товара в поиске по каждому запросу.
    """

    date_from: str = Field(..., description="Начало периода (ISO 8601, date-time).")
    date_to: str = Field(..., description="Конец периода (ISO 8601, date-time).")
    sku: int | str = Field(..., description="SKU товара.")
    page: int = Field(default=1, description="Номер страницы.")
    page_size: int = Field(default=100, le=1000, description="Количество запросов на странице.")

    normalize_from = field_validator("date_from", mode="before")(_to_iso_str)
    normalize_to = field_validator("date_to", mode="before")(_to_iso_str)

    @field_validator("sku", mode="before")
    @classmethod
    def sku_to_str(cls, v: int | str) -> str:
        return str(v)


class ManageStocksRequest(OzonBaseModel):
    """POST /v1/analytics/manage/stocks — управление остатками на складах (бета).

    Позволяет не только смотреть, но и управлять остатками через API.
    """

    skus: list[int | str] = Field(..., description="Список SKU для управления остатками.")
    warehouse_id: int | None = Field(default=None, description="Идентификатор склада.")
    action: str | None = Field(default=None, description="Действие с остатками (зависит от версии API).")

    @field_validator("skus", mode="after")
    @classmethod
    def skus_to_str(cls, v: list[int | str]) -> list[str]:
        return _sku_list_to_str(v)


class FinanceTransactionDateFilter(OzonBaseModel):
    """Фильтр по дате в финансовых операциях (/v3/finance/transaction/list).

    API Ozon ожидает поля ``from``/``to`` (а не ``date_from``/``date_to``)
    и формат даты ``YYYY-MM-DDTHH:mm:ss.000Z``.
    """

    from_: datetime | str = Field(..., alias="from", description="Начало периода (RFC 3339: YYYY-MM-DDTHH:mm:ss.000Z).")
    to: datetime | str = Field(..., description="Конец периода (RFC 3339: YYYY-MM-DDTHH:mm:ss.999Z).")

    normalize_from = field_validator("from_", mode="before")(_to_rfc3339_ozon)
    normalize_to = field_validator("to", mode="before")(_to_rfc3339_ozon)


class FinanceTransactionListFilter(OzonBaseModel):
    """Фильтр списка финансовых операций (/v3/finance/transaction/list)"""

    date: FinanceTransactionDateFilter = Field(..., description="Период операций.")
    operation_type: list[str] | None = Field(default=None, description="Типы операций.")
    posting_number: str | None = Field(default=None, description="Номер отправления.")
    transaction_type: TransactionType | str = Field(
        default=TransactionType.ALL,
        description="Тип транзакции.",
    )


class FinanceTransactionListRequest(OzonBaseModel):
    """POST /v3/finance/transaction/list — детальные финансовые транзакции.

    Позволяет рассчитать чистую прибыль по каждому заказу.
    """

    filter_: FinanceTransactionListFilter = Field(..., alias="filter")
    page: int = Field(default=1, description="Номер страницы.")
    page_size: int = Field(default=1000, le=1000, description="Количество операций на странице.")


class FinanceTransactionTotalsRequest(OzonBaseModel):
    """POST /v3/finance/transaction/totals — итоговые финансовые показатели за период.

    Отличие от /v3/finance/transaction/list: поля фильтра передаются
    на верхнем уровне тела запроса, без обёртки ``filter`` (см. swagger:
    ``financev3FinanceTransactionTotalsV3Request`` и его example).
    Достаточно указать либо период ``date``, либо ``posting_number`` —
    иначе API отвечает 400 «date required when posting_number empty».
    """

    date: FinanceTransactionDateFilter | None = Field(
        default=None,
        description="Период операций. Обязателен, если ``posting_number`` пуст.",
    )
    posting_number: str | None = Field(
        default=None,
        description="Номер отправления (альтернатива фильтру по периоду).",
    )
    transaction_type: TransactionType | str = Field(
        default=TransactionType.ALL,
        description="Тип транзакции.",
    )

    @model_validator(mode="after")
    def check_date_or_posting(self) -> "FinanceTransactionTotalsRequest":
        if self.date is None and not (self.posting_number or "").strip():
            raise ValueError(
                "Требуется date или posting_number (swagger /v3/finance/transaction/totals)."
            )
        return self


class ReportReturnsCreateRequest(OzonBaseModel):
    """POST /v2/report/returns/create — создание отчёта по возвратам.

    Возвращает код отчёта; статус и файл нужно запрашивать через /v1/report/info.
    """

    report_type: SellerReportType = Field(
        default=SellerReportType.SELLER_RETURNS,
        description="Тип отчёта. Для возвратов — SELLER_RETURNS.",
    )
    date_from: datetime | str = Field(..., description="Начало периода (ISO 8601).")
    date_to: datetime | str = Field(..., description="Конец периода (ISO 8601).")
    language: str = Field(default="DEFAULT", description="Язык отчёта.")

    normalize_from = field_validator("date_from", mode="before")(_to_iso_str)
    normalize_to = field_validator("date_to", mode="before")(_to_iso_str)


class ReviewListRequest(OzonBaseModel):
    """POST /v1/review/list — список отзывов.

    Важно: метод не возвращает номер заказа (order_number).
    """

    last_id: str = Field(default="", description="Идентификатор последнего отзыва на странице.")
    limit: int = Field(default=20, ge=20, le=100, description="Количество отзывов: 20–100.")
    sort_dir: ReviewSortDir | None = Field(default=None, description="Направление сортировки.")
    status: ReviewStatus | None = Field(default=None, description="Статус отзыва.")


class PostingStatusDateFilter(OzonBaseModel):
    """Фильтр по дате изменения статуса отправления"""

    date_from: datetime | str = Field(..., description="Начало периода (ISO 8601).")
    date_to: datetime | str = Field(..., description="Конец периода (ISO 8601).")

    normalize_from = field_validator("date_from", mode="before")(_to_iso_str)
    normalize_to = field_validator("date_to", mode="before")(_to_iso_str)


class PostingFbsListFilter(OzonBaseModel):
    """Фильтр списка FBS-поставок (/v3/posting/fbs/list)"""

    since: datetime | str = Field(..., description="Начало периода (ISO 8601).")
    to: datetime | str = Field(..., description="Конец периода (ISO 8601).")
    delivery_method_id: list[int] | None = None
    fbp_filter: FbpFilter | None = Field(default=None, alias="fbpFilter")
    order_id: int | None = None
    provider_id: list[int] | None = None
    status: str | None = None
    warehouse_id: list[int] | None = None
    last_changed_status_date: PostingStatusDateFilter | None = None

    normalize_since = field_validator("since", mode="before")(_to_iso_str)
    normalize_to = field_validator("to", mode="before")(_to_iso_str)


class PostingFbsWithParams(OzonBaseModel):
    """Дополнительные поля в ответе FBS-поставок"""

    analytics_data: bool | None = Field(default=None, description="Добавить аналитические данные.")
    barcodes: bool | None = Field(default=None, description="Добавить штрихкоды.")
    financial_data: bool | None = Field(default=None, description="Добавить финансовые данные.")
    legal_info: bool | None = Field(default=None, description="Добавить юридическую информацию.")
    translit: bool | None = Field(default=None, description="Транслитерировать значения.")


class PostingFbsListRequest(OzonBaseModel):
    """POST /v3/posting/fbs/list — список поставок FBS.

    В ответе есть shipment_date_without_delay — дата отгрузки без учёта задержек.
    """

    filter_: PostingFbsListFilter = Field(..., alias="filter")
    dir: PostingSortDir | None = Field(default=None, description="Направление сортировки.")
    limit: int = Field(default=50, ge=1, le=1000, description="Количество на странице: 1–1000.")
    offset: int = Field(default=0, ge=0, description="Смещение.")
    with_: PostingFbsWithParams | None = Field(default=None, alias="with")


class PostingFbsUnfulfilledListFilter(OzonBaseModel):
    """Фильтр неотгруженных FBS-поставок (/v3/posting/fbs/unfulfilled/list)"""

    cutoff_from: datetime | str = Field(..., description="Начало периода cutoff (ISO 8601).")
    cutoff_to: datetime | str = Field(..., description="Конец периода cutoff (ISO 8601).")
    delivering_date_from: datetime | str | None = None
    delivering_date_to: datetime | str | None = None
    delivery_method_id: list[int] | None = None
    fbp_filter: FbpFilter | None = Field(default=None, alias="fbpFilter")
    provider_id: list[int] | None = None
    status: str | None = None
    warehouse_id: list[int] | None = None

    normalize_cutoff_from = field_validator("cutoff_from", mode="before")(_to_iso_str)
    normalize_cutoff_to = field_validator("cutoff_to", mode="before")(_to_iso_str)


class PostingFbsUnfulfilledListRequest(OzonBaseModel):
    """POST /v3/posting/fbs/unfulfilled/list — список неотгруженных поставок FBS"""

    filter_: PostingFbsUnfulfilledListFilter = Field(..., alias="filter")
    dir: PostingSortDir | None = Field(default=None, description="Направление сортировки.")
    limit: int = Field(default=50, ge=1, le=1000, description="Количество на странице: 1–1000.")
    offset: int = Field(default=0, ge=0, description="Смещение.")
    with_: PostingFbsWithParams | None = Field(default=None, alias="with")


class ProductInfoStocksRequest(OzonBaseModel):
    """POST /v4/product/info/stocks — информация об остатках по товарам"""

    offer_id: str | None = Field(default=None, description="Артикул продавца.")
    product_id: int | str | None = Field(default=None, description="Идентификатор товара.")
    sku: int | str | None = Field(default=None, description="SKU товара.")
    page: int = Field(default=1, description="Номер страницы.")
    page_size: int = Field(default=100, le=1000, description="Количество товаров на странице.")


class ProductInfoListRequest(OzonBaseModel):
    """POST /v3/product/info/list — информация о товарах.

    В ответе есть model_info.count — если > 1, это склеенная карточка.
    """

    offer_id: list[str] | None = Field(default=None, description="Список артикулов продавца.")
    product_id: list[int | str] | None = Field(default=None, description="Список идентификаторов товаров.")
    sku: list[int | str] | None = Field(default=None, description="Список SKU.")

    @field_validator("product_id", "sku", mode="after")
    @classmethod
    def ids_to_str(cls, v: list[int | str] | None) -> list[str] | None:
        if v is None:
            return None
        return [str(item) for item in v]


class ProductInfoPricesV5Filter(OzonBaseModel):
    """Фильтр цен и комиссий (/v5/product/info/prices)"""

    offer_id: list[str] | None = Field(default=None, description="Список артикулов продавца.")
    product_id: list[int | str] | None = Field(
        default=None, description="Список идентификаторов товаров."
    )
    visibility: Visibility = Field(
        default=Visibility.ALL,
        description="Фильтр по видимости товара.",
    )

    @field_validator("product_id", mode="after")
    @classmethod
    def ids_to_str(cls, v: list[int | str] | None) -> list[str] | None:
        if v is None:
            return None
        return [str(item) for item in v]


class ProductInfoPricesV5Request(OzonBaseModel):
    """POST /v5/product/info/prices — цены, комиссии и логистические тарифы.

    В ответе по каждому товару: блок ``commissions`` (проценты и суммы
    логистики FBO/FBS), ``price`` (текущая/старая/минимальная цена, НДС) и
    ``volume_weight`` (объёмный вес в литрах) — основа для расчёта
    юнит-экономики и тарифа логистики.
    """

    cursor: str = Field(
        default="",
        description="Курсор для следующей страницы. Пусто при первом запросе.",
    )
    filter_: ProductInfoPricesV5Filter = Field(
        default_factory=ProductInfoPricesV5Filter,
        alias="filter",
        description="Параметры фильтрации товаров.",
    )
    limit: int = Field(
        default=1000,
        ge=1,
        le=1000,
        description="Количество значений на странице: 1–1000.",
    )


class WarehouseListRequest(OzonBaseModel):
    """POST /v2/warehouse/list — список складов"""

    # Метод не требует тела запроса, но оставляем пустую модель для единообразия.
    pass
