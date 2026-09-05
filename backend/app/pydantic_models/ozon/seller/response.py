"""Модели ответов Seller API (на основе swagger_saller.json v2.1)"""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from backend.app.pydantic_models.ozon.commons import OzonBaseModel
from backend.app.pydantic_models.ozon.seller.enums import ItemTag, TurnoverGrade


class AnalyticsDataRowDimension(OzonBaseModel):
    """Измерение в строке аналитического отчёта (/v1/analytics/data)"""

    id: str | None = Field(default=None, description="Идентификатор товара в системе Ozon — SKU.")
    name: str | None = Field(default=None, description="Наименование.")


class AnalyticsDataRow(OzonBaseModel):
    """Строка данных аналитического отчёта"""

    dimensions: list[AnalyticsDataRowDimension] = Field(
        ...,
        description="Группировка данных в отчёте.",
    )
    metrics: list[float] = Field(
        ...,
        description="Список значений метрики.",
    )


class AnalyticsGetDataResponseResult(OzonBaseModel):
    """Результаты запроса аналитики"""

    data: list[AnalyticsDataRow] = Field(
        ...,
        description="Массив данных.",
    )
    totals: list[float] = Field(
        ...,
        description="Итоговые и средние значения метрик.",
    )


class AnalyticsGetDataResponse(OzonBaseModel):
    """Ответ POST /v1/analytics/data"""

    result: AnalyticsGetDataResponseResult | None = Field(
        default=None,
        description="Результаты запроса.",
    )
    timestamp: str | None = Field(
        default=None,
        description="Время создания отчёта.",
    )


class AnalyticsStocksResponseItem(OzonBaseModel):
    """Элемент ответа API аналитики остатков (/v1/analytics/stocks)"""

    ads: float | None = Field(
        default=None,
        description="Среднесуточное количество проданных единиц товара за последние 28 дней."
    )
    available_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара, доступное к продаже."
    )
    cluster_id: int | None = Field(
        default=None,
        description="Идентификатор кластера."
    )
    cluster_name: str | None = Field(
        default=None,
        description="Название кластера."
    )
    days_without_sales: int | None = Field(
        default=None,
        description="Количество дней без продаж."
    )
    excess_stock_count: int | None = Field(
        default=None,
        description="Количество излишков с поставки, доступных к вывозу."
    )
    expiring_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара с истекающим сроком годности."
    )
    idc: float | None = Field(
        default=None,
        description="На сколько дней хватит остатка с учётом среднесуточных продаж за 28 дней."
    )
    item_tags: list[ItemTag] | None = Field(
        default=None,
        description="Теги товара: ECONOM, NOVEL, DISCOUNT, FBS_RETURN, SUPER и т. д."
    )
    name: str | None = Field(
        default=None,
        description="Название товара."
    )
    offer_id: str | None = Field(
        default=None,
        description="Артикул продавца."
    )
    other_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара, проходящих проверку."
    )
    requested_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара в заявках на поставку."
    )
    return_from_customer_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара в процессе возврата от покупателей."
    )
    return_to_seller_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара, готовящихся к вывозу по вашей заявке."
    )
    sku: int | None = Field(
        default=None,
        description="Идентификатор товара в системе Ozon — SKU."
    )
    stock_defect_stock_count: int | None = Field(
        default=None,
        description="Количество брака, доступное к вывозу со склада."
    )
    transit_defect_stock_count: int | None = Field(
        default=None,
        description="Количество брака, доступное к вывозу с поставки."
    )
    transit_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара в поставках в пути."
    )
    # TurnoverGrade вне enum сохраняем строкой — ответ не отбрасывать
    turnover_grade: TurnoverGrade | str | None = Field(
        default=None,
        description="Статус ликвидности товара."
    )
    valid_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара, доступное для продажи."
    )
    waiting_docs_stock_count: int | None = Field(
        default=None,
        description="Количество маркируемых товаров, ожидающих ваших действий."
    )
    warehouse_id: int | None = Field(
        default=None,
        description="Идентификатор склада."
    )
    warehouse_name: str | None = Field(
        default=None,
        description="Название склада."
    )


