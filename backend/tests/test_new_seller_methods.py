"""Тесты новых типизированных методов Ozon Seller API.

Покрывают методы, добавленные по расширенному списку API:
- Аналитика: /v1/analytics/product-queries/details, /v1/analytics/manage/stocks;
- Финансы:   /v3/finance/transaction/list, /v3/finance/transaction/totals,
             /v2/report/returns/create;
- Репутация: /v1/review/list (без order_number — ограничение API),
             /v1/rating/history;
- Поставки:  /v3/posting/fbs/list, /v3/posting/fbs/unfulfilled/list,
             /v4/product/info/stocks, /v3/product/info/list, /v2/warehouse/list.

Проверяются: сериализация запросов (алиасы, нормализация дат, SKU->str,
exclude_none), ограничения лимитов Ozon и парсинг ответов клиента в Pydantic-
модели (без обращения к сети).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from backend.app.ozon_seller import OzonSellerClient
from backend.app.pydantic_models.ozon.seller.enums import (
    FbpFilter,
    PostingSortDir,
    ReviewStatus,
    SellerReportType,
    StockShipmentType,
    TransactionType,
)
from backend.app.pydantic_models.ozon.seller.request import (
    FinanceTransactionDateFilter,
    FinanceTransactionListFilter,
    FinanceTransactionListRequest,
    FinanceTransactionTotalsRequest,
    ManageStocksRequest,
    PostingFbsListFilter,
    PostingFbsListRequest,
    PostingFbsUnfulfilledListFilter,
    PostingFbsUnfulfilledListRequest,
    PostingFbsWithParams,
    ProductInfoListRequest,
    ProductInfoStocksRequest,
    ProductQueriesDetailsRequest,
    RatingHistoryRequest,
    ReportReturnsCreateRequest,
    ReviewListRequest,
)
from backend.app.pydantic_models.ozon.seller.response import (
    FinanceOperation,
    FinanceTransactionListResponse,
    FbsPosting,
    ManageStocksResponse,
    ProductInfoItem,
    ProductInfoListResponse,
    ProductInfoModelInfo,
    ProductInfoStocksResponse,
    ProductInfoStocksStock,
    PostingFbsListResponse,
    PostingFbsUnfulfilledListResponse,
    ProductQueriesDetailsItem,
    ProductQueriesDetailsResponse,
    RatingHistoryResponse,
    ReportReturnsCreateResponse,
    Review,
    ReviewListResponse,
    Warehouse,
    WarehouseListResponse,
)

UTC_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def make_seller() -> OzonSellerClient:
    return OzonSellerClient("test-client-id", "test-api-key")


def install_fake_transport(seller: OzonSellerClient, payload: dict[str, Any]) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    async def fake_request(
        method: str, path: str, base_url: Any = None, headers: Any = None, **kwargs: Any
    ) -> Any:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs.get("json")
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.json = MagicMock(return_value=payload)
        return resp

    seller._http.request = fake_request  # type: ignore[method-assign]
    return captured


# /v1/analytics/product-queries/details — детализация поисковых запросов


class TestProductQueriesDetails:
    def test_serialization_normalizes_sku_and_dates(self) -> None:
        req = ProductQueriesDetailsRequest(
            date_from=UTC_NOW, date_to=UTC_NOW, sku=1585887323, page_size=500
        )
        payload = req.model_dump(mode="json", exclude_none=True)
        assert payload["sku"] == "1585887323"
        assert payload["date_from"] == "2026-08-26T12:00:00+00:00"
        assert payload["date_to"] == "2026-08-26T12:00:00+00:00"
        assert payload["page"] == 1
        assert payload["page_size"] == 500

    def test_page_size_over_limit_rejected(self) -> None:
        with pytest.raises(ValueError):
            ProductQueriesDetailsRequest(
                date_from=UTC_NOW, date_to=UTC_NOW, sku="123", page_size=1001
            )

    @pytest.mark.asyncio
    async def test_client_parses_query_positions(self) -> None:
        seller = make_seller()
        captured = install_fake_transport(
            seller,
            {
                "items": [
                    {
                        "query": "кроссовки мужские",
                        "position": 3.4,
                        "gmv": 125000.5,
                        "order_count": 12,
                        "sku": 1585887323,
                    }
                ]
            },
        )
        result = await seller.get_product_queries_details(
            ProductQueriesDetailsRequest(date_from=UTC_NOW, date_to=UTC_NOW, sku=1585887323)
        )

        assert isinstance(result, ProductQueriesDetailsResponse)
        assert captured["path"] == "/v1/analytics/product-queries/details"
        assert captured["json"]["sku"] == "1585887323"
        item = result.items[0]
        assert isinstance(item, ProductQueriesDetailsItem)
        assert item.query == "кроссовки мужские"
        assert item.position == 3.4
        assert item.order_count == 12


# /v1/analytics/manage/stocks — управление остатками (бета)


class TestManageStocks:
    def test_skus_normalized_to_strings(self) -> None:
        req = ManageStocksRequest(skus=[111, "222"], warehouse_id=42)
        payload = req.model_dump(mode="json", exclude_none=True)
        assert payload["skus"] == ["111", "222"]
        assert payload["warehouse_id"] == 42
        assert "action" not in payload  # None отброшен

    @pytest.mark.asyncio
    async def test_client_posts_manage_stocks(self) -> None:
        seller = make_seller()
        captured = install_fake_transport(seller, {})
        result = await seller.manage_stocks(
            ManageStocksRequest(skus=["111"], warehouse_id=7, action="update")
        )

        assert isinstance(result, ManageStocksResponse)
        assert captured["path"] == "/v1/analytics/manage/stocks"
        assert captured["json"]["skus"] == ["111"]
        assert captured["json"]["warehouse_id"] == 7


def _finance_filter() -> FinanceTransactionListFilter:
    return FinanceTransactionListFilter(
        date=FinanceTransactionDateFilter(from_=UTC_NOW, to=UTC_NOW),
    )


class TestFinanceTransactionList:
    def test_filter_aliased_and_none_excluded(self) -> None:
        req = FinanceTransactionListRequest(filter_=_finance_filter())
        payload = req.model_dump(mode="json", exclude_none=True, by_alias=True)
        assert set(payload) == {"filter", "page", "page_size"}
        assert payload["filter"]["transaction_type"] == "all"
        assert payload["filter"]["date"]["from"] == "2026-08-26T12:00:00.000Z"
        assert payload["filter"]["date"]["to"] == "2026-08-26T12:00:00.000Z"
        assert payload["page_size"] == 1000

    def test_page_size_capped_at_1000(self) -> None:
        with pytest.raises(ValueError):
            FinanceTransactionListRequest(filter_=_finance_filter(), page_size=2000)

    def test_transaction_type_enum_value(self) -> None:
        f = FinanceTransactionListFilter(
            date=_finance_filter().date, transaction_type=TransactionType.ORDER
        )
        dumped = f.model_dump(mode="json")
        assert dumped["transaction_type"] == "order"

    @pytest.mark.asyncio
    async def test_client_parses_operations(self) -> None:
        seller = make_seller()
        captured = install_fake_transport(
            seller,
            {
                # Реальный формат API: операции вложены в result
                # (financev3FinanceTransactionListV3Response из swagger_saller.json).
                "result": {
                    "operations": [
                        {
                            "operation_id": 987654,
                            "operation_type": "OperationOrderPayment",
                            "amount": 1500.0,
                            "accruals_for_sale": 1200.0,
                            "sale_commission": -180.0,
                            "posting": {
                                "posting_number": "12345678-0001-1",
                                "delivery_schema": "FBS",
                                "warehouse_id": 55,
                            },
                            "items": [{"sku": 1585887323, "name": "Кроссовки"}],
                            "services": [{"name": "MarketplaceDeliveryService", "price": 60.5}],
                        }
                    ],
                    "page_count": 3,
                    "row_count": 2500,
                }
            },
        )
        result = await seller.get_finance_transaction_list(
            FinanceTransactionListRequest(filter_=_finance_filter())
        )

        assert isinstance(result, FinanceTransactionListResponse)
        assert captured["path"] == "/v3/finance/transaction/list"
        assert result.page_count == 3
        op = result.operations[0]
        assert isinstance(op, FinanceOperation)
        assert op.posting is not None and op.posting.posting_number == "12345678-0001-1"
        assert op.items[0].sku == 1585887323
        assert op.services[0].price == 60.5

    @pytest.mark.asyncio
    async def test_flat_payload_still_accepted(self) -> None:
        """Плоский ответ без обёртки result парсится для обратной совместимости"""
        seller = make_seller()
        install_fake_transport(
            seller,
            {
                "operations": [{"operation_id": 1, "amount": 10.0}],
                "page_count": 1,
                "row_count": 1,
            },
        )
        result = await seller.get_finance_transaction_list(
            FinanceTransactionListRequest(filter_=_finance_filter())
        )
        assert result.operations[0].operation_id == 1
        assert result.page_count == 1
        assert result.row_count == 1

    def test_nested_model_matches_swagger(self) -> None:
        """Вложенная структура result соответствует financev3FinanceTransactionListV3Response"""
        resp = FinanceTransactionListResponse.model_validate(
            {"result": {"operations": [], "page_count": 0, "row_count": 0}}
        )
        assert resp.result.operations == []
        assert resp.result.page_count == 0
        assert resp.result.row_count == 0


class TestFinanceTransactionTotals:
    def test_flat_payload_matches_swagger(self) -> None:
        """У totals фильтр без обёртки «filter» — поля на верхнем уровне"""
        req = FinanceTransactionTotalsRequest(
            date=FinanceTransactionDateFilter(from_=UTC_NOW, to=UTC_NOW)
        )
        payload = req.model_dump(mode="json", exclude_none=True, by_alias=True)
        assert set(payload) == {"date", "transaction_type"}
        assert payload["date"]["from"] == "2026-08-26T12:00:00.000Z"
        assert payload["transaction_type"] == "all"

    def test_date_or_posting_required(self) -> None:
        with pytest.raises(ValueError):
            FinanceTransactionTotalsRequest()
        # posting_number вместо периода — валидно (oneOf в swagger).
        ok = FinanceTransactionTotalsRequest(posting_number="12345678-0001-1")
        assert ok.posting_number == "12345678-0001-1"

    @pytest.mark.asyncio
    async def test_client_parses_totals(self) -> None:
        seller = make_seller()
        captured = install_fake_transport(
            seller, {"result": {"accruals_for_sale": 90000.0, "sale_commission": -13500.0}}
        )
        result = await seller.get_finance_transaction_totals(
            FinanceTransactionTotalsRequest(
                date=FinanceTransactionDateFilter(from_=UTC_NOW, to=UTC_NOW)
            )
        )

        assert captured["path"] == "/v3/finance/transaction/totals"
        # Тело запроса плоское: date/transaction_type без обёртки «filter».
        assert "filter" not in captured["json"]
        assert captured["json"]["date"]["from"] == "2026-08-26T12:00:00.000Z"
        assert result.result["accruals_for_sale"] == 90000.0


# /v2/report/returns/create — отчёт по возвратам


class TestReportReturnsCreate:
    def test_defaults_seller_returns_and_language(self) -> None:
        req = ReportReturnsCreateRequest(date_from=UTC_NOW, date_to=UTC_NOW)
        payload = req.model_dump(mode="json", exclude_none=True)
        assert payload["report_type"] == SellerReportType.SELLER_RETURNS.value
        assert payload["language"] == "DEFAULT"
        assert payload["date_from"] == "2026-08-26T12:00:00+00:00"

    @pytest.mark.asyncio
    async def test_client_returns_report_code(self) -> None:
        seller = make_seller()
        captured = install_fake_transport(
            seller,
            {"code": "report-abc", "status": "", "report_type": "SELLER_RETURNS"},
        )
        result = await seller.create_returns_report(
            ReportReturnsCreateRequest(date_from=UTC_NOW, date_to=UTC_NOW)
        )

        assert isinstance(result, ReportReturnsCreateResponse)
        assert captured["path"] == "/v2/report/returns/create"
        assert captured["json"]["report_type"] == "SELLER_RETURNS"
        assert result.code == "report-abc"


# /v1/review/list — список отзывов


class TestReviewList:
    @pytest.mark.parametrize("limit", [5, 19, 101])
    def test_limit_out_of_bounds_rejected(self, limit: int) -> None:
        with pytest.raises(ValueError):
            ReviewListRequest(limit=limit)

    def test_default_payload_has_empty_last_id(self) -> None:
        payload = ReviewListRequest().model_dump(mode="json", exclude_none=True)
        assert payload["last_id"] == ""
        assert payload["limit"] == 20

    def test_status_filter_accepts_enum(self) -> None:
        req = ReviewListRequest(status=ReviewStatus.UNPROCESSED, sort_dir="ASC")
        payload = req.model_dump(mode="json", exclude_none=True)
        assert payload["status"] == ReviewStatus.UNPROCESSED.value

    @pytest.mark.asyncio
    async def test_client_parses_reviews_without_order_number(self) -> None:
        seller = make_seller()
        captured = install_fake_transport(
            seller,
            {
                "has_next": False,
                "last_id": "",
                "reviews": [
                    {
                        "id": "review-1",
                        "rating": 4,
                        "text": "Хорошие кроссовки",
                        "sku": 1585887323,
                        "comments_amount": 0,
                    }
                ],
            },
        )
        result = await seller.get_reviews(ReviewListRequest(limit=50))

        assert isinstance(result, ReviewListResponse)
        assert captured["path"] == "/v1/review/list"
        assert captured["json"]["limit"] == 50
        review: Review = result.reviews[0]
        assert review.rating == 4 and review.sku == 1585887323
        # Известное ограничение API: номер заказа не возвращается, поля в модели нет.
        assert "order_number" not in type(review).model_fields


# /v1/rating/history — история рейтингов (типизированная версия)


class TestRatingHistory:
    def test_request_serialization(self) -> None:
        req = RatingHistoryRequest(
            date_from=UTC_NOW, date_to=UTC_NOW, ratings=["index_price"]
        )
        payload = req.model_dump(mode="json", exclude_none=True)
        assert payload["ratings"] == ["index_price"]
        assert payload["date_from"] == "2026-08-26T12:00:00+00:00"

    @pytest.mark.asyncio
    async def test_client_parses_history(self) -> None:
        seller = make_seller()
        captured = install_fake_transport(
            seller,
            {"ratings": [{"rating_type": "rating_on_time", "values": [{"value": 98.5}]}]},
        )
        result = await seller.get_rating_history(
            RatingHistoryRequest(date_from=UTC_NOW, date_to=UTC_NOW, ratings=["rating_on_time"])
        )

        assert isinstance(result, RatingHistoryResponse)
        assert captured["path"] == "/v1/rating/history"
        assert result.ratings[0]["rating_type"] == "rating_on_time"


# /v3/posting/fbs/list — список поставок FBS


class TestPostingFbsList:
    def test_serialization_aliases_and_dates(self) -> None:
        req = PostingFbsListRequest(
            filter_=PostingFbsListFilter(since=UTC_NOW, to=UTC_NOW, fbp_filter=FbpFilter.ONLY),
            dir=PostingSortDir.ASC,
            limit=100,
            with_=PostingFbsWithParams(analytics_data=True, barcodes=True),
        )
        payload = req.model_dump(mode="json", exclude_none=True, by_alias=True)

        assert payload["filter"]["since"] == "2026-08-26T12:00:00+00:00"
        assert payload["filter"]["to"] == "2026-08-26T12:00:00+00:00"
        assert payload["filter"]["fbpFilter"] == "ONLY"
        assert payload["dir"] == "asc"
        assert payload["with"]["analytics_data"] is True

    def test_limit_over_1000_rejected(self) -> None:
        with pytest.raises(ValueError):
            PostingFbsListRequest(
                filter_=PostingFbsListFilter(since=UTC_NOW, to=UTC_NOW), limit=1001
            )

    @pytest.mark.asyncio
    async def test_client_parses_postings_with_shipment_date(self) -> None:
        seller = make_seller()
        captured = install_fake_transport(
            seller,
            {
                "has_next": False,
                "postings": [
                    {
                        "posting_number": "03953949-0017-1",
                        "order_id": 43820841,
                        "order_number": "1007001-0006-1",
                        "status": "awaiting_deliver",
                        "shipment_date": "2026-08-21T10:00:00Z",
                        "shipment_date_without_delay": "2026-08-20T00:00:00Z",
                        "products": [
                            {"sku": 1585887323, "name": "Кроссовки", "price": 2990.0, "quantity": 1}
                        ],
                        "barcodes": {"lower_barcode": "651048002", "upper_barcode": "14077758"},
                    }
                ],
            },
        )
        result = await seller.get_posting_fbs_list(
            PostingFbsListRequest(
                filter_=PostingFbsListFilter(since=UTC_NOW, to=UTC_NOW),
                with_=PostingFbsWithParams(barcodes=True),
            )
        )

        assert isinstance(result, PostingFbsListResponse)
        assert captured["path"] == "/v3/posting/fbs/list"
        assert captured["json"]["with"] == {"barcodes": True}
        posting: FbsPosting = result.postings[0]
        # Ключевой параметр контроля логистики — дата отгрузки без задержек.
        assert posting.shipment_date_without_delay == "2026-08-20T00:00:00Z"
        assert posting.products[0].sku == 1585887323
        assert posting.barcodes is not None and posting.barcodes.upper_barcode == "14077758"


# /v3/posting/fbs/unfulfilled/list — неотгруженные поставки


class TestPostingFbsUnfulfilledList:
    def test_serialization_normalizes_cutoff_dates(self) -> None:
        req = PostingFbsUnfulfilledListRequest(
            filter_=PostingFbsUnfulfilledListFilter(cutoff_from=UTC_NOW, cutoff_to=UTC_NOW)
        )
        payload = req.model_dump(mode="json", exclude_none=True, by_alias=True)

        assert payload["filter"]["cutoff_from"] == "2026-08-26T12:00:00+00:00"
        assert payload["filter"]["cutoff_to"] == "2026-08-26T12:00:00+00:00"

    @pytest.mark.asyncio
    async def test_client_parses_unfulfilled_postings(self) -> None:
        seller = make_seller()
        captured = install_fake_transport(
            seller,
            {
                "postings": [
                    {
                        "posting_number": "03953949-0018-1",
                        "status": "awaiting_packaging",
                        "cutoff": "2026-08-27T14:30:00Z",
                    }
                ]
            },
        )
        result = await seller.get_posting_fbs_unfulfilled_list(
            PostingFbsUnfulfilledListRequest(
                filter_=PostingFbsUnfulfilledListFilter(cutoff_from=UTC_NOW, cutoff_to=UTC_NOW)
            )
        )

        assert isinstance(result, PostingFbsUnfulfilledListResponse)
        assert captured["path"] == "/v3/posting/fbs/unfulfilled/list"
        assert result.postings[0].posting_number == "03953949-0018-1"


# /v4/product/info/stocks — остатки по товарам


class TestProductInfoStocks:
    def test_page_size_bounds(self) -> None:
        req = ProductInfoStocksRequest(sku="1585887323", page=2, page_size=1000)
        payload = req.model_dump(mode="json", exclude_none=True)

        assert payload["sku"] == "1585887323"
        assert payload["page_size"] == 1000
        with pytest.raises(ValueError):
            ProductInfoStocksRequest(sku="123", page_size=1001)

    @pytest.mark.asyncio
    async def test_client_parses_warehouse_stocks(self) -> None:
        seller = make_seller()
        captured = install_fake_transport(
            seller,
            {
                "cursor": "",
                "total": 1,
                "items": [
                    {
                        "offer_id": "ART-1001",
                        "product_id": 77413819,
                        "stocks": [
                            {
                                "sku": 1585887323,
                                "present": 12,
                                "reserved": 3,
                                "shipment_type": "SHIPMENT_TYPE_GENERAL",
                            }
                        ],
                    }
                ],
            },
        )
        result = await seller.get_product_info_stocks(ProductInfoStocksRequest(sku="1585887323"))

        assert isinstance(result, ProductInfoStocksResponse)
        assert captured["path"] == "/v4/product/info/stocks"
        assert result.total == 1
        stock = result.items[0].stocks[0]
        assert isinstance(stock, ProductInfoStocksStock)
        assert stock.present == 12 and stock.reserved == 3
        assert stock.shipment_type == StockShipmentType.GENERAL


# /v3/product/info/list — информация о товарах (+склеенные карточки)


class TestProductInfoList:
    def test_ids_normalized_to_str(self) -> None:
        req = ProductInfoListRequest(product_id=[123, 456], sku=[789])
        payload = req.model_dump(mode="json", exclude_none=True)

        assert payload["product_id"] == ["123", "456"]
        assert payload["sku"] == ["789"]

    @pytest.mark.asyncio
    async def test_client_detects_merged_card(self) -> None:
        seller = make_seller()
        captured = install_fake_transport(
            seller,
            {
                "items": [
                    {
                        "offer_id": "ART-2002",
                        "product_id": 77413820,
                        "sku": 1585887420,
                        "name": "Куртка",
                        "model_info": {"count": 3, "model_id": 100500},
                        "visibility_details": {"has_price": True, "has_stock": True},
                    }
                ]
            },
        )
        result = await seller.get_product_info_list(
            ProductInfoListRequest(sku=[1585887420])
        )

        assert isinstance(result, ProductInfoListResponse)
        assert captured["path"] == "/v3/product/info/list"
        item = result.items[0]
        assert isinstance(item, ProductInfoItem)
        # model_info.count > 1 => склеенная карточка.
        model_info = item.model_info
        assert isinstance(model_info, ProductInfoModelInfo)
        assert model_info.count == 3


# /v2/warehouse/list — список складов


class TestWarehouseList:
    @pytest.mark.asyncio
    async def test_client_parses_warehouses(self) -> None:
        seller = make_seller()
        captured = install_fake_transport(
            seller,
            {
                "result": [
                    {
                        "warehouse_id": 900001,
                        "name": "Коледино",
                        "is_rfbs": False,
                        "is_kgt": True,
                        "status": "NEW",
                        "working_days": ["Mon", "Tue"],
                    }
                ]
            },
        )
        result = await seller.get_warehouse_list()

        assert isinstance(result, WarehouseListResponse)
        assert captured["path"] == "/v2/warehouse/list"
        warehouse: Warehouse = result.result[0]
        assert warehouse.warehouse_id == 900001
        assert warehouse.name == "Коледино"
        assert warehouse.is_rfbs is False
