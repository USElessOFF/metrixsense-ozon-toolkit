"""Перечисления Performance API (на основе swagger_performance.json v2.0)"""

from __future__ import annotations

from enum import StrEnum


class AdvObjectType(StrEnum):
    """
    Тип рекламируемой кампании (advObjectType).
    SKU = Трафареты / Вывод в топ
    BANNER = Баннерная рекламная кампания
    SEARCH_PROMO = Продвижение в поиске
    """

    SKU = "SKU"
    BANNER = "BANNER"
    SEARCH_PROMO = "SEARCH_PROMO"
    ALL_SKU_PROMO = "ALL_SKU_PROMO" # TODO


class CampaignPaymentType(StrEnum):
    """
    Тип оплаты кампании (paymentType).
    CPO = за заказы
    CPC = за клики
    CPM = за показы
    """

    INVALID = "CAMPAIGN_TYPE_INVALID"
    CPO = "CPO"
    CPC = "CPC"
    CPM = "CPM"


class CampaignState(StrEnum):
    """Состояние рекламной кампании"""

    UNKNOWN = "CAMPAIGN_STATE_UNKNOWN"
    RUNNING = "CAMPAIGN_STATE_RUNNING"
    PLANNED = "CAMPAIGN_STATE_PLANNED"
    STOPPED = "CAMPAIGN_STATE_STOPPED"
    INACTIVE = "CAMPAIGN_STATE_INACTIVE"
    ARCHIVED = "CAMPAIGN_STATE_ARCHIVED"
    MODERATION_DRAFT = "CAMPAIGN_STATE_MODERATION_DRAFT"
    MODERATION_IN_PROGRESS = "CAMPAIGN_STATE_MODERATION_IN_PROGRESS"
    MODERATION_FAILED = "CAMPAIGN_STATE_MODERATION_FAILED"
    FINISHED = "CAMPAIGN_STATE_FINISHED"


class CampaignPlacement(StrEnum):
    """Место размещения продвигаемых товаров"""

    INVALID = "PLACEMENT_INVALID"
    PDP = "PLACEMENT_PDP"
    SEARCH_AND_CATEGORY = "PLACEMENT_SEARCH_AND_CATEGORY"
    TOP_PROMOTION = "PLACEMENT_TOP_PROMOTION"
    TAKEOVER = "PLACEMENT_TAKEOVER"


class ProductAutopilotStrategy(StrEnum):
    """Автостратегия кампании (productAutopilotStrategy)"""

    MAX_VIEWS = "MAX_VIEWS"
    MAX_CLICKS = "MAX_CLICKS"
    TOP_MAX_CLICKS = "TOP_MAX_CLICKS"
    NO_AUTO_STRATEGY = "NO_AUTO_STRATEGY"
    TAKEOVER = "TAKEOVER"
    TARGET_BIDS = "TARGET_BIDS" # TODO


class ProductCampaignMode(StrEnum):
    """Режим управления товарной кампанией"""

    AUTO = "PRODUCT_CAMPAIGN_MODE_AUTO"
    MANUAL = "PRODUCT_CAMPAIGN_MODE_MANUAL"


class SkuAddMode(StrEnum):
    """Стратегия добавления товаров в кампанию с автостратегией MAX_VIEWS"""

    UNKNOWN = "PRODUCT_CAMPAIGN_SKU_ADD_MODE_UNKNOWN"
    MANUAL = "PRODUCT_CAMPAIGN_SKU_ADD_MODE_MANUAL"
    AUTO = "PRODUCT_CAMPAIGN_SKU_ADD_MODE_AUTO"


class StatisticsGroupBy(StrEnum):
    """Группировка отчёта по времени (groupBy)"""

    NO_GROUP_BY = "NO_GROUP_BY"
    DATE = "DATE"
    START_OF_WEEK = "START_OF_WEEK"
    START_OF_MONTH = "START_OF_MONTH"


class StatisticsRequestState(StrEnum):
    """Состояние асинхронного запроса на формирование отчёта"""

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    ERROR = "ERROR"
    OK = "OK"


class ReportKind(StrEnum):
    """
    Тип запрашиваемого отчёта (kind).
    STATS = отчёт по кампании;
    SEARCH_PHRASES = отчёт по поисковым фразам и по категории товаров;
    ATTRIBUTION = отчёт по заказам для продвижения в поиске;
    VIDEO = отчёт по показам видеобаннера.
    """

    STATS = "STATS"
    SEARCH_PHRASES = "SEARCH_PHRASES"
    ATTRIBUTION = "ATTRIBUTION"
    VIDEO = "VIDEO"
    SEARCH_PROMO_ORGANISATION_ORDERS = "SEARCH_PROMO_ORGANISATION_ORDERS"
    SEARCH_PROMO_ORGANISATION_PRODUCTS = "SEARCH_PROMO_ORGANISATION_PRODUCTS"


class Role(StrEnum):
    """Роль кабинета в отчётах по внешнему трафику (доступ)"""

    MAIN = "MAIN"
    SUB = "SUB"


class CampaignTypeRate(StrEnum):
    """Тип минимальной ставки по инструменту продвижения"""

    CPO = "CTYPE_CPO"
    CPC = "CTYPE_CPC"
    CPM = "CTYPE_CPM"


class PaymentTypeRate(StrEnum):
    """
    Тип минимальной ставки (минимальные ставки по SKU).
    PAYMENT_TYPE_CPO = Продвижение в поиске
    PAYMENT_TYPE_CPC = Трафареты
    PAYMENT_TYPE_CPC_TOP = Вывод в топ
    
    """

    PAYMENT_TYPE_CPO = "PAYMENT_TYPE_CPO"
    PAYMENT_TYPE_CPC = "PAYMENT_TYPE_CPC"
    PAYMENT_TYPE_CPC_TOP = "PAYMENT_TYPE_CPC_TOP"


class MarketplaceID(StrEnum):
    """Операционная система площадки (marketplaceId)"""

    RU = "MARKETPLACE_ID_RU"
    BY = "MARKETPLACE_ID_BY"


class ReportFileState(StrEnum):
    """Статус файла импорта CSV (финансовые/товарные отчёты инструмента)"""

    IN_ANALYSIS = "IN_ANALYSIS"
    IN_PROGRESS = "IN_PROGRESS"
    ERROR = "ERROR"
    OK = "OK"