class ProductListItem(OzonBaseModel):
    """Элемент списка товаров (/v3/product/list)"""

    offer_id: str | None = Field(default=None, description="Артикул продавца.")
    product_id: int | None = Field(default=None, description="Идентификатор товара.")
    sku: int | None = Field(default=None, description="SKU.")
    name: str | None = Field(default=None, description="Название товара.")


class ProductListResponse(OzonBaseModel):
    """Ответ POST /v3/product/list"""

    items: list[ProductListItem] = Field(default_factory=list, description="Список товаров.")
    last_id: str | None = Field(default=None, description="Идентификатор последнего значения.")
    total: int | None = Field(default=None, description="Общее количество товаров.")

    days_without_sales: int | None = Field(
        default=None,
        description="Количество дней без продаж."
    )
    excess_stock_count: int | None = Field(
        default=None,
        description="Количество излишков с поставки, которые доступны к вывозу."
    )
    expiring_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара с истекающим сроком годности."
    )
    idc: float | None = Field(
        default=None,
        description="Количество дней, на которое хватит остатка товара с учётом среднесуточных продаж за 28 дней."
    )
    item_tags: list[str] | None = Field(
        default=None,
        description="Теги товара."
    )
    name: str | None = Field(
        default=None,
        description="Название товара."
    )
    offer_id: str | None = Field(
        default=None,
        description="Идентификатор товара в системе продавца — артикул."
    )
    other_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара, проходящих проверку."
    )
    requested_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара в заявках на поставку."
    )
    return_from_customer_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара в процессе возврата от покупателей."
    )
    return_to_seller_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара, готовящихся к вывозу по вашей заявке."
    )
    sku: int | None = Field(
        default=None,
        description="Идентификатор товара в системе Ozon — SKU."
    )
    stock_defect_stock_count: int | None = Field(
        default=None,
        description="Количество брака, доступное к вывозу со стока."
    )
    transit_defect_stock_count: int | None = Field(
        default=None,
        description="Количество брака, доступное к вывозу с поставки."
    )
    transit_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара в поставках в пути."
    )
    turnover_grade: str | None = Field(
        default=None,
        description="Статус ликвидности товара."
    )
    valid_stock_count: int | None = Field(
        default=None,
        description="Количество единиц товара, доступное для продажи."
    )
    waiting_docs_stock_count: int | None = Field(
        default=None,
        description="Количество маркируемых товаров, которые ожидают ваших действий."
    )
    warehouse_id: int | None = Field(
        default=None,
        description="Идентификатор склада."
    )
    warehouse_name: str | None = Field(
        default=None,
        description="Название склада."
    )


class AnalyticsStocksResponse(OzonBaseModel):
    """Ответ POST /v1/analytics/stocks — аналитика остатков на складах"""

    items: list[AnalyticsStocksResponseItem | None] = Field(
        ...,
        description="Информация о товарах."
    )


class ProductQueriesResponseItem(OzonBaseModel):
    """Элемент аналитики поисковых запросов (/v1/analytics/product-queries)"""

    category: str | None = Field(default=None, description="Категория запроса.")
    currency: str | None = Field(default=None, description="Валюта.")
    gmv: float | None = Field(default=None, description="Доход по запросу.")
    name: str | None = Field(default=None, description="Текст запроса.")
    offer_id: str | None = Field(default=None, description="Артикул продавца.")
    position: float | None = Field(default=None, description="Средняя позиция товара в поиске.")
    sku: int | None = Field(default=None, description="SKU товара.")
    unique_search_users: int | None = Field(default=None, description="Уникальные пользователи поиска.")
    unique_view_users: int | None = Field(default=None, description="Уникальные пользователи просмотра карточки.")
    view_conversion: float | None = Field(default=None, description="Конверсия по просмотру.")


