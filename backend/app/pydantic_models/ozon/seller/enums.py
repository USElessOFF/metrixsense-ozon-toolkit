"""Перечисления Seller API"""

from __future__ import annotations

from enum import StrEnum


class AnalyticsDimension(StrEnum):
    """Группировка данных в аналитическом отчёте (/v1/analytics/data).

    Базовые (доступны всем): ``sku``, ``spu``, ``day``, ``week``, ``month``.
    Premium: ``year``, ``category1-4``, ``brand``, ``modelID``.
    """

    UNKNOWN = "unknownDimension"
    SKU = "sku"
    SPU = "spu"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    CATEGORY1 = "category1"
    CATEGORY2 = "category2"
    CATEGORY3 = "category3"
    CATEGORY4 = "category4"
    BRAND = "brand"
    MODEL_ID = "modelID"


class AnalyticsMetric(StrEnum):
    """Метрики аналитики (/v1/analytics/data).
    Cписок метриĸ, по ĸоторым будет сформирован отчёт.
    Метрики, доступные всем продавцам:
    - `revenue` — заказано на сумму,
    - `ordered_units` — заказано товаров.
        
    Метрики, доступные только продавцам с Premium-подпиской:
    - `unknown_metric` — неизвестная метрика.
    - `hits_view_search` — показы в поиске и в категории.
    - `hits_view_pdp` — показы на карточке товара.
    - `hits_view` — всего показов.
    - `hits_tocart_search` — в корзину из поиска или категории.
    - `hits_tocart_pdp` — в корзину из карточки товара.
    - `hits_tocart` — всего добавлено в корзину.
    - `session_view_search` — сессии с показом в поиске или в каталоге. Считаются уникальные посетители с просмотром в поиске или каталоге.
    - `session_view_pdp` — сессии с показом на карточке товара. Считаются уникальные посетители, которые просмотрели карточку товара.
    - `session_view` — всего сессий. Считаются уникальные посетители.
    - `conv_tocart_search` — конверсия в корзину из поиска или категории.
    - `conv_tocart_pdp` — конверсия в корзину из карточки товара.
    - `conv_tocart` — общая конверсия в корзину.
    - `returns` — возвращено товаров.
    - `cancellations` — отменено товаров.
    - `delivered_units` — доставлено товаров.
    - `position_category` — позиция в поиске и категории."

    """

    UNKNOWN = "unknown_metric"
    REVENUE = "revenue"
    ORDERED_UNITS = "ordered_units"
    HITS_VIEW_SEARCH = "hits_view_search"
    HITS_VIEW_PDP = "hits_view_pdp"
    HITS_VIEW = "hits_view"
    HITS_TOCART_SEARCH = "hits_tocart_search"
    HITS_TOCART_PDP = "hits_tocart_pdp"
    HITS_TOCART = "hits_tocart"
    SESSION_VIEW_SEARCH = "session_view_search"
    SESSION_VIEW_PDP = "session_view_pdp"
    SESSION_VIEW = "session_view"
    CONV_TOCART_SEARCH = "conv_tocart_search"
    CONV_TOCART_PDP = "conv_tocart_pdp"
    CONV_TOCART = "conv_tocart"
    #ADV_VIEW_PDP = "adv_view_pdp"
    #ADV_VIEW_SEARCH = "adv_view_search"
    #ADV_VIEW_ALL = "adv_view_all"
    RETURNS = "returns"
    CANCELLATIONS = "cancellations"
    DELIVERED_UNITS = "delivered_units"
    POSITION_CATEGORY = "position_category"


class AnalyticsFilterOp(StrEnum):
    """Операция сравнения в аналитическом фильтре"""

    EQ = "EQ"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"


class AnalyticsSortOrder(StrEnum):
    """Направление сортировки аналитики"""

    ASC = "ASC"
    DESC = "DESC"


