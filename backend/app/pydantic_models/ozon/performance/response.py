"""Модели ответов Performance API (на основе swagger_performance.json v2.0)"""

from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field

from backend.app.pydantic_models.ozon.commons import OzonBaseModel
from backend.app.pydantic_models.ozon.performance.request import StatisticsRequest

from .enums import (
    AdvObjectType,
    CampaignPaymentType,
    CampaignPlacement,
    CampaignState,
    CampaignTypeRate,
    MarketplaceID,
    ProductAutopilotStrategy,
    ProductCampaignMode,
    ReportKind,
    Role,
    SkuAddMode,
    StatisticsRequestState,
)


def _micro_rubles_to_rubles(value: str | None) -> Decimal | None:
    """Конвертация миллионных долей рубля в рубли (Decimal с 2 знаками)"""
    if value is None or value == "":
        return None
    return (Decimal(value) / Decimal(1_000_000)).quantize(Decimal("0.01"))

    
class CampaignAutoIncrease(OzonBaseModel):
    """Информация об автоподнятии бюджета"""

    auto_increase_percent: float | None = Field(default=None, alias="autoIncreasePercent")
    auto_increased_budget: str | None = Field(default=None, alias="autoIncreasedBudget")
    is_auto_increased: bool | None = Field(default=None, alias="isAutoIncreased")
    recommended_auto_increase_percent: float | None = Field(
        default=None, alias="recommendedAutoIncreasePercent"
    )


class CampaignAutopilotProperties(OzonBaseModel):
    """Свойства автостратегии кампании"""

    category_id: str | None = Field(default=None, alias="categoryId")
    sku_add_mode: SkuAddMode | None = Field(default=None, alias="skuAddMode")


class Campaign(OzonBaseModel):
    """Рекламная кампания (элемент списка GET /api/client/campaign)"""

    id: str = Field(..., description="Идентификатор кампании.")
    payment_type: CampaignPaymentType = Field(
        default=CampaignPaymentType.INVALID,
        alias="paymentType",
        description="Тип оплаты: CPC — за клики, CPM — за показы, CPO — за заказы.",
    )
    title: str | None = Field(default=None, description="Название кампании.")
    state: CampaignState = Field(
        default=CampaignState.UNKNOWN,
        description="Состояние кампании.",
    )
    adv_object_type: AdvObjectType | None = Field(
        default=None,
        alias="advObjectType",
        description="Тип рекламируемой кампании.",
    )
    from_date: str | None = Field(default=None, alias="fromDate")
    to_date: str | None = Field(default=None, alias="toDate")
    budget: str | None = Field(
        default=None,
        description="Бюджет кампании в миллионных долях рубля.",
    )
    daily_budget: str | None = Field(
        default=None,
        alias="dailyBudget",
        description="Дневной бюджет в миллионных долях рубля.",
    )
    weekly_budget: str | None = Field(
        default=None,
        alias="weeklyBudget",
        description="Недельный бюджет в миллионных долях рубля.",
    )
    placement: CampaignPlacement | list[CampaignPlacement] | None = Field(
        default=None,
        description="Место размещения продвигаемых товаров.",
    )
    product_autopilot_strategy: ProductAutopilotStrategy | None = Field(
        default=None,
        alias="productAutopilotStrategy",
        description="Автостратегия, используемая кампанией.",
    )
    autopilot: CampaignAutopilotProperties | None = None
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    product_campaign_mode: ProductCampaignMode | None = Field(
        default=None,
        alias="productCampaignMode",
        description="Режим управления товарной кампанией.",
    )
    auto_increase: CampaignAutoIncrease | None = Field(default=None, alias="autoIncrease")

    @property
    def budget_rubles(self) -> Decimal | None:
        """Бюджет в рублях"""
        return _micro_rubles_to_rubles(self.budget)

    @property
    def daily_budget_rubles(self) -> Decimal | None:
        """Дневной бюджет в рублях"""
        return _micro_rubles_to_rubles(self.daily_budget)

    @property
    def weekly_budget_rubles(self) -> Decimal | None:
        """Недельный бюджет в рублях"""
        return _micro_rubles_to_rubles(self.weekly_budget)