class ProductQueriesResponse(OzonBaseModel):
    """Ответ POST /v1/analytics/product-queries"""

    items: list[ProductQueriesResponseItem] = Field(
        default_factory=list,
        description="Список запросов.",
    )
    total: int | None = Field(default=None, description="Общее количество запросов.")
    page_count: int | None = Field(default=None, description="Количество страниц.")


class TurnoverStocksResponseItem(OzonBaseModel):
    """Элемент ответа /v1/analytics/turnover/stocks"""

    ads: float | None = Field(default=None, description="Среднесуточные продажи за 60 дней.")
    current_stock: int | None = Field(default=None, description="Текущий остаток, шт.")
    idc: float | None = Field(default=None, description="Индекс достаточности (дней).")
    idc_grade: str | None = Field(default=None, description="Оценка достаточности.")
    name: str | None = Field(default=None, description="Название товара.")
    offer_id: str | None = Field(default=None, description="Артикул продавца.")
    sku: int | None = Field(default=None, description="SKU товара.")
    turnover: float | None = Field(default=None, description="Оборачиваемость, дней.")
    turnover_grade: str | None = Field(default=None, description="Оценка оборачиваемости.")


class TurnoverStocksResponse(OzonBaseModel):
    """Ответ POST /v1/analytics/turnover/stocks"""

    items: list[TurnoverStocksResponseItem] = Field(default_factory=list)


class RatingSummaryItem(OzonBaseModel):
    """Элемент рейтинга в /v1/rating/summary"""

    rating_type: str | None = Field(default=None, description="Тип рейтинга.")
    score: float | None = Field(default=None, description="Текущий балл.")
    description: str | None = Field(default=None, description="Описание.")


class RatingSummaryGroup(OzonBaseModel):
    """Группа рейтингов в /v1/rating/summary"""

    group_name: str | None = Field(default=None, description="Название группы.")
    items: list[RatingSummaryItem] = Field(default_factory=list)


class RatingSummaryResponse(OzonBaseModel):
    """Ответ POST /v1/rating/summary"""

    groups: list[RatingSummaryGroup] = Field(default_factory=list)


class RatingHistoryResponse(OzonBaseModel):
    """Ответ GET /v1/rating/history — история изменения рейтинга продавца"""

    ratings: list[dict[str, Any]] = Field(default_factory=list, description="История рейтингов по типам.")


class ProductQueriesDetailsItem(OzonBaseModel):
    """Элемент детализации поисковых запросов (/v1/analytics/product-queries/details)"""

    currency: str | None = Field(default=None, description="Валюта.")
    gmv: float | None = Field(default=None, description="Выручка по запросу.")
    order_count: int | None = Field(default=None, description="Количество заказов по запросу.")
    position: float | None = Field(default=None, description="Средняя позиция товара в поиске.")
    query: str | None = Field(default=None, description="Текст запроса.")
    query_index: int | None = Field(default=None, description="Индекс запроса.")
    sku: int | None = Field(default=None, description="SKU товара.")
    unique_search_users: int | None = Field(default=None, description="Уникальные пользователи поиска.")
    unique_view_users: int | None = Field(default=None, description="Уникальные пользователи просмотра.")
    view_conversion: float | None = Field(default=None, description="Конверсия по просмотру.")


class ProductQueriesDetailsResponse(OzonBaseModel):
    """Ответ POST /v1/analytics/product-queries/details"""

    items: list[ProductQueriesDetailsItem] = Field(default_factory=list, description="Список запросов.")


class ManageStocksResponse(OzonBaseModel):
    """Ответ POST /v1/analytics/manage/stocks — управление остатками (бета)"""


class OperationPosting(OzonBaseModel):
    """Информация об отправлении в финансовой операции"""

    delivery_schema: str | None = Field(default=None, description="Схема доставки.")
    order_date: str | None = Field(default=None, description="Дата приёма отправления в обработку.")
    posting_number: str | None = Field(default=None, description="Номер отправления.")
    warehouse_id: int | None = Field(default=None, description="Идентификатор склада.")


