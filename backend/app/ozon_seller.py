"""Клиент Ozon Seller API"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import pandas as pd
import structlog

from backend.app.http_client import HTTPClient
from backend.app.pydantic_models.ozon.seller.enums import (
    AnalyticsDimension,
    AnalyticsMetric,
    AnalyticsSortOrder,
)
from backend.app.pydantic_models.ozon.seller.request import (
    AnalyticsDataRequest,
    AnalyticsSort,
    AnalyticsStocksRequest,
    FinanceTransactionListRequest,
    FinanceTransactionTotalsRequest,
    ManageStocksRequest,
    PostingFbsListRequest,
    PostingFbsUnfulfilledListRequest,
    ProductInfoListRequest,
    ProductInfoPricesV5Filter,
    ProductInfoPricesV5Request,
    ProductInfoStocksRequest,
    ProductListRequest,
    ProductQueriesDetailsRequest,
    ProductQueriesRequest,
    RatingHistoryRequest,
    ReportReturnsCreateRequest,
    ReviewListRequest,
    TurnoverStocksRequest,
)
from backend.app.pydantic_models.ozon.seller.response import (
    AnalyticsGetDataResponse,
    AnalyticsStocksResponse,
    FinanceTransactionListResponse,
    FinanceTransactionTotalsResponse,
    ManageStocksResponse,
    PostingFbsListResponse,
    PostingFbsUnfulfilledListResponse,
    ProductInfoItem,
    ProductInfoListResponse,
    ProductInfoPricesItemV5,
    ProductInfoPricesV5Response,
    ProductInfoStocksResponse,
    ProductListResponse,
    ProductQueriesDetailsResponse,
    ProductQueriesResponse,
    RatingHistoryResponse,
    RatingSummaryResponse,
    ReportReturnsCreateResponse,
    ReviewListResponse,
    TurnoverStocksResponse,
    WarehouseListResponse,
)

logger = structlog.get_logger(__name__)


class OzonSellerClient:
    """Клиент Seller API v1-v3"""

    BASE_URL = "https://api-seller.ozon.ru"

    def __init__(self, client_id: str, api_key: str):
        self.client_id = client_id
        self.api_key = api_key
        # ~6-7 RPS — запас к лимитам Ozon, редкие 429 дожимает backoff
        self._http = HTTPClient(timeout=30.0, min_request_interval=0.15)
        self._headers = {
            "Client-Id": client_id,
            "Api-Key": api_key,
            "Content-Type": "application/json",
        }
        self.userfriendly_metric = {
            "revenue": "Заказано, ₽",
            "ordered_units": "Заказано, шт.",
            "hits_view_search": "Показы(поиск и категория)",
            "hits_view_pdp": "Показы(карточка товара)",
            "hits_view": "Показы(всего)",
            "hits_tocart_search": "В корзину(поиск или категория)",
            "hits_tocart_pdp": "В корзину(карточка товара)",
            "hits_tocart": "В корзину(всего)",
            "session_view_search": "Уникальные показы(поиск или каталог)",
            "session_view_pdp": "Уникальные показы(карточка товара)",
            "session_view": "Уникальные показы(всего)",
            "conv_tocart_search": "Соотношение(в корзину из поиска или категории)",
            "conv_tocart_pdp": "Соотношение(в корзину из карточки товара)",
            "conv_tocart": "Соотношение(в корзину всего)",
            "returns": "Возвраты",
            "cancellations": "Отмены",
            "delivered_units": "Доставлено",
            "position_category": "Позиция(поиск и категория)",
        }
        self.readable_base_header = {"id": "ID Товара", "name": "Наименование"}

    async def _request(self, method: str, path: str, **kwargs: dict[str, Any]):
        return await self._http.request(method, path, base_url=self.BASE_URL, headers=self._headers, **kwargs)

    async def check_connection(self) -> bool:
        try:
            resp = await self._request("GET", "/v1/actions")
            return resp.status_code == 200
        except (ConnectionError, TimeoutError) as e:
            logger.warning("Seller API check failed", error=str(e))
            return False


    async def get_product_list(
        self, request: ProductListRequest | None = None
    ) -> ProductListResponse:
        """Получить список товаров (с пагинацией)"""
        if request is None:
            request = ProductListRequest()
        payload = request.model_dump(mode="json", exclude_none=True, by_alias=True)
        resp = await self._request("POST", "/v3/product/list", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_product_list",
            request=payload,
            response=resp_json,
        )
        return ProductListResponse.model_validate(resp_json)

    async def get_analytics_data(
        self, request: AnalyticsDataRequest
    ) -> AnalyticsGetDataResponse:
        json_request = request.model_dump(mode="json", exclude_none=True)
        resp = await self._request(
            "POST",
            "/v1/analytics/data",
            json=json_request,
        )
        resp = resp.json()
        logger.info(
            "::get_analytics_data",
            request=json_request,
            response=resp,
        )
        return AnalyticsGetDataResponse.model_validate(resp)

    async def get_analytics_stocks(self, data: AnalyticsStocksRequest) -> AnalyticsStocksResponse:
        payload = data.model_dump(mode="json", exclude_none=True)
        resp = await self._request("POST", "/v1/analytics/stocks", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_analytics_stocks",
            request=payload,
            response=resp_json,
        )
        return AnalyticsStocksResponse.model_validate(resp_json)

    async def get_rating_history(
        self, request: RatingHistoryRequest
    ) -> RatingHistoryResponse:
        """/v1/rating/history"""
        payload = request.model_dump(mode="json", exclude_none=True)
        resp = await self._request("POST", "/v1/rating/history", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_rating_history",
            request=payload,
            response=resp_json,
        )
        return RatingHistoryResponse.model_validate(resp_json)

    async def get_rating_summary(self) -> RatingSummaryResponse:
        """/v1/rating/summary"""
        payload = {}
        resp = await self._request("POST", "/v1/rating/summary", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_rating_summary",
            request=payload,
            response=resp_json,
        )
        return RatingSummaryResponse.model_validate(resp_json)

    async def get_product_queries(self, request: ProductQueriesRequest) -> ProductQueriesResponse:
        """/v1/analytics/product-queries"""
        payload = request.model_dump(mode="json", exclude_none=True)
        resp = await self._request("POST", "/v1/analytics/product-queries", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_product_queries",
            request=payload,
            response=resp_json,
        )
        return ProductQueriesResponse.model_validate(resp_json)

    async def get_turnover_stocks(self, request: TurnoverStocksRequest) -> TurnoverStocksResponse:
        """/v1/analytics/turnover/stocks"""
        payload = request.model_dump(mode="json", exclude_none=True)
        resp = await self._request("POST", "/v1/analytics/turnover/stocks", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_turnover_stocks",
            request=payload,
            response=resp_json,
        )
        return TurnoverStocksResponse.model_validate(resp_json)

    async def get_product_queries_details(
        self, request: ProductQueriesDetailsRequest
    ) -> ProductQueriesDetailsResponse:
        payload = request.model_dump(mode="json", exclude_none=True)
        resp = await self._request("POST", "/v1/analytics/product-queries/details", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_product_queries_details",
            request=payload,
            response=resp_json,
        )
        return ProductQueriesDetailsResponse.model_validate(resp_json)

    async def manage_stocks(self, request: ManageStocksRequest) -> ManageStocksResponse:
        payload = request.model_dump(mode="json", exclude_none=True)
        resp = await self._request("POST", "/v1/analytics/manage/stocks", json=payload)
        resp_json = resp.json()
        logger.info(
            "::manage_stocks",
            request=payload,
            response=resp_json,
        )
        return ManageStocksResponse.model_validate(resp_json)

    async def get_finance_transaction_list(
        self, request: FinanceTransactionListRequest
    ) -> FinanceTransactionListResponse:
        """/v3/finance/transaction/list"""
        payload = request.model_dump(mode="json", exclude_none=True, by_alias=True)
        resp = await self._request("POST", "/v3/finance/transaction/list", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_finance_transaction_list",
            request=payload,
            response=resp_json,
        )
        return FinanceTransactionListResponse.model_validate(resp_json)

    async def get_finance_transaction_totals(
        self, request: FinanceTransactionTotalsRequest
    ) -> FinanceTransactionTotalsResponse:
        payload = request.model_dump(mode="json", exclude_none=True, by_alias=True)
        resp = await self._request("POST", "/v3/finance/transaction/totals", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_finance_transaction_totals",
            request=payload,
            response=resp_json,
        )
        return FinanceTransactionTotalsResponse.model_validate(resp_json)

    async def create_returns_report(
        self, request: ReportReturnsCreateRequest
    ) -> ReportReturnsCreateResponse:
        """/v2/report/returns/create"""
        payload = request.model_dump(mode="json", exclude_none=True)
        resp = await self._request("POST", "/v2/report/returns/create", json=payload)
        resp_json = resp.json()
        logger.info(
            "::create_returns_report",
            request=payload,
            response=resp_json,
        )
        return ReportReturnsCreateResponse.model_validate(resp_json)

    async def get_reviews(self, request: ReviewListRequest) -> ReviewListResponse:
        """/v1/review/list"""
        payload = request.model_dump(mode="json", exclude_none=True)
        resp = await self._request("POST", "/v1/review/list", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_reviews",
            request=payload,
            response=resp_json,
        )
        return ReviewListResponse.model_validate(resp_json)

    async def get_posting_fbs_list(
        self, request: PostingFbsListRequest
    ) -> PostingFbsListResponse:
        """/v3/posting/fbs/list"""
        payload = request.model_dump(mode="json", exclude_none=True, by_alias=True)
        resp = await self._request("POST", "/v3/posting/fbs/list", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_posting_fbs_list",
            request=payload,
            response=resp_json,
        )
        return PostingFbsListResponse.model_validate(resp_json)

    async def get_posting_fbs_unfulfilled_list(
        self, request: PostingFbsUnfulfilledListRequest
    ) -> PostingFbsUnfulfilledListResponse:
        payload = request.model_dump(mode="json", exclude_none=True, by_alias=True)
        resp = await self._request("POST", "/v3/posting/fbs/unfulfilled/list", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_posting_fbs_unfulfilled_list",
            request=payload,
            response=resp_json,
        )
        return PostingFbsUnfulfilledListResponse.model_validate(resp_json)

    async def get_product_info_stocks(
        self, request: ProductInfoStocksRequest
    ) -> ProductInfoStocksResponse:
        payload = request.model_dump(mode="json", exclude_none=True)
        resp = await self._request("POST", "/v4/product/info/stocks", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_product_info_stocks",
            request=payload,
            response=resp_json,
        )
        return ProductInfoStocksResponse.model_validate(resp_json)

    async def get_product_info_list(
        self, request: ProductInfoListRequest
    ) -> ProductInfoListResponse:
        """/v3/product/info/list"""
        payload = request.model_dump(mode="json", exclude_none=True)
        resp = await self._request("POST", "/v3/product/info/list", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_product_info_list",
            request=payload,
            response=resp_json,
        )
        return ProductInfoListResponse.model_validate(resp_json)

    async def get_all_product_info_items(
        self, *, catalog_page_size: int = 100, info_batch_size: int = 1000
    ) -> list[ProductInfoItem]:
        """Полный каталог карточек продавца.

        /v3/product/info/list с пустым фильтром Ozon отклоняет
        (400 «use either offer_id or product_id or sku»), поэтому сначала
        собираем SKU постранично через /v3/product/list, затем берём карточки
        (имя, комиссии, объёмный вес) батчами по SKU из info/list.
        Важно: product/list при limit=1000 возвращает пустой result —
        страничный размер каталога не должен превышать 100.
        """
        skus: list[str] = []
        last_id = ""
        while True:
            resp = await self.get_product_list(
                ProductListRequest(last_id=last_id, limit=catalog_page_size)
            )
            page = [item for item in resp.items if item.sku is not None]
            if not page:
                break
            skus.extend(str(item.sku) for item in page)
            last_id = resp.last_id or ""
            if len(page) < catalog_page_size or not last_id:
                break

        items: list[ProductInfoItem] = []
        for start in range(0, len(skus), info_batch_size):
            batch = skus[start:start + info_batch_size]
            info = await self.get_product_info_list(ProductInfoListRequest(sku=batch))
            items.extend(info.items)
        return items

    async def get_product_info_prices(
        self, request: ProductInfoPricesV5Request
    ) -> ProductInfoPricesV5Response:
        """/v5/product/info/prices"""
        payload = request.model_dump(mode="json", exclude_none=True, by_alias=True)
        resp = await self._request("POST", "/v5/product/info/prices", json=payload)
        first_page = ProductInfoPricesV5Response.model_validate(resp.json())

        items: list[ProductInfoPricesItemV5] = list(first_page.items)
        cursor = first_page.cursor or ""
        max_pages = 20  # защитный предел: 20 * 1000 = 20 000 позиций
        pages = 1

        while cursor and pages < max_pages:
            payload["cursor"] = cursor
            resp = await self._request("POST", "/v5/product/info/prices", json=payload)
            page = ProductInfoPricesV5Response.model_validate(resp.json())
            items.extend(page.items)
            cursor = page.cursor or ""
            pages += 1

        if cursor:
            logger.warning(
                "::get_product_info_prices> Cursor pagination stopped at safety limit",
                pages=pages,
                collected=len(items),
            )

        logger.info(
            "::get_product_info_prices",
            request=payload,
            response={"items": len(items), "pages": pages},
        )
        return ProductInfoPricesV5Response(
            cursor=cursor,
            items=items,
            total=first_page.total if first_page.total is not None else len(items),
        )

    async def get_product_info_prices_from_sku(self, sku: int | str) -> dict[str, Any] | None:
        """Цены и комиссии одного товара по SKU (sku -> product_id -> /v5/prices)"""
        info = await self.get_product_info_list(ProductInfoListRequest(sku=[sku]))
        if not info.items or info.items[0].product_id is None:
            return None
        product_id = info.items[0].product_id
        resp = await self.get_product_info_prices(
            ProductInfoPricesV5Request(
                filter=ProductInfoPricesV5Filter(product_id=[product_id])
            )
        )
        if not resp.items:
            return None
        item = resp.items[0]
        commissions = item.commissions
        fbo_min = commissions.fbo_direct_flow_trans_min_amount if commissions else None
        fbo_max = commissions.fbo_direct_flow_trans_max_amount if commissions else None
        fbs_min = commissions.fbs_first_mile_min_amount if commissions else None
        fbs_max = commissions.fbs_first_mile_max_amount if commissions else None
        return {
            "product_id": item.product_id,
            "offer_id": item.offer_id,
            "price": float(item.price.price) if item.price and item.price.price else None,
            "commission_fbo_percent": commissions.sales_percent_fbo if commissions else None,
            "commission_fbs_percent": commissions.sales_percent_fbs if commissions else None,
            "acquiring_percent": item.acquiring,
            "logistics_fbo_mid": (fbo_min + fbo_max) / 2 if fbo_min is not None and fbo_max is not None else None,
            "logistics_fbs_first_mile_mid": (fbs_min + fbs_max) / 2 if fbs_min is not None and fbs_max is not None else None,
            "volume_weight_l": item.volume_weight,
        }

    async def get_warehouse_list(self) -> WarehouseListResponse:
        payload = {}
        resp = await self._request("POST", "/v2/warehouse/list", json=payload)
        resp_json = resp.json()
        logger.info(
            "::get_warehouse_list",
            request=payload,
            response=resp_json,
        )
        return WarehouseListResponse.model_validate(resp_json)


    async def process_full_analytics_report(self, date_from: datetime, date_to: datetime) -> pd.DataFrame:
        df = pd.DataFrame()
        pd.options.display.float_format = "{:.2f}".format
        valid_metrics = [m for m in AnalyticsMetric if m != AnalyticsMetric.UNKNOWN]
        for metric in valid_metrics:
            resp = await self.get_analytics_data(
                AnalyticsDataRequest(
                    date_to=date_to.strftime("%Y-%m-%d"),
                    date_from=date_from.strftime("%Y-%m-%d"),
                    dimension=[AnalyticsDimension.SKU],
                    metrics=[metric],
                    sort=[AnalyticsSort(key=metric, order=AnalyticsSortOrder.DESC)],
                )
            )
            parsed = await self._parse_analytics_data(resp, metric)
            if df.empty:
                df = parsed
            else:
                df = pd.merge(df, parsed, on=["id", "name"], how="outer")
            await asyncio.sleep(2)
        df = await self._make_header_readable(df)
        return df

    async def _parse_analytics_data(self, data: AnalyticsGetDataResponse, metric_name: str = "") -> pd.DataFrame:
        items = data.result
        if items is None:
            raise ValueError("Empty response from Ozon API")
        items = items.data

        df = pd.json_normalize(
            [_.model_dump() for _ in items],
            max_level=2,
            record_path=["dimensions"],
            meta=["metrics"],
        )
        df["metric"] = df["metrics"].str[0]
        df = df.drop(columns=["metrics"])
        df["id"] = df["id"].astype(int)
        df["name"] = df["name"].astype(str)
        match metric_name:
            case AnalyticsMetric.CONV_TOCART_SEARCH.value | AnalyticsMetric.CONV_TOCART_PDP.value | AnalyticsMetric.CONV_TOCART.value:
                total_metric = df["metric"].mean()
                total_row = pd.DataFrame([{"id": "Всего", "name": "—", "metric": total_metric}])
            case AnalyticsMetric.POSITION_CATEGORY.value:
                df["metric"] = df["metric"].round(2)
                total_row = pd.DataFrame([{"id": "Всего", "name": "—", "metric": "—"}])
            case _:
                total_metric = df["metric"].sum()
                total_row = pd.DataFrame([{"id": "Всего", "name": "—", "metric": total_metric}])
        df = pd.concat([df, total_row], ignore_index=True)
        df = df.rename(columns={"metric": self.userfriendly_metric.get(metric_name)})
        return df

    async def _make_header_readable(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            return df.rename(columns=self.readable_base_header)
        except (KeyError, ValueError) as e:
            logger.warning("[OzonSellerClient] Failed to rename columns: %s", str(e))
            return df

    async def close(self):
        await self._http.close()