class CampaignsList(OzonBaseModel):
    """GET /api/client/campaign — список рекламных кампаний"""

    list_campaign: list[Campaign] = Field(..., description="Список кампаний.", alias="list")


class CampaignObjectsListObject(OzonBaseModel):
    """Объект продвижения в кампании"""

    id: str | None = None
    icon: str | None = None

class CampaignObjectsList(OzonBaseModel):
    """GET /api/client/campaign/{campaignId}/objects — объекты кампании"""

    list_campaign: list[CampaignObjectsListObject] = Field(..., alias="list")


class InstrumentLimitProperties(OzonBaseModel):
    """Свойства лимита по инструменту продвижения"""

    daily_budget_from: str | None = Field(default=None, alias="dailyBudgetFrom")
    rate_from: Decimal | None = Field(default=None, alias="rateFrom")
    budget_from: str | None = Field(default=None, alias="budgetFrom")


class InstrumentLimit(OzonBaseModel):
    """Лимиты ставок и бюджета по инструменту"""

    ctype: CampaignTypeRate | None = None
    description: str | None = None
    title: str | None = None
    payment_type: CampaignPaymentType | None = Field(default=None, alias="paymentType")
    properties: InstrumentLimitProperties = Field(default_factory=InstrumentLimitProperties)


class InstrumentLimits(OzonBaseModel):
    """Лимиты по инструменту для конкретной площадки"""

    id: MarketplaceID = Field(..., description="Площадка (RU/BY).")
    min_limits: list[InstrumentLimit] = Field(default_factory=list[InstrumentLimit], alias="minLimits")


class ListLimitsResponse(OzonBaseModel):
    """GET /api/client/limits/list — лимиты ставок и бюджетов"""

    instrument_limits: list[InstrumentLimits] = Field(
        default_factory=list[InstrumentLimits], alias="instrumentLimits",
        description="Лимиты по инструментам продвижения по каждой площадке.",
    )


class BidBySKURateResponseCell(OzonBaseModel):
    """Минимальная ставка по конкретному SKU"""

    sku: str | None = Field(default=None, description="SKU товара.")
    type: str | None = Field(default=None, description="Тип минимальной ставки.")
    rate: Decimal | None = Field(default=None, description="Значение ставки в рублях.")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class BidBySKURates(OzonBaseModel):
    """Ставки по SKU по типу оплаты"""

    payment_type: CampaignPaymentType | None = Field(default=None, alias="paymentType")
    rates: list[BidBySKURateResponseCell] = Field(default_factory=list[BidBySKURateResponseCell])


class BidBySKUResponse(OzonBaseModel):
    """POST /api/client/min/sku — минимальные ставки для всех инструментов"""

    model_config = ConfigDict(populate_by_name=True)

    marketplace_id: MarketplaceID | None = Field(default=None, alias="marketplaceId")
    min_rates: list[BidBySKURates] = Field(default_factory=list[BidBySKURates], alias="minRates") 


class StatisticsRequestID(OzonBaseModel):
    """Идентификатор запроса на формирование отчёта (submit → poll)"""

    model_config = ConfigDict(populate_by_name=True)

    uuid: str | None = Field(
        default=None,
        alias="UUID",
        description="Уникальный идентификатор отправленного запроса.",
    )
    vendor: bool | None = Field(
        default=None,
        description="`true` — отчёт с аналитикой внешнего трафика.",
    )


class StatisticsReport(OzonBaseModel):
    """Содержимое сформированного отчёта / ссылка на него"""

    content_type: str | None = Field(default=None, alias="contentType")
    content: bytes | None = None
    report_id: str | None = Field(default=None, alias="reportId")
    code: str | None = None
    link: str | None = None