class OperationItem(OzonBaseModel):
    """Товар в финансовой операции"""

    name: str | None = Field(default=None, description="Название товара.")
    sku: int | None = Field(default=None, description="SKU товара.")


class OperationService(OzonBaseModel):
    """Услуга в финансовой операции"""

    name: str | None = Field(default=None, description="Название услуги.")
    price: float | None = Field(default=None, description="Стоимость услуги.")


class FinanceOperation(OzonBaseModel):
    """Финансовая операция (/v3/finance/transaction/list)"""

    operation_id: int | None = Field(default=None, description="Идентификатор операции.")
    operation_type: str | None = Field(default=None, description="Тип операции.")
    operation_date: str | None = Field(default=None, description="Дата операции.")
    operation_type_name: str | None = Field(default=None, description="Название типа операции.")
    delivery_charge: float | None = Field(default=None, description="Стоимость доставки.")
    return_delivery_charge: float | None = Field(default=None, description="Стоимость возвратной доставки.")
    accruals_for_sale: float | None = Field(default=None, description="Начисления за продажу.")
    sale_commission: float | None = Field(default=None, description="Комиссия за продажу.")
    amount: float | None = Field(default=None, description="Сумма операции.")
    type: str | None = Field(default=None, description="Тип начисления.")
    posting: OperationPosting | None = Field(default=None, description="Информация об отправлении.")
    items: list[OperationItem] = Field(default_factory=list, description="Товары.")
    services: list[OperationService] = Field(default_factory=list, description="Услуги.")


class FinanceTransactionListResult(OzonBaseModel):
    """``result`` из ответа POST /v3/finance/transaction/list"""

    operations: list[FinanceOperation] = Field(default_factory=list, description="Список операций.")
    page_count: int | None = Field(
        default=None, description="Количество страниц (0 — страниц больше нет)."
    )
    row_count: int | None = Field(
        default=None, description="Количество транзакций на всех страницах."
    )


class FinanceTransactionListResponse(OzonBaseModel):
    """Ответ POST /v3/finance/transaction/list.

    По схеме swagger_saller.json (financev3FinanceTransactionListV3Response)
    данные вложены в ``result``: ``{"result": {"operations": [...], "page_count": N,
    "row_count": M}}``. Плоский формат без обёртки ``result`` также принимается
    для устойчивости к вариациям API.
    """

    result: FinanceTransactionListResult = Field(
        default_factory=FinanceTransactionListResult, description="Результаты запроса."
    )

    @model_validator(mode="before")
    @classmethod
    def _wrap_flat_payload(cls, data: Any) -> Any:
        """Плоский ответ без ``result`` оборачивается для совместимости"""
        if (
            isinstance(data, dict)
            and "result" not in data
            and {"operations", "page_count", "row_count"} & data.keys()
        ):
            return {"result": data}
        return data

    @property
    def operations(self) -> list[FinanceOperation]:
        return self.result.operations

    @property
    def page_count(self) -> int | None:
        return self.result.page_count

    @property
    def row_count(self) -> int | None:
        return self.result.row_count


class FinanceTransactionTotalsResponse(OzonBaseModel):
    """Ответ POST /v3/finance/transaction/totals"""

    result: dict[str, Any] = Field(default_factory=dict, description="Итоговые показатели.")


class ReportReturnsCreateResponse(OzonBaseModel):
    """Ответ POST /v2/report/returns/create"""

    code: str | None = Field(default=None, description="Код отчёта.")
    created_at: str | None = Field(default=None, description="Дата создания.")
    error: str | None = Field(default=None, description="Код ошибки.")
    file: str | None = Field(default=None, description="Ссылка на файл отчёта.")
    params: dict[str, str] = Field(default_factory=dict, description="Параметры отчёта.")
    report_type: str | None = Field(default=None, description="Тип отчёта.")
    status: str | None = Field(default=None, description="Статус формирования.")