class Visibility(StrEnum):
    """Фильтр по видимости товара (/v3/product/list)"""

    ALL = "ALL"
    VISIBLE = "VISIBLE"
    INVISIBLE = "INVISIBLE"
    EMPTY_STOCK = "EMPTY_STOCK"
    NOT_MODERATED = "NOT_MODERATED"
    MODERATED = "MODERATED"
    DISABLED = "DISABLED"
    STATE_FAILED = "STATE_FAILED"
    READY_TO_SUPPLY = "READY_TO_SUPPLY"
    VALIDATION_STATE_PENDING = "VALIDATION_STATE_PENDING"
    VALIDATION_STATE_FAIL = "VALIDATION_STATE_FAIL"
    VALIDATION_STATE_SUCCESS = "VALIDATION_STATE_SUCCESS"
    TO_SUPPLY = "TO_SUPPLY"
    IN_SALE = "IN_SALE"
    REMOVED_FROM_SALE = "REMOVED_FROM_SALE"
    OVERPRICED = "OVERPRICED"
    CRITICALLY_OVERPRICED = "CRITICALLY_OVERPRICED"
    EMPTY_BARCODE = "EMPTY_BARCODE"
    BARCODE_EXISTS = "BARCODE_EXISTS"
    QUARANTINE = "QUARANTINE"
    ARCHIVED = "ARCHIVED"
    OVERPRICED_WITH_STOCK = "OVERPRICED_WITH_STOCK"
    PARTIAL_APPROVED = "PARTIAL_APPROVED"


class ItemTag(StrEnum):
    """Тег товара в аналитике остатков"""

    ITEM_ATTRIBUTE_NONE = "ITEM_ATTRIBUTE_NONE"
    ECONOM = "ECONOM"
    NOVEL = "NOVEL"
    DISCOUNT = "DISCOUNT"
    FBS_RETURN = "FBS_RETURN"
    SUPER = "SUPER"
    MARKABLE = "MARKABLE"
    UNSPECIFIED = "UNSPECIFIED"


class TurnoverGrade(StrEnum):
    """Статус ликвидности товара (оборачиваемость остатков)"""

    TURNOVER_GRADE_NONE = "TURNOVER_GRADE_NONE"
    DEFICIT = "DEFICIT"
    POPULAR = "POPULAR"
    ACTUAL = "ACTUAL"
    SURPLUS = "SURPLUS"
    WAS_NO_SALES = "WAS_NO_SALES"
    COLLECTING_DATA = "COLLECTING_DATA"
    WAITING_FOR_SUPPLY = "WAITING_FOR_SUPPLY"
    WAS_DEFICIT = "WAS_DEFICIT"
    WAS_POPULAR = "WAS_POPULAR"
    WAS_ACTUAL = "WAS_ACTUAL"
    WAS_SURPLUS = "WAS_SURPLUS"
    # Значение реально приходит от /v1/analytics/stocks (лог 2026-08-29,
    # SKU 1709707935), хотя в swagger его нет.
    NO_SALES = "NO_SALES"


class RatingType(StrEnum):
    """Системные названия рейтингов продавца (/v1/rating/history)"""

    ON_TIME = "rating_on_time"
    REVIEW_AVG_SCORE_TOTAL = "rating_review_avg_score_total"
    PRICE = "rating_price"
    ORDER_CANCELLATION = "rating_order_cancellation"
    SHIPMENT_DELAY = "rating_shipment_delay"
    SSL = "rating_ssl"
    ON_TIME_SUPPLY_DELIVERY = "rating_on_time_supply_delivery"
    ORDER_ACCURACY = "rating_order_accuracy"
    ON_TIME_SUPPLY_CANCELLATION = "rating_on_time_supply_cancellation"
    REACTION_TIME = "rating_reaction_time"
    AVERAGE_RESPONSE_TIME = "rating_average_response_time"
    REPLIED_DIALOGS_RATIO = "rating_replied_dialogs_ratio"


class PostingStatusFBS(StrEnum):
    """Статус отправления FBS"""

    AWAITING_REGISTRATION = "awaiting_registration"
    ACCEPTANCE_IN_PROGRESS = "acceptance_in_progress"
    AWAITING_APPROVE = "awaiting_approve"
    AWAITING_PACKAGING = "awaiting_packaging"
    AWAITING_DELIVER = "awaiting_deliver"
    ARBITRATION = "arbitration"
    CLIENT_ARBITRATION = "client_arbitration"
    DELIVERING = "delivering"
    DRIVER_PICKUP = "driver_pickup"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    NOT_ACCEPTED = "not_accepted"
    SENT_BY_SELLER = "sent_by_seller"