class StatisticsRequestInfo(OzonBaseModel):
    """Параметры исходного запроса отчёта"""

    campaigns: list[str] | None = None
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    date_from: str | None = Field(default=None, alias="dateFrom")
    date_to: str | None = Field(default=None, alias="dateTo")


class StatisticsReportsListItemCampaign(OzonBaseModel):
    """Кампания в элементе списка отчётов"""

    id: str | None = None
    icon: str | None = None
    state: CampaignState | None = None
    title: str | None = None
    type: str | None = None


class StatisticsReportsListItem(OzonBaseModel):
    """Элемент списка отчётов по статистике"""

    uuid: str | None = Field(default=None, alias="UUID")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    state: StatisticsRequestState | None = None
    request: StatisticsRequestInfo | None = None
    error: str | None = None
    link: str | None = None
    kind: str | None = None
    sub_kind: str | None = Field(default=None, alias="subKind")
    campaigns: list[StatisticsReportsListItemCampaign] = Field(default_factory=list[StatisticsReportsListItemCampaign]) 
    generate_by_template: str | None = Field(default=None, alias="generateByTemplate")


class StatisticsReportsList(OzonBaseModel):
    """GET /api/client/statistics/list — список запрошенных отчётов"""

    items: list[StatisticsReportsListItem] | None = Field(default_factory=list[StatisticsReportsListItem])
    total: str | None = Field(default=None, description="Количество отчётов.")


class TokenResponse(OzonBaseModel):
    """POST /api/client/token — OAuth2 токен доступа"""

    access_token: str = Field(..., description="Токен доступа (Bearer).")
    access_token2: str | None = Field(default=None, alias="accessToken2")
    expires_in: int = Field(default=1800, description="Время жизни токена в секундах.")
    token_type: str = Field(default="Bearer", description="Тип токена в формате JWT.")
    role: Role | None = Field(default=None, description="Роль кабинета.")


class ErrorResponse(OzonBaseModel):
    """Стандартная ошибка Performance API"""

    code: int | None = None
    detail: str | None = None
    message: str | None = None
    trace_id: str | None = Field(default=None, alias="traceId")
    
    @property
    def text(self) -> str:
        """Читаемое представление ошибки"""
        return self.message or self.detail or f"HTTP {self.code}" if self.code else "Unknown error"


class StatisticsResponse(OzonBaseModel):
    """
    GET /api/client/statistics/{UUID} — статус формирования отчёта.
    """

    uuid: str | None = Field(
        alias='UUID', 
        description='Уникальный идентификатор запроса, для которого производилась проверка.',
        default=None
    )

    state: StatisticsRequestState = Field(default=StatisticsRequestState.NOT_STARTED)
    created_at: datetime | None = Field(
            alias='createdAt',
            description='Дата и время получения запроса сервером, часовой пояс UTC.',
            default=None
    )
    updated_at: datetime | None = Field(
            alias='updatedAt',
            description='Дата и время последнего обновления состояния запроса, часовой пояс UTC.',
            default=None
    )
    request: StatisticsRequest | None = Field(default=None)
    error: str | None = Field(
            description='Краткое описание возникшей ошибки.\n\nПоле присутствует, если выполнение запроса завершилось '
                        'ошибкой.\n',
            default=None
    )
    link: str | None = Field(
            description='Относительная ссылка на отчёт в формате CSV.\n\nПоле присутствует, если запрос выполнен '
                        'успешно.\n',
            default=None
    )
    kind: ReportKind | None = Field(
            description='Тип запрашиваемого отчёта:\n- `STATS` — отчёт по кампании;\n- `SEARCH_PHRASES` — отчёт по '
                        'поисковым фразам и по категории товаров;\n- `ATTRIBUTION` — отчёт по заказам для продвижения '
                        'в поиске;\n- `VIDEO` — отчёт по показам видеобаннера.\n',
            default=ReportKind.STATS
    )
    
class VendorStatisticsResponse(StatisticsResponse):
    """Статус отчёта по внешнему трафику (аналогичен обычному)"""