class Review(OzonBaseModel):
    """Отзыв (/v1/review/list)"""

    comments_amount: int | None = Field(default=None, description="Количество комментариев.")
    id: str | None = Field(default=None, description="Идентификатор отзыва.")
    is_rating_participant: bool | None = Field(default=None, description="Учитывается в рейтинге.")
    order_status: str | None = Field(default=None, description="Статус заказа.")
    photos_amount: int | None = Field(default=None, description="Количество фото.")
    published_at: str | None = Field(default=None, description="Дата публикации.")
    rating: int | None = Field(default=None, description="Оценка.")
    sku: int | None = Field(default=None, description="SKU товара.")
    status: str | None = Field(default=None, description="Статус отзыва.")
    text: str | None = Field(default=None, description="Текст отзыва.")
    videos_amount: int | None = Field(default=None, description="Количество видео.")


class ReviewListResponse(OzonBaseModel):
    """Ответ POST /v1/review/list"""

    has_next: bool | None = Field(default=None, description="Есть ли следующая страница.")
    last_id: str | None = Field(default=None, description="Идентификатор последнего отзыва.")
    reviews: list[Review] = Field(default_factory=list, description="Список отзывов.")


class FbsPostingAnalyticsData(OzonBaseModel):
    """Аналитические данные FBS-поставки"""

    city: str | None = Field(default=None, description="Город доставки.")
    delivery_date_begin: str | None = Field(default=None, description="Начало доставки.")
    delivery_date_end: str | None = Field(default=None, description="Конец доставки.")
    delivery_type: str | None = Field(default=None, description="Способ доставки.")
    is_legal: bool | None = Field(default=None, description="Юридическое лицо.")
    is_premium: bool | None = Field(default=None, description="Premium-покупатель.")
    payment_type_group_name: str | None = Field(default=None, description="Способ оплаты.")
    region: str | None = Field(default=None, description="Регион доставки.")
    tpl_provider: str | None = Field(default=None, description="Транспортная компания.")
    tpl_provider_id: int | None = Field(default=None, description="ID транспортной компании.")
    warehouse: str | None = Field(default=None, description="Склад отправки.")
    warehouse_id: int | None = Field(default=None, description="ID склада.")


class FbsPostingProduct(OzonBaseModel):
    """Товар в FBS-поставке"""

    digital_codes: list[str] = Field(default_factory=list)
    name: str | None = Field(default=None, description="Название товара.")
    offer_id: str | None = Field(default=None, description="Артикул продавца.")
    price: float | None = Field(default=None, description="Цена.")
    quantity: int | None = Field(default=None, description="Количество.")
    sku: int | None = Field(default=None, description="SKU.")


class FbsPostingCancellation(OzonBaseModel):
    """Причина отмены FBS-поставки"""

    affect_cancellation_rating: bool | None = None
    cancel_reason: str | None = None
    cancel_reason_id: int | None = None
    cancellation_initiator: str | None = None
    cancellation_type: str | None = None
    cancelled_after_ship: bool | None = None


class FbsPostingRequirements(OzonBaseModel):
    """Требования к поставке FBS"""

    products_requiring_gtd: list[str] = Field(default_factory=list)
    products_requiring_country: list[str] = Field(default_factory=list)
    products_requiring_mandatory_mark: list[str] = Field(default_factory=list)
    products_requiring_rnpt: list[str] = Field(default_factory=list)


class FbsBarcodes(OzonBaseModel):
    """Штрихкоды поставки"""

    lower_barcode: str | None = None
    upper_barcode: str | None = None