class PostingStatusFBO(StrEnum):
    """Статус отправления FBO"""

    AWAITING_PACKAGING = "awaiting_packaging"
    AWAITING_DELIVER = "awaiting_deliver"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ProductQueriesSortBy(StrEnum):
    """Поле сортировки аналитики поисковых запросов (/v1/analytics/product-queries)"""

    DEFAULT = "DEFAULT"
    GMV = "GMV"
    UNIQUE_SEARCH_USERS = "UNIQUE_SEARCH_USERS"
    UNIQUE_VIEW_USERS = "UNIQUE_VIEW_USERS"
    VIEW_CONVERSION = "VIEW_CONVERSION"
    POSITION = "POSITION"


class ProductQueriesSortDir(StrEnum):
    """Направление сортировки аналитики поисковых запросов"""

    ASC = "ASC"
    DESC = "DESC"


class TurnoverGradeExtended(StrEnum):
    """Оценка оборачиваемости (/v1/analytics/turnover/stocks)"""

    GRADES_NONE = "GRADES_NONE"
    GRADES_NOSALES = "GRADES_NOSALES"
    GRADES_GREEN = "GRADES_GREEN"
    GRADES_YELLOW = "GRADES_YELLOW"
    GRADES_RED = "GRADES_RED"
    GRADES_CRITICAL = "GRADES_CRITICAL"

class ReviewSortDir(StrEnum):
    """Направление сортировки отзывов (/v1/review/list)"""

    ASC = "ASC"
    DESC = "DESC"


class ReviewStatus(StrEnum):
    """Статус отзыва (/v1/review/list)"""

    ALL = "ALL"
    UNPROCESSED = "UNPROCESSED"
    PROCESSED = "PROCESSED"


class FbpFilter(StrEnum):
    """Фильтр FBP-поставок (/v3/posting/fbs/list)"""

    ALL = "ALL"
    ONLY = "ONLY"
    WITHOUT = "WITHOUT"


class PostingSortDir(StrEnum):
    """Направление сортировки поставок FBS"""

    ASC = "asc"
    DESC = "desc"


class WarehouseStatus(StrEnum):
    """Статус склада (/v2/warehouse/list)"""

    NEW = "new"
    CREATED = "created"
    DISABLED = "disabled"
    BLOCKED = "blocked"
    DISABLED_DUE_TO_LIMIT = "disabled_due_to_limit"
    ERROR = "error"


class StockShipmentType(StrEnum):
    """Тип отгрузки остатков (/v4/product/info/stocks)"""

    GENERAL = "SHIPMENT_TYPE_GENERAL"
    BOX = "SHIPMENT_TYPE_BOX"
    PALLET = "SHIPMENT_TYPE_PALLET"


class SellerReportType(StrEnum):
    """Тип отчёта Seller API (/v2/report/.../create)"""

    SELLER_PRODUCTS = "SELLER_PRODUCTS"
    SELLER_TRANSACTIONS = "SELLER_TRANSACTIONS"
    SELLER_PRODUCT_PRICES = "SELLER_PRODUCT_PRICES"
    SELLER_STOCK = "SELLER_STOCK"
    SELLER_RETURNS = "SELLER_RETURNS"
    SELLER_POSTINGS = "SELLER_POSTINGS"
    SELLER_FINANCE = "SELLER_FINANCE"
    SELLER_PRODUCT_DISCOUNTED = "SELLER_PRODUCT_DISCOUNTED"
    DOCUMENT_B2B_SALES = "DOCUMENT_B2B_SALES"
    MUTUAL_SETTLEMENT = "MUTUAL_SETTLEMENT"
    COMPENSATION = "COMPENSATION"
    DECOMPENSATION = "DECOMPENSATION"


class SellerReportStatus(StrEnum):
    """Статус формирования отчёта Seller API"""

    WAITING = "waiting"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class TransactionType(StrEnum):
    """Тип транзакции в финансовых операциях (/v3/finance/transaction/list)"""

    ALL = "all"
    OPERATION = "operation"
    NON_OPERATION = "non_operation"
    ORDER = "order"
