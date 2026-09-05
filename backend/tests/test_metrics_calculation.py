"""Юнит-тесты расчёта метрик отчёта и сетевой надёжности.

Покрывают фиксы по логу app_20260824_121749_clean.json:
- 500 на /v1/analytics/stocks (null-поля в payload, отсутствие retry на 5xx);
- 429 «Превышен лимит активных запросов (максимум 1)» на Performance API;
- юнит-экономика (прибыль/маржинальность с налогом и логистикой из настроек);
- итоговая строка «Всего» с пересчётом долевых метрик из сумм.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pandas as pd
import pytest

from backend.app import config
from backend.app.http_client import HTTPClient
from backend.app.ozon_performance import OzonPerformanceClient
from backend.app.ozon_seller import OzonSellerClient
from backend.app.pydantic_models.ozon.seller.enums import (
    ProductQueriesSortBy,
    ProductQueriesSortDir,
    TurnoverGrade,
)
from backend.app.pydantic_models.ozon.seller.request import (
    AnalyticsStocksRequest,
    ProductQueriesRequest,
    TurnoverStocksRequest,
)
from backend.app.pydantic_models.ozon.seller.response import (
    AnalyticsStocksResponse,
    AnalyticsStocksResponseItem,
    ProductQueriesResponse,
    RatingSummaryResponse,
)
from backend.app.services.report_service import ReportService


@pytest.fixture
def report_service() -> ReportService:
    """ReportService с мок-адаптером (БД не используется)"""
    return ReportService(MagicMock())


# Stocks: payload без null-полей (фикс 500 {"code":2})

class TestStocksRequestPayload:
    def test_model_dump_excludes_null_fields(self) -> None:
        payload = AnalyticsStocksRequest(skus=[1, "2", 3]).model_dump(mode="json", exclude_none=True)
        assert payload == {"skus": ["1", "2", "3"]}

    @pytest.mark.asyncio
    async def test_client_sends_no_null_fields(self) -> None:
        seller = OzonSellerClient("cid", "key")
        captured: dict[str, Any] = {}

        async def fake_request(method: str, path: str, base_url: Any = None, headers: Any = None, **kwargs: Any) -> Any:
            captured.update(kwargs.get("json") or {})
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            resp.json = MagicMock(return_value={"items": []})
            return resp

        seller._http.request = fake_request  # type: ignore[method-assign]
        await seller.get_analytics_stocks(AnalyticsStocksRequest(skus=[1585887323]))

        assert captured["skus"] == ["1585887323"]
        for null_field in ("cluster_ids", "item_tags", "turnover_grades", "warehouse_ids"):
            assert null_field not in captured


# /v1/analytics/stocks: turnover_grade вне enum не отбрасывает ответ
# (лог 2026-08-29: API вернул NO_SALES, ответ по SKU отбрасывался -> нули)

class TestAnalyticsStocksTurnoverGrade:
    def _item(self, **overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "sku": 1709707935,
            "warehouse_name": "Склад",
            "available_stock_count": 12,
        }
        payload.update(overrides)
        return payload

    def test_no_sales_value_parsed(self) -> None:
        """Реальное значение NO_SALES из лога парсится (enum)"""
        item = AnalyticsStocksResponseItem.model_validate(self._item(turnover_grade="NO_SALES"))
        assert item.turnover_grade == TurnoverGrade.NO_SALES
        assert item.turnover_grade == "NO_SALES"
        assert item.available_stock_count == 12

    def test_unknown_future_value_kept_as_str(self) -> None:
        """Неизвестное будущее значение сохраняется строкой, ответ не отбрасывается"""
        item = AnalyticsStocksResponseItem.model_validate(
            self._item(turnover_grade="SOME_FUTURE_GRADE")
        )
        assert item.turnover_grade == "SOME_FUTURE_GRADE"

    def test_known_value_is_enum(self) -> None:
        item = AnalyticsStocksResponseItem.model_validate(self._item(turnover_grade="SURPLUS"))
        assert item.turnover_grade == TurnoverGrade.SURPLUS

    def test_response_with_no_sales_item(self) -> None:
        """Полный ответ с NO_SALES валидируется целиком"""
        resp = AnalyticsStocksResponse.model_validate(
            {"items": [self._item(turnover_grade="NO_SALES")]}
        )
        assert len(resp.items) == 1
        assert resp.items[0].turnover_grade == TurnoverGrade.NO_SALES


# HTTP-клиент: retry на 5xx

class TestHttpClientRetry:
    @pytest.mark.asyncio
    async def test_retries_on_500_then_succeeds(self) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(500, text='{"code":2}')
            return httpx.Response(200, text='{"ok": true}')

        client = HTTPClient(base_url="http://test")
        client._client = httpx.AsyncClient(base_url="http://test", transport=httpx.MockTransport(handler))

        resp = await client.request("POST", "/v1/analytics/stocks", json={"skus": ["1"]})

        assert resp.status_code == 200
        assert calls == 2
        await client.close()

    @pytest.mark.asyncio
    async def test_no_retry_on_400(self) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(400, text="bad request")

        client = HTTPClient(base_url="http://test")
        client._client = httpx.AsyncClient(base_url="http://test", transport=httpx.MockTransport(handler))

        with pytest.raises(httpx.HTTPStatusError):
            await client.request("GET", "/x")
        assert calls == 1
        await client.close()


# Performance API: не более 1 активного запроса (семафор)

class TestPerformanceClientSerialization:
    @pytest.mark.asyncio
    async def test_requests_are_serialized(self) -> None:
        client = OzonPerformanceClient("cid", "secret")
        client._token = "token"
        client._token_expires_at = time.time() + 3600

        active = 0
        max_active = 0

        async def fake_request(*args: Any, **kwargs: Any) -> Any:
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1
            resp = MagicMock(spec=httpx.Response)
            resp.status_code = 200
            return resp

        client._http.request = fake_request  # type: ignore[method-assign]
        await asyncio.gather(*(client._request("GET", f"/x{i}") for i in range(4)))

        assert max_active == 1
        await client.close()


# Двухэтапный сбор остатков (товары с заказами батчами, без заказов — по одному)

class TestCollectStocksData:
    @pytest.mark.asyncio
    async def test_two_stage_with_fallback_to_zero(self, report_service: ReportService) -> None:
        """Товары с заказами идут батчем; товар без заказов — по одному, при 500 → остаток 0"""
        seller = MagicMock()

        async def fake_get_stocks(request: AnalyticsStocksRequest) -> AnalyticsStocksResponse:
            if len(request.skus) > 1:
                # батч товаров с заказами
                return AnalyticsStocksResponse(
                    items=[
                        AnalyticsStocksResponseItem(sku=int(request.skus[0]), available_stock_count=100),
                        AnalyticsStocksResponseItem(sku=int(request.skus[1]), available_stock_count=200),
                    ]
                )
            if request.skus[0] == "3":
                raise httpx.HTTPStatusError(
                    "500 Internal Server Error",
                    request=httpx.Request("POST", "http://test"),
                    response=httpx.Response(500, text='{"code":2}'),
                )
            return AnalyticsStocksResponse(
                items=[AnalyticsStocksResponseItem(sku=int(request.skus[0]), available_stock_count=50)]
            )

        seller.get_analytics_stocks = AsyncMock(side_effect=fake_get_stocks)

        request_uuid = "test-stocks-uuid"
        report_dir = f"{config.PROJECT_ROOT}/files/{request_uuid}"
        os.makedirs(report_dir, exist_ok=True)
        try:
            result = await report_service._collect_stocks_data(  # type: ignore[attr-defined]
                seller, request_uuid, product_ids=["1", "2", "3"], ordered_ids=["1", "2"]
            )
        finally:
            shutil.rmtree(report_dir, ignore_errors=True)

        rows = result.set_index("ID Товара")["Остаток (на складах)"]
        assert len(result) == 3
        assert rows[1] == 100
        assert rows[2] == 200
        assert rows[3] == 0

        # Проверяем, что батч был один и он содержал товары с заказами,
        # а товар без заказов ушёл одиночным запросом.
        sent_skus = [call.args[0].skus for call in seller.get_analytics_stocks.call_args_list]
        assert ["1", "2"] in sent_skus
        assert ["3"] in sent_skus

    @pytest.mark.asyncio
    async def test_missing_ordered_ids_uses_all_as_batch(self, report_service: ReportService) -> None:
        """Без ordered_ids (старое поведение) все товары идут батчами"""
        seller = MagicMock()

        async def fake_get_stocks(request: AnalyticsStocksRequest) -> AnalyticsStocksResponse:
            return AnalyticsStocksResponse(
                items=[
                    AnalyticsStocksResponseItem(sku=int(sku), available_stock_count=7)
                    for sku in request.skus
                ]
            )

        seller.get_analytics_stocks = AsyncMock(side_effect=fake_get_stocks)

        request_uuid = "test-stocks-uuid-batch"
        report_dir = f"{config.PROJECT_ROOT}/files/{request_uuid}"
        os.makedirs(report_dir, exist_ok=True)
        try:
            result = await report_service._collect_stocks_data(  # type: ignore[attr-defined]
                seller, request_uuid, product_ids=["1", "2", "3"]
            )
        finally:
            shutil.rmtree(report_dir, ignore_errors=True)

        rows = result.set_index("ID Товара")["Остаток (на складах)"]
        assert rows.to_dict() == {1: 7, 2: 7, 3: 7}

    def test_empty_response_yields_zero_for_all(self, report_service: ReportService) -> None:
        """Пустой ответ API не должен ронять сбор: всем товарам — остаток 0"""
        seller = MagicMock()
        seller.get_analytics_stocks = AsyncMock(return_value=AnalyticsStocksResponse(items=[]))

        request_uuid = "test-stocks-uuid-empty"
        report_dir = f"{config.PROJECT_ROOT}/files/{request_uuid}"
        os.makedirs(report_dir, exist_ok=True)
        try:
            result = asyncio.run(  # sync-обёртка для теста
                report_service._collect_stocks_data(  # type: ignore[attr-defined]
                    seller, request_uuid, product_ids=["1", "2"]
                )
            )
        finally:
            shutil.rmtree(report_dir, ignore_errors=True)

        assert set(result["ID Товара"].tolist()) == {1, 2}
        assert result["Остаток (на складах)"].sum() == 0


# Юнит-экономика: прибыль/маржинальность с учётом налога и логистики

class TestUnitEconomics:
    def _base_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "ID Товара": [1, 2],
                "Наименование": ["A", "B"],
                "Заказано, ₽": [10000.0, 4000.0],
                "Заказано, шт.": [10.0, 4.0],
                "Расход (Трафареты/Вывод в топ)": [500.0, 0.0],
            }
        )

    def test_usn_6_profit(self, report_service: ReportService) -> None:
        df = report_service._add_unit_economics_metrics(
            self._base_df(), tax_system="usn_6", logistics_cost=150.0
        )
        row_a = df.iloc[0]
        # себестоимость = 10000*0.5 = 5000; логистика = 1500; реклама = 500
        # до налога = 10000-5000-1500-500 = 3000; налог 6% от выручки = 600
        assert row_a["Прибыль, ₽"] == 2400.0
        assert row_a["Маржинальность, %"] == 24.0
        assert row_a["Средняя цена товара"] == 1000.0

    def test_cost_is_share_of_revenue(self, report_service: ReportService) -> None:
        """Себестоимость считается долей от выручки (Ozon не отдаёт её)"""
        df = report_service._add_unit_economics_metrics(
            self._base_df(), tax_system="usn_6", logistics_cost=150.0
        )
        row_b = df.iloc[1]
        # себестоимость = 4000*0.5 = 2000; логистика = 600; реклама = 0
        # до налога = 1400; налог = 240
        assert row_b["Прибыль, ₽"] == 1160.0

    def test_usn_15_tax_on_positive_base(self, report_service: ReportService) -> None:
        df = report_service._add_unit_economics_metrics(
            self._base_df(), tax_system="usn_15", logistics_cost=150.0
        )
        row_a = df.iloc[0]
        # до налога = 3000 → налог 15% = 450
        assert row_a["Прибыль, ₽"] == 2550.0

    def test_advertised_without_sales_gives_negative_profit(self, report_service: ReportService) -> None:
        """Товар с рекламными расходами без продаж — отрицательная прибыль, а не NaN"""
        df = pd.DataFrame(
            {
                "ID Товара": [1],
                "Наименование": ["A"],
                "Заказано, ₽": [0.0],
                "Заказано, шт.": [0.0],
                "Расход (Трафареты/Вывод в топ)": [700.0],
            }
        )
        result = report_service._add_unit_economics_metrics(df, "usn_6", 150.0)
        assert result.iloc[0]["Прибыль, ₽"] == -700.0
        assert pd.isna(result.iloc[0]["Маржинальность, %"])

    def test_missing_revenue_column_returns_df_unchanged(self, report_service: ReportService) -> None:
        df = pd.DataFrame({"ID Товара": [1]})
        result = report_service._add_unit_economics_metrics(df)
        assert "Прибыль, ₽" not in result.columns


# Итоговая строка «Всего»

class TestAppendTotalRow:
    def _df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "ID Товара": [1, 2],
                "Наименование": ["A", "B"],
                "Заказано, ₽": [10000.0, 4000.0],
                "Заказано, шт.": [10.0, 4.0],
                "Клики": [100.0, 50.0],
                "В корзину(всего)": [20.0, 5.0],
                "Расход (Трафареты/Вывод в топ)": [500.0, 100.0],
                "Доход (Трафареты/Вывод в топ)": [2000.0, 300.0],
                "CR в корзину, %\n(Интерес к товару)": [20.0, 10.0],
                "ДРР (всего), %": [5.0, 2.5],
                "ROMI, %": [300.0, 200.0],
                "CTR,% (Трафареты/Вывод в топ)": [2.0, 4.0],
                "CPA, ₽\n(Стоимость привлечения заказа)": [50.0, 25.0],
                "Прибыль, ₽": [2400.0, 1160.0],
                "Маржинальность, %": [24.0, 29.0],
                "Средняя цена товара": [1000.0, 1000.0],
                "Приоритет": [2, 0],
            }
        )

    def test_total_row_absolute_sums(self, report_service: ReportService) -> None:
        total = report_service._append_total_row(self._df()).iloc[-1]
        assert total["ID Товара"] == "Всего"
        assert total["Наименование"] == "—"
        assert total["Заказано, ₽"] == 14000.0
        assert total["Заказано, шт."] == 14.0
        assert total["Прибыль, ₽"] == 3560.0

    def test_total_row_ratios_recomputed_from_sums(self, report_service: ReportService) -> None:
        total = report_service._append_total_row(self._df()).iloc[-1]
        # CR в корзину: 25/150*100 = 16.67 (не сумма 30 и не среднее 15)
        assert total["CR в корзину, %\n(Интерес к товару)"] == pytest.approx(16.67)
        # ROMI: (2300-600)/600*100 = 283.33
        assert total["ROMI, %"] == pytest.approx(283.33)
        # ДРР (всего): 600/14000*100 = 4.29
        assert total["ДРР (всего), %"] == pytest.approx(4.29)
        # CPA: 600/14 = 42.86
        assert total["CPA, ₽\n(Стоимость привлечения заказа)"] == pytest.approx(42.86)
        # Маржинальность: 3560/14000*100 = 25.43
        assert total["Маржинальность, %"] == pytest.approx(25.43)

    def test_total_row_non_summable_columns_blank(self, report_service: ReportService) -> None:
        total = report_service._append_total_row(self._df()).iloc[-1]
        assert pd.isna(total["Приоритет"])
        # Средняя цена в итоге пересчитывается из выручки на единицу
        assert total["Средняя цена товара"] == 1000.0
        # CTR — средний по товарам
        assert total["CTR,% (Трафареты/Вывод в топ)"] == pytest.approx(3.0)

    def test_total_row_stays_at_bottom_after_sort(self, report_service: ReportService) -> None:
        result = report_service._append_total_row(self._df())
        sorted_df = result.sort_values(["Приоритет", "Заказано, ₽"], ascending=[False, False])
        assert sorted_df.iloc[-1]["ID Товара"] == "Всего"

    def test_empty_df_returned_unchanged(self, report_service: ReportService) -> None:
        df = pd.DataFrame()
        assert report_service._append_total_row(df).empty

    def test_missing_id_column_returned_unchanged(self, report_service: ReportService) -> None:
        df = pd.DataFrame({"A": [1]})
        assert len(report_service._append_total_row(df)) == 1


# Premium опциональный: отчёт без Performance API

class TestOptionalPremium:
    """Проверка, что отчёт работает без Performance (Premium) секретов"""

    @pytest.mark.asyncio
    async def test_unit_economics_without_performance_data(self, report_service: ReportService) -> None:
        """Без рекламных данных юнит-экономика считает рекламу как 0"""
        df = pd.DataFrame(
            {
                "ID Товара": [1, 2],
                "Наименование": ["A", "B"],
                "Заказано, ₽": [10000.0, 5000.0],
                "Заказано, шт.": [10.0, 5.0],
            }
        )
        # expense_channels пустой → ad_spend = 0
        result = report_service._add_unit_economics_metrics(df, "usn_6", 150.0)
        
        # Для товара A: revenue=10000, cost=5000, logistics=1500, ad=0
        # pre_tax = 10000-5000-1500 = 3500; tax = 600; profit = 2900
        assert result.iloc[0]["Прибыль, ₽"] == 2900.0
        assert result.iloc[0]["Маржинальность, %"] == 29.0
        
        # Для товара B: revenue=5000, cost=2500, logistics=750, ad=0
        # pre_tax = 5000-2500-750 = 1750; tax = 300; profit = 1450
        assert result.iloc[1]["Прибыль, ₽"] == 1450.0
        assert result.iloc[1]["Маржинальность, %"] == 29.0

    @pytest.mark.asyncio
    async def test_sum_channel_columns_empty_list(self, report_service: ReportService) -> None:
        """Пустой список каналов возвращает нулевую серию"""
        df = pd.DataFrame({"A": [1, 2, 3]})
        result = report_service._sum_channel_columns(df, [])
        assert len(result) == 3
        assert result.sum() == 0.0

    def test_create_report_requires_seller_secrets(self) -> None:
        """Без Seller секретов отчёт не создаётся"""
        from unittest.mock import AsyncMock
        from backend.app.models.ozon_secrets import OzonSecrets
        from backend.app.exceptions import OzonAPIError
        
        # Создаём мок секреты без seller данных
        secrets = OzonSecrets(
            user_id=1,
            performance_client_id="perf_id",
            performance_secret="perf_secret",
            seller_client_id=None,
            seller_api_key=None,
        )
        
        adapter = AsyncMock()
        adapter.get_secrets = AsyncMock(return_value=secrets)
        
        report_service = ReportService(adapter)
        
        with pytest.raises(OzonAPIError, match="Seller API secrets are required"):
            import asyncio
            asyncio.run(report_service.create_report_full_report("2026-01-01", "2026-01-07"))

    def test_create_report_without_premium_logs_warning(self) -> None:
        """Без Premium секретов отчёт создаётся, но логируется предупреждение"""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import AsyncMock, MagicMock
        from backend.app.models.ozon_secrets import OzonSecrets
        from backend.app.models.report_request import ReportRequestOzon
        
        # Создаём мок секреты с seller, но без performance
        secrets = OzonSecrets(
            user_id=1,
            performance_client_id=None,
            performance_secret=None,
            seller_client_id="seller_id",
            seller_api_key="seller_key",
        )
        
        adapter = AsyncMock()
        adapter.get_secrets = AsyncMock(return_value=secrets)
        # Ранняя валидация налоговой системы требует настроек юнит-экономики.
        adapter.get_settings = AsyncMock(
            return_value=MagicMock(tax_system="usn_6")
        )

        # Мок создания запроса отчёта
        report_request = MagicMock(spec=ReportRequestOzon)
        report_request.request_uuid = "test-uuid-123"
        adapter.create_report_request = AsyncMock(return_value=report_request)
        
        report_service = ReportService(adapter)
        
        # Используем даты в пределах 90 дней
        date_to = datetime.now(timezone.utc) - timedelta(days=1)
        date_from = date_to - timedelta(days=7)
        date_from_str = date_from.strftime("%Y-%m-%d")
        date_to_str = date_to.strftime("%Y-%m-%d")
        
        # Должно сработать без исключения
        import asyncio
        result = asyncio.run(report_service.create_report_full_report(date_from_str, date_to_str))
        
        assert result is not None
        assert adapter.create_report_request.called


# Новые Seller API методы: рейтинг, поисковые запросы, оборачиваемость

class TestNewSellerMethods:
    """Проверка новых методов клиента и сериализации Pydantic-моделей"""

    def test_product_queries_request_serialization(self) -> None:
        """Сериализация запроса поисковых запросов: skus в str, сортировка в значения enum"""
        req = ProductQueriesRequest(
            date_from="2026-08-18T00:00:00Z",
            date_to="2026-08-25T23:59:59Z",
            skus=[3548202635, "3601829240"],
            page_size=100,
            sort_by=ProductQueriesSortBy.GMV,
            sort_dir=ProductQueriesSortDir.DESC,
        )
        payload = req.model_dump(mode="json", exclude_none=True)
        assert payload["skus"] == ["3548202635", "3601829240"]
        assert payload["sort_by"] == "GMV"
        assert payload["sort_dir"] == "DESC"
        assert payload["date_from"] == "2026-08-18T00:00:00Z"

    def test_turnover_stocks_request_excludes_none(self) -> None:
        """Запрос оборачиваемости без null-полей"""
        payload = TurnoverStocksRequest(skus=[1, "2"]).model_dump(mode="json", exclude_none=True)
        assert payload == {"skus": ["1", "2"]}

    @pytest.mark.asyncio
    async def test_get_product_queries_parses_response(self) -> None:
        """Клиент корректно парсит ответ аналитики поисковых запросов"""
        seller = OzonSellerClient("cid", "key")

        async def fake_request(method: str, path: str, base_url: Any = None, headers: Any = None, **kwargs: Any) -> Any:
            assert path == "/v1/analytics/product-queries"
            resp = MagicMock(spec=httpx.Response)
            resp.json = MagicMock(
                return_value={
                    "items": [
                        {
                            "category": "Электроника",
                            "currency": "RUB",
                            "gmv": 12345.5,
                            "name": "наушники",
                            "offer_id": "art-1",
                            "position": 2.5,
                            "sku": 1,
                            "unique_search_users": 100,
                            "unique_view_users": 50,
                            "view_conversion": 0.5,
                        }
                    ],
                    "total": 1,
                    "page_count": 1,
                }
            )
            return resp

        seller._http.request = fake_request  # type: ignore[method-assign]
        result = await seller.get_product_queries(
            ProductQueriesRequest(date_from="2026-08-18T00:00:00Z", date_to="2026-08-25T23:59:59Z", skus=[1])
        )
        assert isinstance(result, ProductQueriesResponse)
        assert result.items[0].name == "наушники"
        assert result.total == 1

    @pytest.mark.asyncio
    async def test_get_rating_summary_parses_empty_groups(self) -> None:
        """Рейтинг с пустыми группами не падает"""
        seller = OzonSellerClient("cid", "key")

        async def fake_request(method: str, path: str, base_url: Any = None, headers: Any = None, **kwargs: Any) -> Any:
            assert path == "/v1/rating/summary"
            resp = MagicMock(spec=httpx.Response)
            resp.json = MagicMock(return_value={"groups": [], "premium": False, "premium_plus": False})
            return resp

        seller._http.request = fake_request  # type: ignore[method-assign]
        result = await seller.get_rating_summary()
        assert isinstance(result, RatingSummaryResponse)
        assert result.groups == []



class TestStockPlanning:
    """Расчёт дней запаса и рекомендуемой поставки"""

    def _row(self, **kw):
        from backend.app.pydantic_models.ozon.seller.response import TurnoverStocksResponseItem
        defaults = dict(sku=1, name="Товар", ads=None, current_stock=0, idc=None, idc_grade=None, turnover=None)
        defaults.update(kw)
        return TurnoverStocksResponseItem(**defaults)

    def test_recommended_stock_target(self):
        from backend.app.services.report_service import ReportService
        item = self._row(ads=10, current_stock=50)
        target = ReportService._calc_stock_recommendation(item, target_days=30, critical_days=14)
        assert target["days_of_stock"] == 5.0
        assert target["recommended_stock"] == 250.0
        assert target["needs_reorder"] is True

    def test_recommended_stock_no_sales(self):
        from backend.app.services.report_service import ReportService
        item = self._row(ads=0, current_stock=0)
        target = ReportService._calc_stock_recommendation(item, target_days=30, critical_days=14)
        assert target["days_of_stock"] is None
        assert target["recommended_stock"] is None
        assert target["needs_reorder"] is False

    def test_recommended_stock_enough(self):
        from backend.app.services.report_service import ReportService
        item = self._row(ads=2, current_stock=100)
        target = ReportService._calc_stock_recommendation(item, target_days=30, critical_days=14)
        assert target["recommended_stock"] == 0.0
        assert target["needs_reorder"] is False