class FbsPosting(OzonBaseModel):
    """Элемент FBS-поставки (/v3/posting/fbs/list)"""

    posting_number: str | None = Field(default=None, description="Номер отправления.")
    order_id: int | None = Field(default=None, description="Номер заказа.")
    order_number: str | None = Field(default=None, description="Номер заказа покупателя.")
    status: str | None = Field(default=None, description="Статус отправления.")
    shipment_date: str | None = Field(default=None, description="Дата отгрузки.")
    shipment_date_without_delay: str | None = Field(
        default=None, description="Дата отгрузки без учёта задержек."
    )
    cutoff: str | None = Field(default=None, description="Крайнее время комплектации.")
    delivering_date: str | None = Field(default=None, description="Дата передачи в доставку.")
    products: list[FbsPostingProduct] = Field(default_factory=list, description="Товары.")
    analytics_data: FbsPostingAnalyticsData | None = Field(default=None, description="Аналитика.")
    financial_data: dict[str, Any] | None = Field(default=None, description="Финансовые данные.")
    cancellation: FbsPostingCancellation | None = Field(default=None, description="Отмена.")
    requirements: FbsPostingRequirements | None = Field(default=None, description="Требования.")
    barcodes: FbsBarcodes | None = Field(default=None, description="Штрихкоды.")


class PostingFbsListResponse(OzonBaseModel):
    """Ответ POST /v3/posting/fbs/list"""

    has_next: bool | None = Field(default=None, description="Есть ли следующая страница.")
    postings: list[FbsPosting] = Field(default_factory=list, description="Список поставок.")


class PostingFbsUnfulfilledListResponse(OzonBaseModel):
    """Ответ POST /v3/posting/fbs/unfulfilled/list"""

    has_next: bool | None = Field(default=None, description="Есть ли следующая страница.")
    postings: list[FbsPosting] = Field(default_factory=list, description="Список неотгруженных поставок.")


class ProductInfoStocksStock(OzonBaseModel):
    """Остаток товара на складе (/v4/product/info/stocks)"""

    present: int | None = Field(default=None, description="Доступно на складе.")
    reserved: int | None = Field(default=None, description="Зарезервировано.")
    shipment_type: str | None = Field(default=None, description="Тип отгрузки.")
    sku: int | None = Field(default=None, description="SKU.")
    type: str | None = Field(default=None, description="Тип склада.")


class ProductInfoStocksItem(OzonBaseModel):
    """Элемент ответа /v4/product/info/stocks"""

    offer_id: str | None = Field(default=None, description="Артикул продавца.")
    product_id: int | None = Field(default=None, description="Идентификатор товара.")
    stocks: list[ProductInfoStocksStock] = Field(default_factory=list, description="Остатки.")


class ProductInfoStocksResponse(OzonBaseModel):
    """Ответ POST /v4/product/info/stocks"""

    cursor: str | None = Field(default=None, description="Курсор для следующей страницы.")
    items: list[ProductInfoStocksItem] = Field(default_factory=list, description="Список товаров.")
    total: int | None = Field(default=None, description="Общее количество товаров.")


class ProductInfoStocksStockV3(OzonBaseModel):
    """Остаток товара в /v3/product/info/list"""

    present: int | None = Field(default=None, description="Доступно на складе.")
    reserved: int | None = Field(default=None, description="Зарезервировано.")
    sku: int | None = Field(default=None, description="SKU.")
    source: str | None = Field(default=None, description="Источник/режим хранения.")


class ProductInfoStocksV3(OzonBaseModel):
    """Блок остатков в /v3/product/info/list"""

    has_stock: bool | None = Field(default=None, description="Есть ли остатки.")
    stocks: list[ProductInfoStocksStockV3] = Field(default_factory=list, description="Остатки.")


class ProductInfoVisibilityDetails(OzonBaseModel):
    """Детали видимости товара"""

    has_price: bool | None = Field(default=None, description="Установлена ли цена.")
    has_stock: bool | None = Field(default=None, description="Есть ли остатки.")


class ProductInfoModelInfo(OzonBaseModel):
    """Информация о модели товара.

    count > 1 означает, что карточка склеена с другими товарами.
    """

    count: int | None = Field(default=None, description="Количество товаров в модели.")
    model_id: int | None = Field(default=None, description="Идентификатор модели.")


class ProductInfoCommission(OzonBaseModel):
    """Комиссия по одной схеме продажи (/v3/product/info/list.commissions)"""

    sale_schema: str | None = Field(default=None, description="Схема продажи (FBO/FBS).")
    percent: float | None = Field(default=None, description="Процент комиссии.")
    value: float | None = Field(default=None, description="Сумма комиссии за единицу.")
    delivery_amount: float | None = Field(default=None, description="Стоимость доставки.")
    return_amount: float | None = Field(default=None, description="Стоимость возврата.")
    title: str | None = Field(default=None, description="Название схемы.")


