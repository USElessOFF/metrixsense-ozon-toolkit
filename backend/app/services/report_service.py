"""Сервис формирования отчётов"""

from __future__ import annotations

import asyncio
import hashlib
import math
import io
import json
from datetime import datetime, timedelta, timezone
from os import makedirs
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd
import structlog
from numpy import nan
from pydantic import BaseModel, ValidationError

from backend.app import config
from backend.app.config import settings
from backend.app.adapters.metrix_adapter import MetrixAdapter
from backend.app.database import get_async_context_session
from backend.app.exceptions import OzonAPIError, SettingsError
from backend.app.get_bg_tasks import background_tasks
from backend.app.models.ozon_secrets import OzonSecrets
from backend.app.models.report_request import (
    ReportRequestOzon,
    ReportStatus,
    ReportType,
)
from backend.app.ozon_performance import OzonPerformanceClient
from backend.app.ozon_seller import OzonSellerClient
from backend.app.pandas_utils import PandasUtil
from backend.app.pydantic_models.ozon.performance.enums import (
    AdvObjectType,
    CampaignState,
)
from backend.app.pydantic_models.ozon.performance.request import (
    CampaignQueryParams,
    DailyStatsQueryParams,
    StatisticsRequest,
)
from backend.app.pydantic_models.ozon.performance.response import Campaign
from backend.app.pydantic_models.ozon.seller.enums import TransactionType
from backend.app.pydantic_models.ozon.seller.request import (
    TurnoverStocksRequest,
    ProductQueriesRequest,
    AnalyticsStocksRequest,
    FinanceTransactionDateFilter,
    FinanceTransactionListFilter,
    FinanceTransactionListRequest,
    FinanceTransactionTotalsRequest,
    ProductInfoListRequest,
    ProductInfoPricesV5Request,
    ProductInfoStocksRequest,
)
from backend.app.pydantic_models.ozon.seller.response import (
    AnalyticsStocksResponse,
    FinanceOperation,
)
from backend.app.pydantic_models.report_cols_enum import ColumnsFullReport
from backend.app.pydantic_models.report_sections import (
    FinanceExpenseRow,
    FinanceExpensesSectionResponse,
    PricesCommissionsRow,
    PricesCommissionsSectionResponse,
    ProductCardRow,
    ProductCardsSectionResponse,
    SellerRatingRow,
    SellerRatingSectionResponse,
    CashFlowRow,
    CashFlowSectionResponse,
    PlanSummary,
    SearchQueryRow,
    SearchQueriesSectionResponse,
    StockPlanningRow,
    StockPlanningSectionResponse,
    StockWarehouseRow,
)
from backend.app.tax import INCOME_MINUS_EXPENSE_SYSTEMS, get_tax_rate

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

DATE_FORMAT = "%Y-%m-%d"
MAX_DATE_RANGE_DAYS = 31
MAX_BACK_DAYS = 90

# Только числовые фоллбэки; налог валидируется в app.tax
COST_PRICE_SHARE = 0.5
DEFAULT_LOGISTICS_COST = 150.0

# Размер батча SKU для /v3/product/info/list (лимит Ozon)
PRODUCT_INFO_BATCH_SIZE = 1000
# Защитный предел страниц /v3/finance/transaction/list
FINANCE_MAX_PAGES = 100
# Порог крупногабарита Ozon: сторона упаковки больше 500 мм → иная тарифная зона
OVERSIZE_SIDE_MM = 500

# Ozon закрыл детальную финансовую выписку v3 (400, code 9 «obsolete method
# cannot be used») — секции «Начисления» и «ДДС» дают человеку понятную ошибку
# вместо голого Client error 400. Замена появится после обновления API.
_FINANCE_OBSOLETE_MARKER = "obsolete method cannot be used"
_FINANCE_UNAVAILABLE_MESSAGE = (
    "Финансовая выписка недоступна: Ozon закрыл метод /v3/finance/transaction (obsolete). "
    "Секции «Начисления» и «ДДС» временно не работают — ожидайте обновление интеграции."
)


def _finance_method_closed(e: Exception) -> bool:
    return _FINANCE_OBSOLETE_MARKER in str(e)