class ProductInfoItem(OzonBaseModel):
    """Элемент ответа /v3/product/info/list"""

    offer_id: str | None = Field(default=None, description="Артикул продавца.")
    product_id: int | None = Field(default=None, description="Идентификатор товара.")
    sku: int | None = Field(default=None, description="SKU.")
    name: str | None = Field(default=None, description="Название товара.")
    barcode: str | None = Field(default=None, description="Штрихкод.")
    buybox_price: str | None = Field(default=None, description="Цена buybox.")
    category_id: int | None = Field(default=None, description="ID категории.")
    created_at: str | None = Field(default=None, description="Дата создания.")
    # Цена и объёмные характеристики — основа тарифа логистики.
    price: str | None = Field(default=None, description="Цена товара (строкой, как в API).")
    old_price: str | None = Field(default=None, description="Цена до скидки.")
    marketing_price: str | None = Field(default=None, description="Цена с учётом маркетинговых акций Ozon.")
    min_price: str | None = Field(default=None, description="Минимальная цена (Ozon-алгоритмы / конкуренты).")
    volume_weight: float | None = Field(
        default=None,
        description="Объёмный вес товара в литрах — база для расчёта тарифа логистики.",
    )
    vat: str | None = Field(default=None, description="Ставка НДС.")
    commissions: list[ProductInfoCommission] = Field(
        default_factory=list,
        description="Комиссии по схемам продажи (FBO/FBS): процент, сумма, доставка, возврат.",
    )
    stocks: ProductInfoStocksV3 | list[ProductInfoStocksV3] | None = Field(
        default=None,
        description="Остатки: API v3 отдаёт объект {has_stock, stocks}, а не список."
    )
    visibility_details: ProductInfoVisibilityDetails | None = Field(default=None, description="Видимость.")
    model_info: ProductInfoModelInfo | None = Field(default=None, description="Информация о модели.")
    status: dict[str, Any] | None = Field(default=None, description="Статусы товара.")


class ProductInfoListResponse(OzonBaseModel):
    """Ответ POST /v3/product/info/list"""

    items: list[ProductInfoItem] = Field(default_factory=list, description="Список товаров.")


class ProductInfoPricesCommissionsV5(OzonBaseModel):
    """Блок комиссий и логистических тарифов /v5/product/info/prices"""

    fbo_deliv_to_customer_amount: float | None = Field(
        default=None, description="Стоимость доставки до покупателя (FBO)."
    )
    fbo_direct_flow_trans_min_amount: float | None = Field(
        default=None, description="Минимальная логистика прямой поток (FBO)."
    )
    fbo_direct_flow_trans_max_amount: float | None = Field(
        default=None, description="Максимальная логистика прямой поток (FBO)."
    )
    fbo_return_flow_amount: float | None = Field(
        default=None, description="Логистика возвратного потока (FBO)."
    )
    fbs_deliv_to_customer_amount: float | None = Field(
        default=None, description="Стоимость доставки до покупателя (FBS)."
    )
    fbs_direct_flow_trans_min_amount: float | None = Field(
        default=None, description="Минимальная логистика прямой поток (FBS)."
    )
    fbs_direct_flow_trans_max_amount: float | None = Field(
        default=None, description="Максимальная логистика прямой поток (FBS)."
    )
    fbs_first_mile_min_amount: float | None = Field(
        default=None, description="Минимальная стоимость первой мили (FBS)."
    )
    fbs_first_mile_max_amount: float | None = Field(
        default=None, description="Максимальная стоимость первой мили (FBS)."
    )
    fbs_return_flow_amount: float | None = Field(
        default=None, description="Логистика возвратного потока (FBS)."
    )
    sales_percent_fbo: float | None = Field(default=None, description="Процент комиссии за продажу (FBO).")
    sales_percent_fbs: float | None = Field(default=None, description="Процент комиссии за продажу (FBS).")