class ReportService:
    """Сервис создания и компиляции аналитических отчётов Ozon"""

    def __init__(self, adapter: MetrixAdapter):
        self.adapter = adapter
        self.pd_util: PandasUtil = PandasUtil()
        self.readable_column_mapping = {
            "sku": "ID Товара",
            "Название товара": "Наименование",
        }
        self.readable_compaign_type = {
            "SKU": "Трафареты/Вывод в топ",
            "BANNER": "Баннеры",
            "SEARCH_PROMO": "Продвижение в поиске",
        }
        self.ctr_c_name = "CTR,% ({})"

    async def create_report_full_report(self, date_from: str, date_to: str) -> ReportRequestOzon:
        """Валидация дат/секретов, создание запроса, фоновая компиляция"""
        secrets = await self.adapter.get_secrets()
        if secrets is None:
            logger.info(f"Unable get secrets for user: {self.adapter.user_id}")
            raise OzonAPIError("Unable to get your Ozon secrets. Please configure them first")

        has_seller = bool(secrets.seller_api_key and secrets.seller_client_id)
        has_premium = bool(secrets.performance_client_id and secrets.performance_secret)

        if not has_seller:
            logger.info(f"User {self.adapter.user_id} has no seller secrets")
            raise OzonAPIError("Seller API secrets are required for report generation")

        if not has_premium:
            logger.info(
                f"User {self.adapter.user_id} has no Premium (Performance) secrets - "
                "report will include only Seller data"
            )

        # Незаданный налог → SettingsError сразу (422), не фоновый FAILED
        user_settings = await self.adapter.get_settings()
        get_tax_rate(user_settings.tax_system)

        from_dt = datetime.strptime(date_from, DATE_FORMAT).replace(tzinfo=timezone.utc)
        to_dt = datetime.strptime(date_to, DATE_FORMAT).replace(tzinfo=timezone.utc)

        self._validate_dates(from_dt, to_dt)

        report_request = await self.adapter.create_report_request(from_dt, to_dt, ReportType.FULL)
        
        report_uuid = report_request.request_uuid
        
        logger.info("Report request created", report_id=report_uuid)
        
        makedirs(f"{config.PROJECT_ROOT}/files/{report_uuid}", exist_ok=True)
        
        background_tasks.defer(self._compile_report_full_report(report_uuid, secrets, has_premium))

        return report_request

    async def get_report(self, request_uuid: str) -> ReportRequestOzon | None:
        return await self.adapter.get_report_request(request_uuid)

    async def get_latest_report(self) -> ReportRequestOzon | None:
        return await self.adapter.get_latest_report_request()

    # Секции для REST API: DI-клиент на запрос, кэш AnalyticsCache
    # Read-through с TTL - правки цен подтягиваются не позже TTL

    SECTION_CACHE_TTL = timedelta(hours=6)

    def _section_cache_key(self, section_name: str, suffix: str = "") -> str:
        """Ключ кэша секции; suffix различает вариант запроса"""
        key = f"section_{self.adapter.user_id}_{section_name}"
        return f"{key}_{suffix}" if suffix else key

    async def _get_cached_section(
        self, cache_key: str, model_cls: type[T]
    ) -> T | None:
        cached = await self.adapter.get_cache(cache_key)
        if not cached:
            return None
        try:
            return model_cls.model_validate_json(cached)
        except ValidationError as e:
            logger.warning(
                "::_get_cached_section> Cached payload is invalid, refetching",
                cache_key=cache_key,
                error=str(e),
            )
            return None

    async def _cache_section_payload(
        self,
        section_name: str,
        payload: dict[str, Any],
        *,
        cache_key: str | None = None,
        ttl: timedelta | None = None,
    ) -> None:
        """Сохранить секцию в AnalyticsCache (TTL по умолчанию)"""
        await self.adapter.set_cache(
            cache_key or self._section_cache_key(section_name),
            payload,
            ttl=ttl if ttl is not None else self.SECTION_CACHE_TTL,
        )

    async def get_prices_commissions_section(
        self, seller: OzonSellerClient
    ) -> PricesCommissionsSectionResponse:
        """Секция «Цены и комиссии» (/v5/product/info/prices)"""
        generated_at = datetime.now(tz=timezone.utc)
        cache_key = self._section_cache_key("prices_commissions")

        cached = await self._get_cached_section(cache_key, PricesCommissionsSectionResponse)
        if cached is not None:
            return cached

        resp = await seller.get_product_info_prices(ProductInfoPricesV5Request())
        rows: list[PricesCommissionsRow] = []
        for item in resp.items:
            commissions = item.commissions
            price = item.price
            rows.append(
                PricesCommissionsRow(
                    product_id=item.product_id,
                    offer_id=item.offer_id,
                    price=price.price if price else None,
                    old_price=price.old_price if price else None,
                    min_price=price.min_price if price else None,
                    marketing_price=price.marketing_price if price else None,
                    commission_fbo_percent=commissions.sales_percent_fbo if commissions else None,
                    commission_fbs_percent=commissions.sales_percent_fbs if commissions else None,
                    acquiring_percent=item.acquiring,
                    logistics_fbo_range=(
                        f"{commissions.fbo_direct_flow_trans_min_amount}–"
                        f"{commissions.fbo_direct_flow_trans_max_amount}"
                        if commissions and commissions.fbo_direct_flow_trans_min_amount is not None
                        else None
                    ),
                    logistics_fbs_first_mile_range=(
                        f"{commissions.fbs_first_mile_min_amount}–"
                        f"{commissions.fbs_first_mile_max_amount}"
                        if commissions and commissions.fbs_first_mile_min_amount is not None
                        else None
                    ),
                    delivery_fbo=(
                        commissions.fbo_deliv_to_customer_amount if commissions else None
                    ),
                    return_flow_fbo=(
                        commissions.fbo_return_flow_amount if commissions else None
                    ),
                    volume_weight_l=item.volume_weight,
                )
            )

        payload = PricesCommissionsSectionResponse(
            section="prices_commissions",
            generated_at=generated_at,
            row_count=len(rows),
            data=rows,
        )
        await self._cache_section_payload("prices_commissions", payload.model_dump(mode="json"), cache_key=cache_key)
        return payload

    async def get_product_cards_section(
        self, seller: OzonSellerClient, sku_list: list[int | str] | None = None
    ) -> ProductCardsSectionResponse:
        """Секция «Карточки товаров» (/v3/product/info/list + габариты)"""
        generated_at = datetime.now(tz=timezone.utc)
        normalized_sku = [str(sku) for sku in (sku_list or [])]
        sku_hash = hashlib.md5(",".join(normalized_sku).encode()).hexdigest()[:10] if normalized_sku else "all"
        cache_key = self._section_cache_key("product_cards", sku_hash)

        cached = await self._get_cached_section(cache_key, ProductCardsSectionResponse)
        if cached is not None:
            return cached

        if not sku_list:
            from backend.app.pydantic_models.ozon.seller.request import ProductListRequest

            catalog = await seller.get_product_list(ProductListRequest())
            sku_list = [
                int(item.sku) for item in catalog.items if item.sku is not None
            ]

        # strict=True: ошибки → 4xx/5xx, не тихий пустой 200
        cards_df = await self._collect_product_cards_data(seller, sku_list, strict=True)
        records = (
            json.loads(cards_df.replace({nan: None}).to_json(orient="records", force_ascii=False))
            if not cards_df.empty
            else []
        )

        local_dims = await self.adapter.get_product_dimensions()
        row_models: list[ProductCardRow] = []
        for record in records:
            sku = record.get(ColumnsFullReport.SKU)
            dim = local_dims.get(int(sku)) if sku is not None else None
            volume_l = None
            oversize = None
            if dim and dim.length_mm and dim.width_mm and dim.height_mm:
                volume_l = round(
                    dim.length_mm * dim.width_mm * dim.height_mm / 1_000_000, 2
                )
                oversize = max(dim.length_mm, dim.width_mm, dim.height_mm) > OVERSIZE_SIDE_MM
            row_models.append(
                ProductCardRow(
                    sku=sku,
                    name=record.get(ColumnsFullReport.NAME),
                    offer_id=record.get(ColumnsFullReport.OFFER_ID),
                    price=record.get(ColumnsFullReport.PRICE_CARD),
                    old_price=record.get(ColumnsFullReport.OLD_PRICE),
                    min_price=record.get(ColumnsFullReport.MIN_PRICE),
                    volume_weight_l=record.get(ColumnsFullReport.VOLUME_WEIGHT_L),
                    commission_fbo_percent=record.get(ColumnsFullReport.COMMISSION_FBO_PCT),
                    commission_fbs_percent=record.get(ColumnsFullReport.COMMISSION_FBS_PCT),
                    delivery_fbo=record.get(ColumnsFullReport.DELIVERY_FBO),
                    return_fbo=record.get(ColumnsFullReport.RETURN_FBO),
                    local_length_mm=dim.length_mm if dim else None,
                    local_width_mm=dim.width_mm if dim else None,
                    local_height_mm=dim.height_mm if dim else None,
                    local_weight_g=dim.weight_g if dim else None,
                    local_volume_l=volume_l,
                    oversize=oversize,
                )
            )

        payload = ProductCardsSectionResponse(
            section="product_cards",
            generated_at=generated_at,
            row_count=len(row_models),
            data=row_models,
        )
        await self._cache_section_payload("product_cards", payload.model_dump(mode="json"), cache_key=cache_key)
        return payload

    async def get_finance_expenses_section(
        self, seller: OzonSellerClient, date_from: str, date_to: str
    ) -> FinanceExpensesSectionResponse:
        """Секция «Финансовые начисления» (/v3/finance/transaction/list)"""
        generated_at = datetime.now(tz=timezone.utc)

        self._validate_dates(
            datetime.strptime(date_from, DATE_FORMAT).replace(tzinfo=timezone.utc),
            datetime.strptime(date_to, DATE_FORMAT).replace(tzinfo=timezone.utc),
        )

        cache_key = self._section_cache_key("finance_expenses", f"{date_from}_{date_to}")
        cached = await self._get_cached_section(cache_key, FinanceExpensesSectionResponse)
        if cached is not None:
            return cached

        # strict=True: ошибки выписки → 4xx/5xx
        finance_df, totals = await self._collect_finance_operations_data(
            seller, date_from, date_to, strict=True
        )
        records = (
            json.loads(finance_df.replace({nan: None}).to_json(orient="records", force_ascii=False))
            if not finance_df.empty
            else []
        )
        row_models = [
            FinanceExpenseRow(
                sku=record.get(ColumnsFullReport.SKU),
                sale_commission=record.get(ColumnsFullReport.FIN_COMMISSION),
                delivery=record.get(ColumnsFullReport.FIN_DELIVERY),
                return_delivery=record.get(ColumnsFullReport.FIN_RETURN_DELIVERY),
                services=record.get(ColumnsFullReport.FIN_SERVICES),
                accruals_for_sale=record.get(ColumnsFullReport.FIN_ACCRUALS),
                actual_logistics_per_unit=record.get(ColumnsFullReport.FIN_LOGISTICS_PER_UNIT),
            )
            for record in records
        ]

        payload = FinanceExpensesSectionResponse(
            section="finance_expenses",
            generated_at=generated_at,
            row_count=len(row_models),
            date_from=date_from,
            date_to=date_to,
            totals=totals,
            data=row_models,
        )
        await self._cache_section_payload("finance_expenses", payload.model_dump(mode="json"), cache_key=cache_key)
        return payload

    async def get_seller_rating_section(
        self, seller: OzonSellerClient
    ) -> SellerRatingSectionResponse:
        """Секция «Рейтинг продавца» (/v1/rating/summary)"""
        generated_at = datetime.now(tz=timezone.utc)
        cache_key = self._section_cache_key("seller_rating")

        cached = await self._get_cached_section(cache_key, SellerRatingSectionResponse)
        if cached is not None:
            return cached

        resp = await seller.get_rating_summary()
        rows = [
            SellerRatingRow(
                group_name=group.group_name,
                rating_type=item.rating_type,
                score=item.score,
                description=item.description,
            )
            for group in resp.groups
            for item in group.items
        ]

        payload = SellerRatingSectionResponse(
            section="seller_rating",
            generated_at=generated_at,
            row_count=len(rows),
            data=rows,
        )
        await self._cache_section_payload("seller_rating", payload.model_dump(mode="json"), cache_key=cache_key)
        return payload

    async def get_stock_planning_section(
        self, seller: OzonSellerClient
    ) -> StockPlanningSectionResponse:
        """Секция «Планирование поставок» (/v1/analytics/turnover/stocks)"""
        generated_at = datetime.now(tz=timezone.utc)
        cache_key = self._section_cache_key("stock_planning")

        cached = await self._get_cached_section(cache_key, StockPlanningSectionResponse)
        if cached is not None:
            return cached

        cards_items = await seller.get_all_product_info_items()
        skus = [str(item.sku) for item in cards_items if item.sku]
        if not skus:
            empty = StockPlanningSectionResponse(
                section="stock_planning",
                generated_at=generated_at,
                row_count=0,
                data=[],
            )
            await self._cache_section_payload("stock_planning", empty.model_dump(mode="json"), cache_key=cache_key)
            return empty

        warehouses_by_sku: dict[str, list[StockWarehouseRow]] = {}
        page = 1
        while page <= 50:
            stocks_resp = await seller.get_product_info_stocks(
                ProductInfoStocksRequest(page=page, page_size=1000)
            )
            for stock_item in stocks_resp.items:
                for st in stock_item.stocks:
                    key = str(st.sku) if st.sku is not None else str(stock_item.product_id)
                    warehouses_by_sku.setdefault(key, []).append(
                        StockWarehouseRow(name=st.warehouse_name, present=st.present, reserved=st.reserved)
                    )
            if not stocks_resp.items:
                break
            page += 1

        rows: list[StockPlanningRow] = []
        for sku_batch in self.pd_util.split_list(skus, max_length=10):
            resp = await seller.get_turnover_stocks(TurnoverStocksRequest(skus=sku_batch))
            for item in resp.items:
                calc = self._calc_stock_recommendation(
                    item, target_days=settings.STOCK_TARGET_DAYS, critical_days=settings.STOCK_CRITICAL_DAYS
                )
                days_of_stock = (
                    round(calc["days_of_stock"], 1) if calc["days_of_stock"] is not None else None
                )
                recommended_units = (
                    math.ceil(calc["recommended_stock"]) if calc["recommended_stock"] is not None else None
                )
                rows.append(
                    StockPlanningRow(
                        sku=item.sku,
                        name=item.name,
                        offer_id=item.offer_id,
                        current_stock=item.current_stock,
                        ads=item.ads,
                        days_of_stock=days_of_stock,
                        idc=item.idc,
                        idc_grade=item.idc_grade,
                        turnover=item.turnover,
                        recommended_stock=round(calc["recommended_stock"], 1) if calc["recommended_stock"] is not None else None,
                        recommended_units=recommended_units,
                        needs_reorder=calc["needs_reorder"],
                        priority=self._supply_priority(
                            calc["days_of_stock"],
                            settings.STOCK_TARGET_DAYS,
                            settings.STOCK_CRITICAL_DAYS,
                        ),
                        due_by=self._calc_due_by(calc["days_of_stock"]),
                        warehouses=warehouses_by_sku.get(str(item.sku), []),
                    )
                )

        payload = StockPlanningSectionResponse(
            section="stock_planning",
            generated_at=generated_at,
            row_count=len(rows),
            target_days=settings.STOCK_TARGET_DAYS,
            critical_days=settings.STOCK_CRITICAL_DAYS,
            plan_summary=self._build_plan_summary(rows),
            data=rows,
        )
        await self._cache_section_payload("stock_planning", payload.model_dump(mode="json"), cache_key=cache_key)
        return payload

    @staticmethod
    def _supply_priority(days_of_stock: float | None, target_days: int, critical_days: int) -> str:
        if days_of_stock is None:
            return "no-velocity"
        if days_of_stock < critical_days:
            return "critical"
        if days_of_stock < target_days:
            return "low"
        return "normal"

    @staticmethod
    def _calc_due_by(days_of_stock: float | None) -> str | None:
        if days_of_stock is None:
            return None
        due = datetime.now(tz=timezone.utc) + timedelta(days=days_of_stock)
        return due.date().isoformat()

    @staticmethod
    def _build_plan_summary(rows: list[StockPlanningRow]) -> PlanSummary:
        return PlanSummary(
            skus_total=len(rows),
            skus_needs_reorder=sum(1 for r in rows if r.needs_reorder),
            skus_critical=sum(1 for r in rows if r.priority == "critical"),
            total_units_to_ship=sum(r.recommended_units or 0 for r in rows if r.recommended_units),
        )


    async def get_search_queries_section(
        self, seller: OzonSellerClient, date_from: str, date_to: str
    ) -> SearchQueriesSectionResponse:
        """Секция «Поисковые фразы» (/v1/analytics/product-queries)"""
        generated_at = datetime.now(tz=timezone.utc)
        cache_key = self._section_cache_key("search_queries", f"{date_from}_{date_to}")

        cached = await self._get_cached_section(cache_key, SearchQueriesSectionResponse)
        if cached is not None:
            return cached

        cards_items = await seller.get_all_product_info_items()
        skus = [str(item.sku) for item in cards_items if item.sku]
        if not skus:
            empty = SearchQueriesSectionResponse(
                section="search_queries", generated_at=generated_at, row_count=0,
                date_from=date_from, date_to=date_to, data=[],
            )
            await self._cache_section_payload("search_queries", empty.model_dump(mode="json"), cache_key=cache_key)
            return empty

        rows: list[SearchQueryRow] = []
        for sku_batch in self.pd_util.split_list(skus, max_length=1000):
            page = 1
            while True:
                resp = await seller.get_product_queries(
                    ProductQueriesRequest(
                        date_from=date_from,
                        date_to=date_to,
                        skus=sku_batch,
                        page=page,
                        page_size=1000,
                    )
                )
                for item in resp.items:
                    rows.append(
                        SearchQueryRow(
                            phrase=item.name,
                            sku=item.sku,
                            offer_id=item.offer_id,
                            category=item.category,
                            gmv=item.gmv,
                            position=item.position,
                            unique_search_users=item.unique_search_users,
                            unique_view_users=item.unique_view_users,
                            view_conversion=item.view_conversion,
                        )
                    )
                if resp.page_count is None or page >= resp.page_count:
                    break
                page += 1

        payload = SearchQueriesSectionResponse(
            section="search_queries",
            generated_at=generated_at,
            row_count=len(rows),
            date_from=date_from,
            date_to=date_to,
            data=rows,
        )
        await self._cache_section_payload("search_queries", payload.model_dump(mode="json"), cache_key=cache_key)
        return payload

    async def get_cashflow_section(
        self, seller: OzonSellerClient, date_from: str, date_to: str
    ) -> CashFlowSectionResponse:
        """Секция «ДДС-журнал»: все операции периода с бегущим балансом"""
        generated_at = datetime.now(tz=timezone.utc)
        cache_key = self._section_cache_key("cashflow", f"{date_from}_{date_to}")

        cached = await self._get_cached_section(cache_key, CashFlowSectionResponse)
        if cached is not None:
            return cached

        operations = []
        page = 1
        while True:
            try:
                resp = await seller.get_finance_transaction_list(
                    FinanceTransactionListRequest(
                        filter_=FinanceTransactionListFilter(
                            date=FinanceTransactionDateFilter(
                                from_=datetime.strptime(date_from, DATE_FORMAT).replace(tzinfo=timezone.utc),
                                to=datetime.strptime(date_to, DATE_FORMAT).replace(tzinfo=timezone.utc),
                            ),
                            transaction_type=TransactionType.ALL,
                        ),
                        page=page,
                        page_size=1000,
                    )
                )
            except Exception as e:
                if _finance_method_closed(e):
                    raise OzonAPIError(_FINANCE_UNAVAILABLE_MESSAGE) from e
                raise
            operations.extend(resp.operations)
            logger.info(
                "::cashflow fetch page",
                page=page,
                got=len(resp.operations),
                total_collected=len(operations),
            )
            if resp.page_count is None or page >= resp.page_count:
                break
            page += 1

        type_names = sorted({o.operation_type_name or o.operation_type or "unknown" for o in operations})
        logger.info(
            "::cashflow collected",
            operations=len(operations),
            types=type_names,
        )

        def _op_date(op: Any) -> datetime:
            if not op.operation_date:
                return datetime.min.replace(tzinfo=timezone.utc)
            try:
                return datetime.fromisoformat(op.operation_date.replace("Z", "+00:00"))
            except ValueError:
                return datetime.min.replace(tzinfo=timezone.utc)

        operations.sort(key=_op_date)

        rows: list[CashFlowRow] = []
        balance = 0.0
        total_income = 0.0
        total_expense = 0.0
        type_summary: dict[str, float] = {}
        for op in operations:
            amount = op.amount or 0.0
            balance += amount
            if amount >= 0:
                total_income += amount
            else:
                total_expense += abs(amount)
            type_name = op.operation_type_name or op.operation_type or "Прочее"
            type_summary[type_name] = type_summary.get(type_name, 0.0) + amount
            rows.append(
                CashFlowRow(
                    date=op.operation_date,
                    operation_type=op.operation_type,
                    operation_type_name=op.operation_type_name,
                    amount=amount,
                    balance_after=round(balance, 2),
                )
            )

        payload = CashFlowSectionResponse(
            section="cashflow",
            generated_at=generated_at,
            row_count=len(rows),
            date_from=date_from,
            date_to=date_to,
            total_income=round(total_income, 2),
            total_expense=round(total_expense, 2),
            net_flow=round(total_income - total_expense, 2),
            type_summary={k: round(v, 2) for k, v in type_summary.items()},
            data=rows,
        )
        await self._cache_section_payload("cashflow", payload.model_dump(mode="json"), cache_key=cache_key)
        return payload

    @staticmethod
    def _calc_stock_recommendation(
        item: Any,
        *,
        target_days: int,
        critical_days: int,
    ) -> dict[str, Any]:
        """Дней запаса и рекомендуемая поставка по SKU"""
        ads = item.ads or 0
        if ads <= 0:
            return {"days_of_stock": None, "recommended_stock": None, "needs_reorder": False}
        current = item.current_stock or 0
        days_of_stock = current / ads
        recommended = max(0.0, ads * target_days - current)
        return {
            "days_of_stock": days_of_stock,
            "recommended_stock": recommended,
            "needs_reorder": days_of_stock < critical_days,
        }

    @staticmethod
    def _validate_dates(date_from: datetime, date_to: datetime) -> None:
        """Диапазон дат по лимитам Ozon"""
        if date_from > date_to:
            raise OzonAPIError("To date must be greater than from date")
        if date_to - date_from > timedelta(days=MAX_DATE_RANGE_DAYS):
            raise OzonAPIError(f"Date range must be lower {MAX_DATE_RANGE_DAYS} days")
        if datetime.now(tz=timezone.utc) - date_from > timedelta(days=MAX_BACK_DAYS):
            raise OzonAPIError(f"OzonAPI has limits for start date not more {MAX_BACK_DAYS} days")
        if date_to > datetime.now(tz=timezone.utc):
            raise OzonAPIError("Date range cannot be in the future")

    async def _compile_report_full_report(self, request_uuid: str, secrets, has_premium: bool) -> None:
        async with await get_async_context_session() as session:
            adapter = MetrixAdapter(session, self.adapter.user_id)
            try:
                request = await adapter.get_report_request(request_uuid)
                if request is None:
                    logger.error("::_compile_report> Report request not found", request_uuid=request_uuid)
                    raise ValueError("Unable get your request from database")

                # Настройки резолвим до клиентов: SettingsError без висящих соединений
                tax_system, logistics_cost, cost_price_share, fbo = await self._resolve_unit_economics_settings(adapter)

                seller = OzonSellerClient(
                    client_id=secrets.seller_client_id or "",
                    api_key=secrets.seller_api_key or "",
                )
                performance: OzonPerformanceClient | None = None
                if has_premium:
                    performance = OzonPerformanceClient(
                        client_id=secrets.performance_client_id or "",
                        client_secret=secrets.performance_secret or "",
                    )

                await adapter.update_report_status(request_uuid, ReportStatus.IN_PROGRESS.value)
                logger.info("::_compile_report> Report compilation started", request_uuid=request_uuid)

                date_from = request.date_from.strftime(DATE_FORMAT)
                date_to = request.date_to.strftime(DATE_FORMAT)

                seller_df = await self._collect_full_seller_data(seller, date_from, date_to, request_uuid)
                if seller_df.empty:
                    logger.exception("::_compile_report> No data for report", request_uuid=request_uuid)
                    raise ValueError("Unable get seller data for report")
                
                product_ids = seller_df["ID Товара"].tolist()

                ordered_ids: list[str | int] = product_ids
                if "Заказано, шт." in seller_df.columns:
                    ordered_ids = seller_df.loc[
                        pd.to_numeric(seller_df["Заказано, шт."], errors="coerce").fillna(0) > 0,
                        "ID Товара",
                    ].tolist()

                if has_premium and performance is not None:
                    collected = await asyncio.gather(
                        self._collect_full_performance_data(performance, date_from, date_to, request_uuid),
                        self._collect_stocks_data(seller, request_uuid, product_ids, ordered_ids=ordered_ids),
                        self._collect_product_cards_data(seller, product_ids),
                        self._collect_finance_operations_data(seller, date_from, date_to),
                    )
                    perf_df, perf_raw_cols = collected[0]
                    stocks_df = collected[1]
                    cards_df = collected[2]
                    finance_df, finance_totals = collected[3]
                else:
                    perf_df = pd.DataFrame()
                    perf_raw_cols: list[str] = []
                    collected = await asyncio.gather(
                        self._collect_stocks_data(seller, request_uuid, product_ids, ordered_ids=ordered_ids),
                        self._collect_product_cards_data(seller, product_ids),
                        self._collect_finance_operations_data(seller, date_from, date_to),
                    )
                    stocks_df = collected[0]
                    cards_df = collected[1]
                    finance_df, finance_totals = collected[2]
                logger.info(
                    "::_compile_report> Preparing to merge data",
                    seller_cols=seller_df.columns.tolist(),
                    perf_cols=perf_df.columns.tolist(),
                    stocks_cols=stocks_df.columns.tolist(),
                    cards_cols=cards_df.columns.tolist(),
                    finance_cols=finance_df.columns.tolist(),
                )
                
                merged_df = pd.merge(seller_df, perf_df, how="outer", on=["ID Товара", "Наименование"])
                logger.info("::_compile_report> Merged seller and performance", shape=merged_df.shape, cols=merged_df.columns.tolist())

                for frame in (merged_df, stocks_df):
                    if "ID Товара" in frame.columns:
                        frame["ID Товара"] = pd.to_numeric( # type: ignore
                            frame["ID Товара"], errors="coerce"
                        ).fillna(-1).astype("int64")
                merged_df = pd.merge(merged_df, stocks_df, how="left", on=["ID Товара"])
                
                # Гарантируем наличие колонки остатков даже если сбор не удался
                if "Остаток (на складах)" not in merged_df.columns:
                    merged_df["Остаток (на складах)"] = float("nan")
                logger.info("::_compile_report> Merged with stocks", shape=merged_df.shape, cols=merged_df.columns.tolist())

                # «Наименование» дублирует аналитику — дропаем до merge
                for frame in (merged_df, cards_df, finance_df):
                    if "ID Товара" in frame.columns and len(frame):
                        frame["ID Товара"] = pd.to_numeric(  # type: ignore
                            frame["ID Товара"], errors="coerce"
                        ).fillna(-1).astype("int64")
                if not cards_df.empty:
                    cards_for_merge = cards_df.drop(columns=["Наименование"], errors="ignore")
                    merged_df = pd.merge(merged_df, cards_for_merge, how="left", on=["ID Товара"])
                    logger.info("::_compile_report> Merged with product cards", shape=merged_df.shape)
                if not finance_df.empty:
                    merged_df = pd.merge(merged_df, finance_df, how="left", on=["ID Товара"])
                    logger.info("::_compile_report> Merged with finance operations", shape=merged_df.shape)

                
                expense_channels = [c for c in merged_df.columns if c.startswith("Расход")]
                income_channels = [c for c in merged_df.columns if c.startswith("Доход")]

                expense_total = self._sum_channel_columns(merged_df, expense_channels)
                income_total = self._sum_channel_columns(merged_df, income_channels)

                # Производные метрики эффективности
                if "Клики" in merged_df.columns:
                    logger.info("::_compile_report> Calculating efficiency metrics")
                    cart_additions_col = "В корзину(всего)" if "В корзину(всего)" in merged_df.columns else None
                    ordered_units_col = "Заказано, шт." if "Заказано, шт." in merged_df.columns else None
                    if cart_additions_col:
                        merged_df["CR в корзину, %\n(Интерес к товару)"] = pd.Series(
                            self.safe_division(
                                merged_df[cart_additions_col],
                                merged_df["Клики"]
                            ) * 100
                        ).round(2)
                    else:
                        logger.warning("::_compile_report> Missing 'В корзину(всего)' column, skipping CR в корзину, % metric")
                    if ordered_units_col:
                        merged_df["CR в заказы, %\n(Готовность к покупке)"] = pd.Series(
                            self.safe_division(
                                merged_df[ordered_units_col], 
                                merged_df["Клики"]
                            ) * 100
                        ).round(2)
                    else:
                        logger.warning("::_compile_report> Missing 'Заказано, шт.' column, skipping CR в заказы, % metric")

                    # CPA (Cost Per Action) - по совокупному расходу всех каналов
                    if ordered_units_col and expense_channels:
                        merged_df["CPA, ₽\n(Стоимость привлечения заказа)"] = pd.Series(
                            self.safe_division(expense_total, merged_df[ordered_units_col])
                        ).round(2)
                    else:
                        logger.warning("::_compile_report> Missing 'Заказано, шт.' or 'Расход' columns, skipping CPA, ₽ metrics")
                else:
                    logger.warning("::_compile_report> Missing 'Клики' column, skipping efficiency metrics", available_cols=merged_df.columns.tolist())

                if expense_channels:
                    logger.info("::_compile_report> Calculating profitability metrics")

                    merged_df["ROMI, %"] = pd.Series(
                        self.safe_division(
                            income_total - expense_total,
                            expense_total
                        ) * 100
                    ).round(2)  

                    # ДРР от подтвержденных продаж (Clean DRR).
                    revenue_col = next((c for c in ("Заказано на сумму, ₽", "Заказано, ₽") if c in merged_df.columns), None)
                    if revenue_col:
                        merged_df["ДРР (оплаченные), %"] = pd.Series(
                            self.safe_division(
                                expense_total,
                                merged_df[revenue_col]
                            ) * 100
                        ).round(2)
                    else:
                        logger.warning("::_compile_report> Missing revenue column, skipping ДРР (оплаченные), % metric")
                    
                    merged_df["ДРР (продвижение), %"] = pd.Series(
                        self.safe_division(
                            expense_total,
                            income_total
                        ) * 100
                    ).round(2)

                    if "Заказано, ₽" in merged_df.columns:
                        merged_df["ДРР (всего), %"] = pd.Series(
                            self.safe_division(
                                expense_total,
                                merged_df["Заказано, ₽"]
                            ) * 100
                        ).round(2)
                    else:
                        logger.warning("::_compile_report> Missing 'Заказано, ₽' column, skipping ДРР,% (Всего) metric")
                else:
                    logger.warning("::_compile_report> Missing 'Расход' columns, skipping profitability metrics")

                # Прибыль = выручка - себестоимость - комиссия - логистика - реклама - налог
                commission_rates_by_sku = self._build_commission_rates_by_sku(merged_df, prefer_fbo=fbo)
                actual_logistics_by_sku = self._build_actual_logistics_by_sku(merged_df)
                merged_df = self._add_unit_economics_metrics(
                    merged_df,
                    tax_system=tax_system,
                    logistics_cost=logistics_cost,
                    cost_price_share=cost_price_share,
                    commission_rates_by_sku=commission_rates_by_sku,
                    actual_logistics_per_unit_by_sku=actual_logistics_by_sku,
                )
                merged_df.to_csv(f"{config.PROJECT_ROOT}/files/{request_uuid}/unit_economics_report.csv", sep=";", decimal=",", index=False)

                # Удаляем служебные колонки рекламных отчётов (после расчётов метрик).
                if perf_raw_cols:
                    merged_df = merged_df.drop(columns=perf_raw_cols, errors="ignore")
                
                merged_df = self._generate_recommendations(merged_df)
                merged_df = self._add_benchmarks(merged_df)
                merged_df = self._add_z_scores(merged_df, ["ROMI, %", "ДРР (оплаченные), %"])

                # Итоговая строка Всего: суммы для абсолютных метрик, долевые
                merged_df = self._append_total_row(merged_df)

                # Сортируем: критические действия - сверху (по приоритету), затем по выручке
                if "Приоритет" in merged_df.columns:
                    merged_df = merged_df.sort_values(["Приоритет", "Заказано, ₽"], ascending=[False, False])
                else:
                    merged_df = merged_df.sort_values("Заказано, ₽", ascending=False)

                logger.info(
                    "::_compile_report> Final DataFrame prepared",
                    columns=merged_df.columns.tolist(),
                    shape=merged_df.shape,
                    head=merged_df.head(3).to_dict(orient="records")
                )
                cache_key = f"report_{request_uuid}"

                merged_df.to_csv(f"{config.PROJECT_ROOT}/files/{request_uuid}/full_report.csv", sep=";", decimal=",", index=False)
                await self.format_full_report_to_xlsx_v2(merged_df, f"{config.PROJECT_ROOT}/files/{request_uuid}/full_report")
                result_json = json.dumps(
                    merged_df.fillna("").to_dict(orient="records"), ensure_ascii=False, default=str # pyright: ignore[reportUnknownMemberType]
                )
                await adapter.set_cache(cache_key, result_json)

                # Сводные итоги финансового периода (/v3/finance/transaction/totals)
                await adapter.set_cache(
                    f"report_{request_uuid}_finance_totals",
                    json.dumps(finance_totals, ensure_ascii=False, default=str),
                )

                await adapter.update_report_status(request_uuid, ReportStatus.COMPLETED.value)
                logger.info("::_compile_report> Report compiled successfully", request_uuid=request_uuid)

            except Exception as e:
                logger.exception("::_compile_report> Report compilation failed", request_uuid=request_uuid, error=str(e))
                await adapter.update_report_status(
                    request_uuid, ReportStatus.FAILED.value, info=f"Error: {e}"
                )
            finally:
                await seller.close()
                if performance is not None:
                    await performance.close()

    async def _collect_full_seller_data(self, seller: OzonSellerClient, date_from: str, date_to: str, request_uuid: str) -> pd.DataFrame:
        try:
            from_dt = datetime.strptime(date_from, DATE_FORMAT).replace(tzinfo=timezone.utc)
            to_dt = datetime.strptime(date_to, DATE_FORMAT).replace(tzinfo=timezone.utc)
            df = await seller.process_full_analytics_report(from_dt, to_dt)
            logger.info(
                "::_collect_full_seller_data> Seller data collected",
                shape=df.shape,
                cols=df.columns.tolist(),
            )
            df.to_csv(f"{config.PROJECT_ROOT}/files/{request_uuid}/seller_report.csv", sep=";", decimal=",", index=False)
            if df.empty:
                return pd.DataFrame(columns=["ID Товара", "Наименование"])

            mask = pd.to_numeric(df["ID Товара"], errors="coerce").notna()
            if not bool(mask.all()):
                logger.info("::_collect_full_seller_data> Dropped non-product aggregate rows", rows=int((~mask).sum()))
                df = df[mask].copy()
            df["ID Товара"] = pd.to_numeric(df["ID Товара"], errors="raise").astype("int64")
            return df
        except Exception as e:
            logger.exception("::_collect_full_seller_data> Seller data collection failed", error=str(e))
            return pd.DataFrame(columns=["ID Товара", "Наименование"])


    async def _collect_product_cards_data(
        self,
        seller: OzonSellerClient,
        sku_list: list[int | str],
        *,
        strict: bool = False,
    ) -> pd.DataFrame:
        """Карточки: цены, комиссии; объёмный вес - габаритов в API нет"""
        empty = pd.DataFrame(columns=[ColumnsFullReport.SKU, ColumnsFullReport.NAME])
        if not sku_list:
            return empty
        try:
            rows: list[dict[str, Any]] = []
            for start in range(0, len(sku_list), PRODUCT_INFO_BATCH_SIZE):
                batch = [str(sku) for sku in sku_list[start:start + PRODUCT_INFO_BATCH_SIZE]]
                resp = await seller.get_product_info_list(ProductInfoListRequest(sku=batch))
                for item in resp.items:
                    fbo_commission = next(
                        (c for c in item.commissions or [] if (c.sale_schema or "").lower() == "fbo"),
                        None,
                    )
                    fbs_commission = next(
                        (c for c in item.commissions or [] if (c.sale_schema or "").lower() == "fbs"),
                        None,
                    )
                    rows.append(
                        {
                            ColumnsFullReport.SKU: int(item.sku) if item.sku is not None else None,
                            ColumnsFullReport.NAME: item.name or "",
                            ColumnsFullReport.OFFER_ID: item.offer_id,
                            ColumnsFullReport.PRICE_CARD: self._safe_float(item.price),
                            ColumnsFullReport.OLD_PRICE: self._safe_float(item.old_price),
                            ColumnsFullReport.MIN_PRICE: self._safe_float(item.min_price),
                            ColumnsFullReport.VOLUME_WEIGHT_L: item.volume_weight,
                            ColumnsFullReport.COMMISSION_FBO_PCT: (
                                fbo_commission.percent if fbo_commission else None
                            ),
                            ColumnsFullReport.COMMISSION_FBS_PCT: (
                                fbs_commission.percent if fbs_commission else None
                            ),
                            ColumnsFullReport.DELIVERY_FBO: (
                                fbo_commission.delivery_amount if fbo_commission else None
                            ),
                            ColumnsFullReport.RETURN_FBO: (
                                fbo_commission.return_amount if fbo_commission else None
                            ),
                        }
                    )
            df = pd.DataFrame(rows)
            df = df.dropna(subset=[ColumnsFullReport.SKU])
            df[ColumnsFullReport.SKU] = df[ColumnsFullReport.SKU].astype("int64")
            df = df.drop_duplicates(subset=[ColumnsFullReport.SKU])
            logger.info(
                "::_collect_product_cards_data> Product cards collected",
                requested=len(sku_list),
                collected=len(df),
            )
            return df
        except Exception as e:
            logger.exception("::_collect_product_cards_data> Failed", error=str(e))
            if strict:
                raise OzonAPIError(f"Не удалось получить карточки товаров: {e}") from e
            return empty

    async def _collect_finance_operations_data(
        self,
        seller: OzonSellerClient,
        date_from: str,
        date_to: str,
        *,
        strict: bool = False,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Финансовые начисления → (DataFrame по SKU, totals)"""
        empty = (pd.DataFrame(columns=["ID Товара"]), {})
        try:
            date_filter = {
                "date": {
                    "from": f"{date_from}T00:00:00.000Z",
                    "to": f"{date_to}T23:59:59.999Z",
                },
                # «all» - вся выписка; из неё агрегируем комиссии, доставки
                # и начисления по товарам.
                "transaction_type": TransactionType.ALL.value,
            }

            sku_aggregates: dict[int, dict[str, float]] = {}
            counted_postings: set[str] = set()
            page = 1
            while page <= FINANCE_MAX_PAGES:
                request = FinanceTransactionListRequest.model_validate(
                    {"filter": date_filter, "page": page, "page_size": 1000}
                )
                resp = await seller.get_finance_transaction_list(request)
                operations: list[FinanceOperation] = resp.operations
                if not operations:
                    break

                for op in operations:
                    delivery = op.delivery_charge or 0.0
                    return_delivery = op.return_delivery_charge or 0.0
                    commission = op.sale_commission or 0.0
                    services_sum = sum((s.price or 0.0) for s in op.services)
                    accruals = op.accruals_for_sale or 0.0

                    posting_number = op.posting.posting_number if op.posting else None
                    if posting_number and posting_number not in counted_postings:
                        counted_postings.add(posting_number)

                    for item in op.items:
                        if item.sku is None:
                            continue
                        sku = int(item.sku)
                        agg = sku_aggregates.setdefault(
                            sku,
                            {
                                "commission": 0.0,
                                "delivery": 0.0,
                                "return_delivery": 0.0,
                                "services": 0.0,
                                "accruals": 0.0,
                                "units": 0.0,
                            },
                        )
                        agg["commission"] += commission
                        agg["delivery"] += delivery
                        agg["return_delivery"] += return_delivery
                        agg["services"] += services_sum
                        agg["accruals"] += accruals
                        agg["units"] += 1  # единица товара в операции

                if resp.page_count is not None and page >= int(resp.page_count):
                    break
                page += 1

            # Точные итоги периода - из totals-метода
            totals: dict[str, Any] = {}
            try:
                totals_request = FinanceTransactionTotalsRequest.model_validate(
                    # У totals фильтр плоский (date/transaction_type на верхнем
                    # уровне тела), а date_filter имеет ровно такую структуру.
                    date_filter
                )
                totals_resp = await seller.get_finance_transaction_totals(totals_request)
                totals = totals_resp.result
            except Exception as e:
                logger.warning("::_collect_finance_operations_data> Totals failed", error=str(e))

            rows: list[dict[str, Any]] = []
            for sku, agg in sku_aggregates.items():
                units = agg["units"] or 0.0
                rows.append(
                    {
                        ColumnsFullReport.SKU: sku,
                        ColumnsFullReport.FIN_COMMISSION: round(agg["commission"], 2),
                        ColumnsFullReport.FIN_DELIVERY: round(agg["delivery"], 2),
                        ColumnsFullReport.FIN_RETURN_DELIVERY: round(agg["return_delivery"], 2),
                        ColumnsFullReport.FIN_SERVICES: round(agg["services"], 2),
                        ColumnsFullReport.FIN_ACCRUALS: round(agg["accruals"], 2),
                        # Фактическая логистика на единицу для юнит-экономики:
                        # сумма тарифов доставки по выписке / количество единиц.
                        ColumnsFullReport.FIN_LOGISTICS_PER_UNIT: (
                            round((abs(agg["delivery"]) + abs(agg["return_delivery"])) / units, 2)
                            if units > 0
                            else nan
                        ),
                    }
                )
            df = pd.DataFrame(rows)
            if not df.empty:
                df[ColumnsFullReport.SKU] = df[ColumnsFullReport.SKU].astype("int64")
            logger.info(
                "::_collect_finance_operations_data> Finance operations collected",
                sku_rows=len(df),
                pages=page,
                unique_postings=len(counted_postings),
            )
            return df, totals
        except Exception as e:
            logger.exception("::_collect_finance_operations_data> Failed", error=str(e))
            if _finance_method_closed(e):
                raise OzonAPIError(_FINANCE_UNAVAILABLE_MESSAGE) from e
            if strict:
                raise OzonAPIError(f"Не удалось получить финансовую выписку: {e}") from e
            return empty

    async def _collect_full_performance_data(
        self, performance: OzonPerformanceClient, date_from: str, date_to: str, request_uuid: str
    ) -> tuple[pd.DataFrame, list[str]]:
        """Реклама: доход/расход по товарам + сырые колонки"""
        try:
            logger.info("::_collect_full_performance_data> Starting collect performance data")
            daily_buffer = await performance.get_campaign_daily_stats_buffer(
                DailyStatsQueryParams(dateFrom=date_from, dateTo=date_to)
            )
            daily_df = await self.pd_util.pd_read_csv(daily_buffer)
            ids = (await self.pd_util.pd_drop_duplicates(daily_df))["ID"].tolist()
            ids = [str(_) for _ in ids]
            logger.info(
                "::_collect_full_performance_data> Campaign IDs deduplicated",
                count=len(ids),
            )

            campaigns: list[Campaign] = []
            split_ids = self.pd_util.split_list(ids, max_length=(len(ids) // 2) or 1)
            logger.info(
                "::_collect_full_performance_data> Campaign IDs split into parts",
                parts=len(split_ids),
                part_sizes=[len(p) for p in split_ids],
            )
            for part in split_ids:
                resp = await performance.list_campaigns(
                    CampaignQueryParams(campaignIds=part, state=CampaignState.UNKNOWN)
                )
                campaigns.extend(resp.list_campaign)
            logger.info(
                "::_collect_full_performance_data> Collected campaigns",
                count=len(campaigns),
            )
            campaigns_with_type = self._serialize_campaign_to_dict_with_type(campaigns)
            logger.info(
                "::_collect_full_performance_data> Campaigns grouped by type",
                counts_by_type={k: len(v) for k, v in campaigns_with_type.items()},
            )

            # Для каждого типа кампаний формируем отчёт и считаем доход/расход
            res_dfs: list[pd.DataFrame] = []
            raw_cols: list[str] = []
            for cp_type, campaign_ids in campaigns_with_type.items():
                _campaigns = campaign_ids
                if len(_campaigns) <= 10:
                    split_groups = [_campaigns]
                else:
                    split_groups = self.pd_util.split_list(_campaigns, 10)
                for group in split_groups:
                    _data: dict[str, Any] = {
                        "campaigns": group,
                        "from_": self._to_rfc3339(date_from, is_from=True),
                        "to": self._to_rfc3339(date_to),
                    }
                    res = await performance.submit_statistics(StatisticsRequest.model_validate(_data))
                    if await performance.wait_report([res], only_wait=True):
                        if not res.uuid:
                            logger.error("::_collect_full_performance_data> Unable get UUID for report")
                            raise RuntimeError
                        buffer_res = await performance.download_statistics_buffer(res.uuid)
                        df = await self._extract_df_from_buffer_response(buffer_res)

                        if cp_type == AdvObjectType.SEARCH_PROMO:
                            _x = await self._calculate_sum_expenditure_from_search_promo_campaign(df)
                        elif cp_type == AdvObjectType.SKU:
                            _x = await self._calculate_sum_expenditure_from_traffarets_campaign(df)
                        elif cp_type == AdvObjectType.BANNER:
                            logger.warning(
                                "::_collect_full_performance_data> BANNER campaigns are not yet supported, skipping",
                                skipped_campaigns=len(_campaigns),
                            )
                            continue
                        else:
                            logger.error(
                                "::_collect_full_performance_data> Unknown campaign type, skipping group",
                                campaign_type=cp_type,
                            )
                            continue

                        if not _x.empty:
                            ctr = self.ctr_c_name.format(self.readable_compaign_type[cp_type])
                            _x.rename(inplace=True, columns={"CTR (%)": ctr, **self.readable_column_mapping})

                            # Добавляем суффикс типа кампании к расходам и доходам
                            campaign_suffix = f" ({self.readable_compaign_type[cp_type]})"
                            if "Расход" in _x.columns:
                                _x.rename(columns={"Расход": f"Расход{campaign_suffix}"}, inplace=True)
                            if "Доход" in _x.columns:
                                _x.rename(columns={"Доход": f"Доход{campaign_suffix}"}, inplace=True)
                            
                            # Служебные «сырые» колонки отчёта кампании, не нужные в финальном отчёте
                            keep_in_report = {
                                "ID Товара",
                                "Наименование",
                                ctr,
                                f"Расход{campaign_suffix}",
                                f"Доход{campaign_suffix}",
                                "Цена товара",
                                "Клики",
                            }
                            raw_cols.extend(c for c in _x.columns if c not in keep_in_report)

                            logger.info(
                                "::_collect_full_performance_data> DataFrame after renaming",
                                campaign_type=cp_type,
                                columns=_x.columns.tolist(),
                                rows=len(_x)
                            )
                            res_dfs.append(_x)
                        else:
                            logger.warning(f"Calculated dataframe is empty for response: {res.model_dump()}")

            if not res_dfs:
                logger.warning("::_collect_full_performance_data> Performance data collection failed, res_dfs is empty")
                return pd.DataFrame(columns=["ID Товара", "Наименование", "Расход", "Доход"]), []

            # 4. Объединяем все таблицы и сохраняем разбивку расходов/доходов по каналам
            all_df = pd.concat(res_dfs, ignore_index=True)

            # Суммируем расходы и доходы по каждому каналу отдельно.
            numeric_cols = all_df.select_dtypes(include="number").columns
            agg_map: dict[str, str] = {
                c: "sum" for c in numeric_cols if c not in ("ID Товара", "Наименование", "Цена товара")
            }
            result = all_df.groupby(["ID Товара", "Наименование"], as_index=False).agg(agg_map)

            # Уникализируем список служебных колонок, сохраняя порядок появления
            raw_cols = list(dict.fromkeys(raw_cols))

            result.to_csv(f"{config.PROJECT_ROOT}/files/{request_uuid}/performance_report.csv", sep=";", decimal=",", index=False)
            return result, raw_cols
        except Exception as e:
            logger.exception("::_collect_full_performance_data> Performance data collection failed", error=str(e))
            return pd.DataFrame(columns=["ID Товара", "Наименование", "Расход", "Доход"]), []

    async def _collect_stocks_data(
        self,
        seller: OzonSellerClient,
        request_uuid: str,
        product_ids: list[str | int],
        ordered_ids: list[str | int] | None = None,
    ) -> pd.DataFrame:
        """Остатки: батчи для товаров с заказами, по одному для остальных"""
        try:
            logger.info("::_collect_stocks_data> Starting collect stocks data")

            str_ids = [str(pid) for pid in product_ids]
            ordered_set = {str(pid) for pid in (ordered_ids if ordered_ids is not None else product_ids)}
            batch_ids = [sku for sku in str_ids if sku in ordered_set]
            single_ids = [sku for sku in str_ids if sku not in ordered_set]
            logger.info(
                "::_collect_stocks_data> Batches vs single",
                batch_count=len(batch_ids),
                single_count=len(single_ids),
            )

            stocks_resp = AnalyticsStocksResponse(items=[])
            for ids in self.pd_util.split_list(batch_ids, max_length=10):
                resp = await seller.get_analytics_stocks(AnalyticsStocksRequest(skus=ids))
                stocks_resp.items.extend(resp.items)

            # Товары без заказов - по одному; одиночные 500/404 не роняют сбор
            for sku in single_ids:
                try:
                    resp = await seller.get_analytics_stocks(AnalyticsStocksRequest(skus=[sku]))
                    stocks_resp.items.extend(resp.items)
                except Exception as e:
                    logger.info(
                        "::_collect_stocks_data> Single SKU stock request failed, fallback to 0",
                        sku=sku,
                        error=str(e),
                    )

            items_data = [item.model_dump() for item in stocks_resp.items if item is not None]
            stocks_df = pd.json_normalize(items_data)
            logger.info(
                "::_collect_stocks_data> Collected stocks for specific products",
                items=len(product_ids),
                shape=stocks_df.shape if not stocks_df.empty else (0, 0),
                cols=stocks_df.columns.tolist(),
            )

            stocks_df.to_csv(f"{config.PROJECT_ROOT}/files/{request_uuid}/stocks_report.csv", sep=";", decimal=",", index=False)

            if "sku" in stocks_df.columns and "available_stock_count" in stocks_df.columns:
                stocks_df = stocks_df.groupby("sku")["available_stock_count"].sum().reset_index()
            else:
                logger.error(
                    "::_collect_stocks_data> Missing required columns in stocks data, zeroing unavailable SKUs",
                    columns=stocks_df.columns.tolist(),
                )
                stocks_df = pd.DataFrame({"sku": str_ids, "available_stock_count": 0.0})

            # Гарантируем строку для каждого товара отчёта: без ответа API - остаток 0.
            all_skus = pd.DataFrame({"sku": str_ids})
            if not stocks_df.empty:
                stocks_df = stocks_df.astype({"sku": str})
            stocks_df = all_skus.merge(stocks_df, how="left", on="sku").fillna(0)

            stocks_df.rename(columns={
                "sku": "ID Товара",
                "available_stock_count": "Остаток (на складах)",
            }, inplace=True)

            stocks_df["ID Товара"] = stocks_df["ID Товара"].astype(int)

            return stocks_df[["ID Товара", "Остаток (на складах)"]]
        except Exception as e:
            logger.exception("::_collect_stocks_data> Stocks data collection failed", error=str(e))
            return pd.DataFrame(columns=["ID Товара", "Остаток (на складах)"])


    @staticmethod
    def _to_rfc3339(date: str | datetime, is_from: bool = False) -> str:
        if isinstance(date, str):
            dt = datetime.strptime(date, DATE_FORMAT).replace(tzinfo=timezone.utc)
        else:
            dt = datetime.combine(date.date(), datetime.min.time(), tzinfo=timezone.utc)
        if is_from:
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=0)
            if dt > datetime.now(timezone.utc):
                dt = dt - timedelta(days=1)
        return dt.isoformat().replace("+00:00", "") + "Z"

    @staticmethod
    def _serialize_campaign_to_dict_with_type(data: list[Campaign]) -> dict[str, list[str]]:
        similars = {"ALL_SKU_PROMO": "SKU"}
        result: dict[str, list[str]] = {}
        for campaign in data:
            _type = campaign.adv_object_type
            if _type is None:
                continue
            _type_name = _type.value if hasattr(_type, "value") else str(_type)
            if _type_name in similars:
                _type_name = similars[_type_name]
            result.setdefault(_type_name, []).append(campaign.id)
        return result

    async def _extract_df_from_buffer_response(self, buffer_res: io.BytesIO) -> pd.DataFrame:
        _params: dict[str, Any] = {"skiprows": 1, "engine": "python", "skipfooter": 1}
        _x = await self.pd_util.unzip_with_combine(buffer_res, **_params)
        if _x is None:
            buffer_res.seek(0)
            _x = await self.pd_util.pd_read_csv(buffer_res, **_params)
        return _x

    async def _calculate_sum_expenditure_from_search_promo_campaign(self, df: pd.DataFrame) -> pd.DataFrame:
        """Доход/расход поисковых кампаний, устойчиво к пропускам"""
        try:
            logger.info(
                "::_calculate_sum_expenditure_from_search_promo_campaign> start",
                shape=df.shape,
                cols=df.columns.tolist(),
            )
            # Числовые колонки могут отсутствовать или содержать нечисловые значения
            for col in ("Цена продажи", "Расход, ₽", "Количество"):
                if col not in df.columns:
                    df[col] = 0.0
                elif not pd.api.types.is_numeric_dtype(df[col]):
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            # Доход строки = цена продажи × количество купленных единиц
            income_per_ozon = (
                df.assign(_income=df["Цена продажи"] * df["Количество"])
                .groupby("Ozon ID")["_income"]
                .sum()
                .reset_index(name="Доход")  # type: ignore
            )
            income_per_ozon_2 = df.groupby("Ozon ID")["Расход, ₽"].sum().reset_index(name="Расход")  # type: ignore
            income_per_ozon_3 = df.groupby("Ozon ID")["Количество"].sum().reset_index(name="kl")  # type: ignore

            df_merged = (
                df.drop_duplicates()
                .merge(
                    income_per_ozon_2.merge(income_per_ozon.merge(income_per_ozon_3, on=["Ozon ID"]), on=["Ozon ID"]),
                    on=["Ozon ID"],
                )
                .reset_index()
            )

            df_merged["Ср. Цена продажи"] = df_merged["Доход"] / df_merged["kl"]

            result = df_merged[["Ozon ID", "Наименование", "Ср. Цена продажи", "Доход", "Расход"]].drop_duplicates()
            result["Ozon ID"] = result["Ozon ID"].astype(int)
            result["Ср. Цена продажи"] = result["Ср. Цена продажи"].round(2)
            result.rename(inplace=True, columns={"Ozon ID": "sku", "Наименование": "Название товара"})
            return result
        except Exception as e:
            logger.exception("::_calculate_sum_expenditure_from_search_promo_campaign>", error=str(e))
            raise

    async def _calculate_sum_expenditure_from_traffarets_campaign(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            logger.info(
                "::_calculate_sum_expenditure_from_traffarets_campaign> start",
                shape=df.shape,
                cols=df.columns.tolist(),
            )
            if "Корректировка" in df["sku"].values:
                corr_row = df[df["sku"] == "Корректировка"]
                numeric_cols = df.select_dtypes(include="number").columns
                corr_column, corr_value = None, None
                for col in numeric_cols:
                    val = corr_row[col].iloc[0]
                    if val != 0:
                        corr_column, corr_value = col, val
                        break
                if corr_column is not None and corr_value is not None:
                    df.loc[df["sku"] != "Корректировка", corr_column] += corr_value
                    df = df[df["sku"] != "Корректировка"].reset_index(drop=True)

            rename_map:dict[str, Any] = {}
            
            expense_col = next((c for c in df.columns if "Расход" in c), None)
            if expense_col:
                rename_map[expense_col] = "Расход"
                
            revenue_col = next((c for c in df.columns if "Выручка" in c or "Доход" in c or "Продажи" in c), None)
            if revenue_col:
                rename_map[revenue_col] = "Доход"
                
            sell_col = next((c for c in df.columns if "Цена товара" in c), None)
            if sell_col:
                rename_map[sell_col] = "Цена товара"
            
            ctr_col = next((c for c in df.columns if "CTR" in c), None)
            if ctr_col:
                rename_map[ctr_col] = "CTR (%)"

            
            df = df.rename(columns=rename_map)
            
            if "Расход" not in df.columns:
                df["Расход"] = 0.0
                logger.warning("::_calculate_sum_expenditure_from_traffarets_campaign> 'Расход' not in df.columns")
            if "Доход" not in df.columns:
                df["Доход"] = 0.0
                logger.warning("::_calculate_sum_expenditure_from_traffarets_campaign> 'Доход' not in df.columns")
            if "CTR (%)" not in df.columns:
                df["CTR (%)"] = 0.0
                logger.warning("::_calculate_sum_expenditure_from_traffarets_campaign> 'CTR' not in df.columns")

            
            df["Расход"] = df["Расход"].astype(float)
            df["Доход"] = df["Доход"].astype(float)
            

            cols_to_drop = [c for c in df.columns if c in ["Дата добавления"]]
            result = df.drop(columns=cols_to_drop).drop_duplicates()

            result["sku"] = result["sku"].astype(int)
            return result
        except Exception as e:
            logger.exception("::_calculate_sum_expenditure_from_traffarets_campaign>", error=str(e))
            raise
        

    def _apply_conditional_format(
        self,
        df: pd.DataFrame,
        worksheet,
        workbook,
        col_name: str,
        fmt_type: str,
        *,
        op: str | None = None,
        value: float | int | None = None,
        colors: dict[str, str] | None = None,
        cell_format: dict[str, Any] | None = None,
    ) -> None:
        """Условное форматирование колонки, если есть"""
        if col_name not in df.columns or df.empty:
            return
        first_row, last_row = 1, len(df)
        col_idx = df.columns.get_loc(col_name)

        if fmt_type == "3_color_scale":
            schema = {"min": "#e40505", "mid": "#e4c005", "max": "#65c734"}
            schema.update(colors or {})
            worksheet.conditional_format( # type: ignore
                first_row,
                col_idx,
                last_row,
                col_idx,
                {
                    "type": "3_color_scale",
                    "min_color": schema["min"],
                    "mid_color": schema["mid"],
                    "max_color": schema["max"],
                },
            )
            return

        if fmt_type == "cell":
            if op is None or value is None:
                logger.warning("::_apply_conditional_format> 'op' and 'value' are required for 'cell'")
                return
            fmt = workbook.add_format( # type: ignore
                {
                    "bg_color": (cell_format or {}).get("bg_color", "#ffcccc"),
                    "font_color": (cell_format or {}).get("font_color", "#9c0006"),
                    "bold": (cell_format or {}).get("bold", False),
                }
            )
            worksheet.conditional_format( # type: ignore
                first_row,
                col_idx,
                last_row,
                col_idx,
                {"type": "cell", "criteria": op, "value": value, "format": fmt},
            )
            return

        logger.error("::_apply_conditional_format> Unknown format type", fmt_type=fmt_type)

    async def format_full_report_to_xlsx_v2(
        self, df: pd.DataFrame, path_to_save: str | Path
    ):
        if df.empty:
            raise OzonAPIError("Empty DataFrame.")
        try:
            df_sorted = df.sort_values(
                ["Приоритет", "Заказано, ₽"], ascending=[False, False]
            ) if "Приоритет" in df.columns else df.sort_values("Заказано, ₽", ascending=False)
            logger.info(
                "::format_full_report_to_xlsx_v2> Report prepared for formatting",
                shape=df_sorted.shape,
                cols=df_sorted.columns.tolist(),
            )
            with pd.ExcelWriter(path=f"{path_to_save}.xlsx", engine="xlsxwriter") as writer: 
                df_sorted.to_excel(writer, sheet_name="Summary", startrow=1, header=False, index=False) # type: ignore
                workbook = writer.book
                worksheet = writer.sheets["Summary"]
                header_fmt = workbook.add_format( # type: ignore
                    {
                        "bold": True,
                        "text_wrap": True,
                        "valign": "top",
                        "align": "center",
                        "border": 1,
                        "bg_color": "#8d83fb",
                    }
                )

                for col_num, value in enumerate(df_sorted.columns.values):
                    worksheet.write(0, col_num, value, header_fmt)

                for idx, col in enumerate(df_sorted.columns):
                    max_len = max(df_sorted[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.set_column(idx, idx, max_len)

                worksheet.set_row(0, 60)
                header_fmt.set_shrink()
                worksheet.freeze_panes(1, 0)
                
                self._apply_conditional_format(df_sorted, worksheet, workbook, "ДРР (оплаченные), %", "3_color_scale", colors={"min": "#65c734", "mid": "#e4c005", "max": "#e40505"})
                #self._apply_conditional_format(df_sorted, worksheet, workbook, "ДРР (оплаченные), %", "cell", op=">", value=30)
                    
                self._apply_conditional_format(df_sorted, worksheet, workbook, "ДРР (продвижение), %", "3_color_scale", colors={"min": "#65c734", "mid": "#e4c005", "max": "#e40505"})
                #self._apply_conditional_format(df_sorted, worksheet, workbook, "ДРР (продвижение), %", "cell", op=">", value=30)
                
                self._apply_conditional_format(df_sorted, worksheet, workbook, "ДРР (всего), %", "3_color_scale", colors={"min": "#65c734", "mid": "#e4c005", "max": "#e40505"})
                #self._apply_conditional_format(df_sorted, worksheet, workbook, "ДРР (всего), %", "cell", op=">", value=30)
                
                # Подсветка CTR (Конверсия кликов: чем выше, тем лучше)
                for ctr_col in [c for c in df_sorted.columns if "CTR" in c]:
                    self._apply_conditional_format(df_sorted, worksheet, workbook, ctr_col, "3_color_scale")

                # Остатки (красный если 0)
                self._apply_conditional_format(
                    df_sorted, worksheet, workbook, "Остаток (на складах)", "cell",
                    op="==", value=0, cell_format={"bg_color": "#ffcccc", "font_color": "#9c0006", "bold": True},
                )

                # ROMI: зелёный если >0, красный если <0
                self._apply_conditional_format(
                    df_sorted, worksheet, workbook, "ROMI, %", "cell",
                    op=">", value=0, cell_format={"bg_color": "#c6efce", "font_color": "#006100", "bold": True},
                )
                self._apply_conditional_format(
                    df_sorted, worksheet, workbook, "ROMI, %", "cell",
                    op="<", value=0, cell_format={"bg_color": "#ffcccc", "font_color": "#9c0006", "bold": True},
                )

                # Прибыль и Маржинальность: зелёный если >0, красный если <0
                for pnl_col in ("Прибыль, ₽", "Маржинальность, %"):
                    self._apply_conditional_format(
                        df_sorted, worksheet, workbook, pnl_col, "cell",
                        op=">", value=0, cell_format={"bg_color": "#c6efce", "font_color": "#006100", "bold": True},
                    )
                    self._apply_conditional_format(
                        df_sorted, worksheet, workbook, pnl_col, "cell",
                        op="<", value=0, cell_format={"bg_color": "#ffcccc", "font_color": "#9c0006", "bold": True},
                    )

                # Подсветка CR (Конверсия: чем выше, тем лучше)
                for cr_col in [c for c in df_sorted.columns if c.startswith("CR ")]:
                    self._apply_conditional_format(df_sorted, worksheet, workbook, cr_col, "3_color_scale")

                # Подсветка CPA (Стоимость привлечения заказа: чем ниже, тем лучше)
                self._apply_conditional_format(
                    df_sorted, worksheet, workbook, "CPA, ₽\n(Стоимость привлечения заказа)", "3_color_scale",
                    colors={"min": "#65c734", "mid": "#e4c005", "max": "#e40505"},
                )
                self._apply_conditional_format(
                    df_sorted, worksheet, workbook, "CPA, ₽\n(Стоимость привлечения заказа)", "cell",
                    op=">", value=500, cell_format={"bg_color": "#ffcccc", "font_color": "#9c0006", "bold": True},
                )

                # Подсветка Приоритета: критический (4) - красный, высокий (3) - янтарный
                self._apply_conditional_format(
                    df_sorted, worksheet, workbook, "Приоритет", "cell",
                    op="==", value=4, cell_format={"bg_color": "#ffcccc", "font_color": "#9c0006", "bold": True},
                )
                self._apply_conditional_format(
                    df_sorted, worksheet, workbook, "Приоритет", "cell",
                    op="==", value=3, cell_format={"bg_color": "#ffeb9c", "font_color": "#9c6500", "bold": True},
                )

            logger.info(f"Format to xlsx success as {path_to_save}")
        except Exception as e:
            logger.exception("::format_full_report_to_xlsx_v2>", error=str(e))
            raise
    
    @staticmethod
    def _sum_channel_columns(df: pd.DataFrame, channels: list[str]) -> pd.Series:
        """Каналы рекламы: NaN = 0 (не рекламировался)"""
        if not channels:
            return pd.Series(0.0, index=df.index)
        return df[channels].fillna(0).sum(axis=1)

    def safe_division(self, x: pd.Series, y: pd.Series) -> pd.Series:
        x = x.fillna(0).infer_objects().astype('float64') # pyright: ignore[reportUnknownMemberType]
        y = y.replace(0, nan).astype('float64').infer_objects() # pyright: ignore[reportUnknownMemberType]
        return x / y

    async def _resolve_unit_economics_settings(
        self, adapter: MetrixAdapter
    ) -> tuple[str, float, float, bool]:
        """Настройки юнит-экономики → (tax, logistics, cost_share, fbo)"""
        user_settings = await adapter.get_settings()
        tax_system = str(getattr(user_settings, "tax_system", "") or "")
        if not tax_system:
            raise SettingsError(
                "Требуется настройка налоговой системы (tax_system не задан). "
                "Укажите её в /api/settings."
            )
        logistics = getattr(user_settings, "logistics_cost", None)
        logistics_cost = float(logistics) if logistics is not None else DEFAULT_LOGISTICS_COST
        share = getattr(user_settings, "cost_price_share", None)
        cost_price_share = float(share) if share is not None else COST_PRICE_SHARE
        fbo = bool(getattr(user_settings, "fbo", False))
        return tax_system, logistics_cost, cost_price_share, fbo

    async def _get_secrets_or_raise(self) -> OzonSecrets:
        secrets = await self.adapter.get_secrets()
        if secrets is None:
            logger.info(f"Unable get secrets for user: {self.adapter.user_id}")
            raise OzonAPIError("Unable to get your Ozon secrets. Please configure them first")
        if not (secrets.seller_api_key and secrets.seller_client_id):
            raise OzonAPIError("Seller API secrets are required")
        return secrets

    def _make_seller_client(self, secrets: OzonSecrets) -> OzonSellerClient:
        return OzonSellerClient(
            client_id=secrets.seller_client_id or "",
            api_key=secrets.seller_api_key or "",
        )

    def _add_unit_economics_metrics(
        self,
        df: pd.DataFrame,
        tax_system: str | None = None,
        logistics_cost: float = DEFAULT_LOGISTICS_COST,
        cost_price_share: float = COST_PRICE_SHARE,
        *,
        commission_rates_by_sku: dict[int, float] | None = None,
        actual_logistics_per_unit_by_sku: dict[int, float] | None = None,
        oversize_skus: set[int] | None = None,
        warnings: list[str] | None = None,
    ) -> pd.DataFrame:
        """Юнит-экономика: средняя цена, прибыль, маржинальность"""
        revenue_col = ColumnsFullReport.REVENUE
        if revenue_col not in df.columns:
            logger.warning("::_add_unit_economics_metrics> Missing revenue column, skipping unit economics")
            return df

        tax_rate = get_tax_rate(tax_system)

        revenue = df[revenue_col].fillna(0).astype("float64")
        units = (
            df[ColumnsFullReport.ORDERED_UNITS].fillna(0).astype("float64")
            if ColumnsFullReport.ORDERED_UNITS in df.columns
            else pd.Series(0.0, index=df.index)
        )
        skus = [
            int(sku) if sku is not None and not pd.isna(sku) else -1
            for sku in df[ColumnsFullReport.SKU]
        ] if ColumnsFullReport.SKU in df.columns else [-1] * len(df)

        # Средняя цена товара из фактической выручки
        df[ColumnsFullReport.AVG_PRICE] = pd.Series(self.safe_division(revenue, units)).round(2)

        # Себестоимость: доля от выручки (настройка cost_price_share)
        cost = revenue * cost_price_share

        # Комиссия Ozon: доля от выручки по SKU
        commission_rub = self._map_sku_param(
            df, commission_rates_by_sku, default=0.0
        ) * revenue

        # Логистика на единицу: фактическая из фин. операций либо из настроек
        logistics_per_unit = self._map_sku_param(
            df, actual_logistics_per_unit_by_sku, default=logistics_cost
        )
        logistics = units * logistics_per_unit
        df[ColumnsFullReport.COMMISSION_OZON] = commission_rub.round(2)
        df[ColumnsFullReport.LOGISTICS_RUB] = logistics.round(2)

        expense_channels = [c for c in df.columns if c.startswith("Расход")]
        ad_spend = self._sum_channel_columns(df, expense_channels)

        pre_tax = revenue - cost - commission_rub - logistics - ad_spend
        if tax_system in INCOME_MINUS_EXPENSE_SYSTEMS:
            # УСН Доходы минус расходы: налог с положительной базы
            tax = pre_tax.clip(lower=0) * tax_rate
        else:
            # Прочие системы: налог с выручки
            tax = revenue * tax_rate

        df[ColumnsFullReport.PROFIT] = (pre_tax - tax).round(2)
        df[ColumnsFullReport.MARGIN] = pd.Series(
            self.safe_division(df[ColumnsFullReport.PROFIT], revenue) * 100
        ).round(2)

        # Предупреждения о точности - только для строк с продажами.
        if warnings is not None:
            sold = revenue > 0
            sold_skus = {sku for sku, s in zip(skus, sold) if s}
            missing_commission = sold_skus - set(commission_rates_by_sku or {})
            fallback_logistics = sold_skus - set(actual_logistics_per_unit_by_sku or {})
            if missing_commission:
                warnings.append(
                    f"Комиссия Ozon не найдена для {len(missing_commission)} товаров "
                    f"(SKU {sorted(missing_commission)[:5]}…) - принята 0 ₽. "
                    "Проверьте карточки /v5/product/info/prices."
                )
            if fallback_logistics:
                warnings.append(
                    f"Фактическая логистика из выписки отсутствует для {len(fallback_logistics)} "
                    f"товаров (SKU {sorted(fallback_logistics)[:5]}…) - использована настройка "
                    f"{logistics_cost} ₽/шт. Расчёт приблизительный."
                )
            oversize_found = oversize_skus and (sold_skus & oversize_skus)
            if oversize_found:
                warnings.append(
                    "Есть крупногабаритные товары (сторона > 500 мм): тариф из настроек "
                    "может занижать логистику - задайте фактические габариты в /api/products/dimensions."
                )
        return df

    @staticmethod
    def _map_sku_param(
        df: pd.DataFrame,
        params_by_sku: dict[int, float] | None,
        default: float,
    ) -> pd.Series:
        """{SKU: значение} → строки; нет SKU - default"""
        index = df.index
        if not params_by_sku or ColumnsFullReport.SKU not in df.columns:
            return pd.Series(default, index=index)
        return pd.Series(
            [float(params_by_sku.get(int(sku), default)) for sku in df[ColumnsFullReport.SKU]],
            index=index,
        )

    def _build_commission_rates_by_sku(
        self, df: pd.DataFrame, *, prefer_fbo: bool = False
    ) -> dict[int, float]:
        """Прогнозная комиссия из карточек FBO/FBS → {SKU: доля}"""
        rates: dict[int, float] = {}
        if df.empty or ColumnsFullReport.SKU not in df.columns:
            return rates
        fbo_col = (
            ColumnsFullReport.COMMISSION_FBO_PCT
            if ColumnsFullReport.COMMISSION_FBO_PCT in df.columns
            else None
        )
        fbs_col = (
            ColumnsFullReport.COMMISSION_FBS_PCT
            if ColumnsFullReport.COMMISSION_FBS_PCT in df.columns
            else None
        )
        if not fbo_col and not fbs_col:
            return rates
        primary, secondary = (
            (fbo_col, fbs_col) if prefer_fbo else (fbs_col, fbo_col)
        )
        for _, row in df.iterrows():
            try:
                sku = int(row[ColumnsFullReport.SKU])
            except (TypeError, ValueError):
                continue
            percent = None
            for col in (primary, secondary):
                if col is None:
                    continue
                value = row.get(col)
                if value is not None and not pd.isna(value) and float(value) > 0:
                    percent = float(value)
                    break
            if percent is not None:
                rates[sku] = percent / 100.0
        return rates

    def _build_actual_commission_rates_by_sku(self, df: pd.DataFrame) -> dict[int, float]:
        """Комиссия из выписки → {SKU: доля}"""
        actual: dict[int, float] = {}
        commission_col = ColumnsFullReport.FIN_COMMISSION
        if (
            df.empty
            or ColumnsFullReport.SKU not in df.columns
            or commission_col not in df.columns
            or ColumnsFullReport.REVENUE not in df.columns
        ):
            return actual
        commissions = pd.to_numeric(df[commission_col], errors="coerce").fillna(0.0)
        revenues = pd.to_numeric(df[ColumnsFullReport.REVENUE], errors="coerce").fillna(0.0)
        for sku, commission, revenue in zip(df[ColumnsFullReport.SKU], commissions, revenues):
            if revenue <= 0 or commission <= 0:
                continue
            try:
                actual[int(sku)] = round(float(commission) / float(revenue), 6)
            except (TypeError, ValueError):
                continue
        return actual

    def _build_actual_logistics_by_sku(self, df: pd.DataFrame) -> dict[int, float]:
        """Логистика из выписки → {SKU: ₽/ед}"""
        actual: dict[int, float] = {}
        col = ColumnsFullReport.FIN_LOGISTICS_PER_UNIT
        if df.empty or col not in df.columns or ColumnsFullReport.SKU not in df.columns:
            return actual
        series = pd.to_numeric(df[col], errors="coerce")
        for sku, value in zip(df[ColumnsFullReport.SKU], series):
            if value is None or pd.isna(value) or value <= 0:
                continue
            try:
                actual[int(sku)] = float(value)
            except (TypeError, ValueError):
                continue
        return actual

    def _append_total_row(self, df: pd.DataFrame) -> pd.DataFrame:
        """«Всего»: абсолютные суммируем, долевые пересчитываем"""
        if df.empty or "ID Товара" not in df.columns:
            return df

        def _col_sum(name: str | None) -> float:
            if name and name in df.columns and pd.api.types.is_numeric_dtype(df[name]):
                return float(df[name].fillna(0).sum())
            return 0.0

        expense_channels = [c for c in df.columns if c.startswith("Расход")]
        income_channels = [c for c in df.columns if c.startswith("Доход")]
        expense_sum = sum(_col_sum(c) for c in expense_channels)
        income_sum = sum(_col_sum(c) for c in income_channels)

        def _resolve(token: str) -> float:
            return {
                "__expense__": expense_sum,
                "__income__": income_sum,
                "__profit_ads__": income_sum - expense_sum,
            }.get(token, _col_sum(token))

        def _ratio(num: float, den: float) -> float:
            return round(num / den * 100, 2) if den else nan

        # Суммы для всех числовых колонок по умолчанию
        total: dict[str, Any] = {}
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                total[col] = _col_sum(col)
            else:
                total[col] = nan

        # Несуммируемые колонки очищаем
        for col in df.columns:
            if (
                col == "Приоритет"
                or col == "Цена товара"
                or "Z-Score" in col
                or "отклонение" in col
                or "Позиция" in col
            ):
                total[col] = nan

        # CTR - средний по товарам (показов по типам кампаний в отчёте нет)
        for col in df.columns:
            if "CTR" in col and pd.api.types.is_numeric_dtype(df[col]) and df[col].notna().any():
                total[col] = round(float(df[col].dropna().mean()), 2)
        # Долевые метрики (в процентах) - пересчёт из сумм компонентов
        ratio_pairs: dict[str, tuple[str, str]] = {
            "CR в корзину, %\n(Интерес к товару)": ("В корзину(всего)", "Клики"),
            "CR в заказы, %\n(Готовность к покупке)": ("Заказано, шт.", "Клики"),
            "Соотношение(в корзину из поиска или категории)": ("В корзину(поиск или категория)", "Показы(поиск и категория)"),
            "Соотношение(в корзину из карточки товара)": ("В корзину(карточка товара)", "Показы(карточка товара)"),
            "Соотношение(в корзину всего)": ("В корзину(всего)", "Показы(всего)"),
            "ДРР (продвижение), %": ("__expense__", "__income__"),
            "ДРР (всего), %": ("__expense__", "Заказано, ₽"),
            "ROMI, %": ("__profit_ads__", "__expense__"),
            "Маржинальность, %": ("Прибыль, ₽", "Заказано, ₽"),
        }
        for col, (num_token, den_token) in ratio_pairs.items():
            if col in df.columns:
                total[col] = _ratio(_resolve(num_token), _resolve(den_token))

        # ДРР (оплаченные): знаменатель как в построчном расчёте
        drr_paid_col = ColumnsFullReport.DRR_PAYED.value
        if drr_paid_col in df.columns:
            den_col = next((c for c in ("Заказано на сумму, ₽", "Заказано, ₽") if c in df.columns), None)
            total[drr_paid_col] = _ratio(expense_sum, _col_sum(den_col)) if den_col else nan

        # Абсолютные ratio-метрики
        units_sum = _col_sum("Заказано, шт.")
        cpa_col = "CPA, ₽\n(Стоимость привлечения заказа)"
        if cpa_col in df.columns:
            total[cpa_col] = round(expense_sum / units_sum, 2) if units_sum else nan
        if "Средняя цена товара" in df.columns:
            total["Средняя цена товара"] = round(_col_sum("Заказано, ₽") / units_sum, 2) if units_sum else nan

        total["ID Товара"] = "Всего"
        total["Наименование"] = "—"

        total_row = pd.DataFrame([total])
        return pd.concat([df, total_row], ignore_index=True)

    def _generate_recommendations(self, df: pd.DataFrame) -> pd.DataFrame:
        """Рекомендация + приоритет per SKU (0..4)"""
        rec_col, prio_col = "Рекомендация", "Приоритет"
        if rec_col in df.columns and prio_col in df.columns:
            return df

        stock_col = ColumnsFullReport.STOCK.value
        romi_col = ColumnsFullReport.ROMI.value
        drr_col = ColumnsFullReport.DRR_PAYED.value
        cr_col = ColumnsFullReport.CR_ORDER.value

        def _num(value: Any) -> tuple[float, bool]:
            if value is None:
                return 0.0, False
            try:
                if pd.isna(value):
                    return 0.0, False
                return float(value), True
            except (TypeError, ValueError):
                return 0.0, False

        def _decide(row: pd.Series) -> tuple[str, int]:
            stock, stock_known = _num(row.get(stock_col))
            romi, _ = _num(row.get(romi_col))
            drr, _ = _num(row.get(drr_col))
            cr, _ = _num(row.get(cr_col))

            if stock_known and stock <= 0:
                return "Нет в наличии: выключить рекламу / пополнить склад", 4
            if romi < 0:
                return "Убыточный товар: снизить ставки или выключить", 3
            if drr > 30:
                return "Высокий ДРР: оптимизировать ключевые фразы/ставки", 3
            if cr > 0 and stock_known and stock > 0 and romi > 50:
                return "Топ-товар: увеличить бюджет/ставки", 2
            if cr == 0 and drr > 0:
                return "Нулевая конверсия: проверить карточку/цену", 2
            return "Без действий", 0

        if df.empty:
            df[rec_col] = []
            df[prio_col] = []
            return df

        decisions = df.apply(_decide, axis=1)
        df[rec_col] = [d[0] for d in decisions]
        df[prio_col] = [d[1] for d in decisions]
        return df

    def _add_benchmarks(self, df: pd.DataFrame) -> pd.DataFrame:
        drr_col = ColumnsFullReport.DRR_PAYED.value
        cr_col = ColumnsFullReport.CR_ORDER.value

        if drr_col in df.columns and df[drr_col].notna().any():
            avg_drr = df[drr_col].mean()
            df["ДРР (отклонение от среднего, п.п.)"] = (df[drr_col] - avg_drr).round(2)

        if cr_col in df.columns and df[cr_col].notna().any():
            avg_cr = df[cr_col].mean()
            df["CR в заказы (отклонение от среднего, п.п.)"] = (df[cr_col] - avg_cr).round(2)

        return df

    def _add_z_scores(self, df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        for col in cols:
            if col in df.columns:
                mean = df[col].mean()
                std = df[col].std()
                if std > 0:
                    df[f"{col} (Z-Score)"] = ((df[col] - mean) / std).round(2)
                else:
                    df[f"{col} (Z-Score)"] = 0
        return df
    
    def _safe_float(self, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