class ProductInfoPricesBlockV5(OzonBaseModel):
    """Блок цен /v5/product/info/prices"""

    currency_code: str | None = Field(default=None, description="Код валюты.")
    price: float | None = Field(default=None, description="Текущая цена.")
    old_price: float | None = Field(default=None, description="Цена до скидки.")
    marketing_price: float | None = Field(default=None, description="Цена с учётом акций Ozon.")
    marketing_seller_price: float | None = Field(
        default=None, description="Цена с учётом акций Ozon после соинвестирования продавца."
    )
    min_price: float | None = Field(default=None, description="Минимальная цена.")
    retail_price: float | None = Field(default=None, description="Розничная цена.")
    auto_action_enabled: bool | None = Field(
        default=None, description="Автоприменение стратегии автодействий."
    )
    vat: float | None = Field(default=None, description="Ставка НДС.")


class ProductInfoPricesItemV5(OzonBaseModel):
    """Элемент ответа /v5/product/info/prices"""

    product_id: int | None = Field(default=None, description="Идентификатор товара.")
    offer_id: str | None = Field(default=None, description="Артикул продавца.")
    acquiring: float | None = Field(default=None, description="Комиссия за эквайринг, %.")
    commissions: ProductInfoPricesCommissionsV5 | None = Field(
        default=None, description="Комиссии и логистические тарифы."
    )
    price: ProductInfoPricesBlockV5 | None = Field(default=None, description="Блок цен.")
    volume_weight: float | None = Field(default=None, description="Объёмный вес, литры.")


class ProductInfoPricesV5Response(OzonBaseModel):
    """Ответ POST /v5/product/info/prices"""

    cursor: str | None = Field(default=None, description="Курсор для следующей страницы.")
    items: list[ProductInfoPricesItemV5] = Field(default_factory=list, description="Список товаров.")
    total: int | None = Field(default=None, description="Общее количество товаров.")


class WarehouseFirstMileType(OzonBaseModel):
    """Тип первой мили склада"""

    dropoff_point_id: str | None = Field(default=None, description="ID точки DropOff.")
    dropoff_timeslot_id: int | None = Field(default=None, description="ID таймслота DropOff.")
    first_mile_is_changing: bool | None = Field(default=None, description="Обновляются настройки.")
    first_mile_type: str | None = Field(default=None, description="Тип первой мили.")


class Warehouse(OzonBaseModel):
    """Склад (/v2/warehouse/list)"""

    has_entrusted_acceptance: bool | None = Field(default=None, description="Доверенный приём.")
    is_rfbs: bool | None = Field(default=None, description="Работает по rFBS.")
    name: str | None = Field(default=None, description="Название склада.")
    warehouse_id: int | None = Field(default=None, description="ID склада.")
    can_print_act_in_advance: bool | None = Field(default=None, description="Можно печатать акт заранее.")
    first_mile_type: WarehouseFirstMileType | None = Field(default=None, description="Первая миля.")
    has_postings_limit: bool | None = Field(default=None, description="Есть лимит на поставки.")
    is_karantin: bool | None = Field(default=None, description="Склад на карантине.")
    is_kgt: bool | None = Field(default=None, description="Принимает КГТ.")
    is_timetable_editable: bool | None = Field(default=None, description="Расписание редактируемо.")
    min_postings_limit: int | None = Field(default=None, description="Минимальный лимит поставок.")
    postings_limit: int | None = Field(default=None, description="Лимит поставок.")
    min_working_days: int | None = Field(default=None, description="Минимальное количество рабочих дней.")
    status: str | None = Field(default=None, description="Статус склада.")
    working_days: list[str] = Field(default_factory=list, description="Рабочие дни.")


class WarehouseListResponse(OzonBaseModel):
    """Ответ POST /v2/warehouse/list"""

    result: list[Warehouse] = Field(default_factory=list, description="Список складов.")
