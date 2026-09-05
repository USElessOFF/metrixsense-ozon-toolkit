"""Юнит-тесты для ReportService._collect_performance_data (моки API, без реальных вызовов Ozon)"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest
from numpy import nan

from backend.app.pydantic_models.ozon.performance.enums import (
    AdvObjectType,
    CampaignState,
    StatisticsRequestState,
)
from backend.app.pydantic_models.ozon.performance.request import (
    CampaignQueryParams,
    DailyStatsQueryParams,
    StatisticsRequest,
)
from backend.app.pydantic_models.ozon.performance.response import (
    Campaign,
    CampaignsList,
    StatisticsRequestID,
    StatisticsResponse,
)
from backend.app.services.report_service import ReportService


def _make_campaign(campaign_id: str, adv_type: AdvObjectType) -> Campaign:
    return Campaign(
        id=campaign_id,
        advObjectType=adv_type,
        title=f"Кампания {campaign_id}",
    )


def _make_campaigns_list(campaigns: list[Campaign]) -> CampaignsList:
    return CampaignsList(list=campaigns)


def _make_statistics_request_id(uuid: str | None = "test-uuid-123") -> StatisticsRequestID:
    return StatisticsRequestID(UUID=uuid)


def _make_statistics_response(
    uuid: str = "test-uuid-123",
    state: StatisticsRequestState = StatisticsRequestState.OK,
    error: str | None = None,
) -> StatisticsResponse:
    return StatisticsResponse(UUID=uuid, state=state, error=error)


def _make_csv_buffer(
    rows: list[dict[str, Any]],
    columns: list[str] | None = None,
    service_lines: bool = False,
) -> io.BytesIO:
    """Создать CSV-буфер (; разделитель, , десятичный).

    Args:
        rows: строки данных.
        columns: заголовки колонок.
        service_lines: имитировать формат отчётов Performance API
            (первая служебная строка под skiprows=1 и футер под skipfooter=1).
            Для CSV дневной статистики (читается без skiprows/skipfooter) — False.
    """
    if columns is None:
        columns = list(rows[0].keys()) if rows else []
    lines: list[str] = []
    if service_lines:
        lines.append("Отчёт;сформирован;автоматически")
    lines.append(";".join(columns))
    for row in rows:
        lines.append(";".join(str(row.get(col, "")) for col in columns))
    if service_lines:
        lines.append("Конец отчёта")  # футер (отбрасывается через skipfooter=1)
    data = "\n".join(lines).encode("utf-8-sig")
    return io.BytesIO(data)


def _make_zip_buffer(csv_buffers: list[io.BytesIO], filenames: list[str] | None = None) -> io.BytesIO:
    if filenames is None:
        filenames = [f"report_{i}.csv" for i in range(len(csv_buffers))]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for filename, csv_buffer in zip(filenames, csv_buffers):
            zf.writestr(filename, csv_buffer.getvalue())
    buffer.seek(0)
    return buffer


@pytest.fixture
def report_service() -> ReportService:
    adapter = MagicMock()
    return ReportService(adapter)


def _prepare_report_dir(tmp_path) -> str:
    from backend.app import config as app_config
    request_uuid = tmp_path.name
    folder = Path(app_config.PROJECT_ROOT) / "files" / request_uuid
    folder.mkdir(parents=True, exist_ok=True)
    return request_uuid


@pytest.fixture
def mock_performance() -> AsyncMock:
    return AsyncMock()


class TestModelSerialization:
    """Проверка корректной сериализации моделей запросов"""

    def test_daily_stats_query_params_serialization(self) -> None:
        """DailyStatsQueryParams должен сериализоваться в dateFrom/dateTo/campaignIds"""
        params = DailyStatsQueryParams(
            dateFrom="2025-01-01",
            dateTo="2025-01-07",
            campaignIds=["123", "456"],
        )
        query = params.to_query_params()
        assert query == {
            "campaignIds": "123,456",
            "dateFrom": "2025-01-01",
            "dateTo": "2025-01-07",
        }

    def test_daily_stats_query_params_empty(self) -> None:
        """Пустые параметры не должны попадать в query"""
        params = DailyStatsQueryParams()
        assert params.to_query_params() == {}

    def test_campaign_query_params_serialization(self) -> None:
        """CampaignQueryParams должен сериализоваться в campaignIds/state"""
        params = CampaignQueryParams(
            campaignIds=["123", "456"],
            state=CampaignState.UNKNOWN,
        )
        query = params.to_query_params()
        assert query == {
            "campaignIds": "123,456",
            "state": "CAMPAIGN_STATE_UNKNOWN",
        }

    def test_statistics_request_serialization(self) -> None:
        """StatisticsRequest должен сериализоваться в from/to (RFC3339)"""
        request_data: dict[str, Any] = {'campaigns': ["123", "456"], 'from_': "2025-01-01T00:00:00Z", 'to': "2025-01-07T23:59:59Z"}
        request = StatisticsRequest.model_validate(request_data)
        payload = request.model_dump(exclude_none=True, by_alias=True)
        assert payload == {
            "campaigns": ["123", "456"],
            "from": "2025-01-01T00:00:00Z",
            "to": "2025-01-07T23:59:59Z",
            "groupBy": "NO_GROUP_BY"
        }


class TestCollectPerformanceData:
    """Тесты метода _collect_performance_data"""

    @pytest.mark.asyncio
    async def test_success_sku_campaign(self, report_service: ReportService, mock_performance: AsyncMock, tmp_path) -> None:
        """Успешный сценарий: SKU-кампания, CSV-отчёт"""
        daily_csv = _make_csv_buffer(
            [{"ID": "111", "Показы": "100"}, {"ID": "111", "Показы": "200"}],
            columns=["ID", "Показы"],
        )
        mock_performance.get_campaign_daily_stats_buffer.return_value = daily_csv

        mock_performance.list_campaigns.return_value = _make_campaigns_list(
            [_make_campaign("111", AdvObjectType.SKU)]
        )

        sku_csv = _make_csv_buffer(
            [
                {
                    "sku": "111",
                    "Название товара": "Товар 1",
                    "Расход, ₽, с НДС": "100,50",
                    "Выручка, ₽": "500,00",
                    "CTR (%)": "2,50",
                }
            ],
            columns=["sku", "Название товара", "Расход, ₽, с НДС", "Выручка, ₽", "CTR (%)"],
            service_lines=True,
        )
        mock_performance.submit_statistics.return_value = _make_statistics_request_id()
        mock_performance.wait_report.return_value = True
        mock_performance.download_statistics_buffer.return_value = sku_csv

        result, raw_cols = await report_service._collect_full_performance_data( # type: ignore
            mock_performance, "2025-01-01", "2025-01-07", _prepare_report_dir(tmp_path)
        )

        sku_suf = " (Трафареты/Вывод в топ)"
        assert not result.empty
        assert "ID Товара" in result.columns
        assert "Наименование" in result.columns
        assert f"Доход{sku_suf}" in result.columns
        assert f"Расход{sku_suf}" in result.columns
        assert result.iloc[0]["ID Товара"] == 111
        assert result.iloc[0]["Доход (Трафареты/Вывод в топ)"] == 500.0
        assert result.iloc[0]["Расход (Трафареты/Вывод в топ)"] == 100.5

        mock_performance.get_campaign_daily_stats_buffer.assert_called_once()
        daily_params: DailyStatsQueryParams = mock_performance.get_campaign_daily_stats_buffer.call_args[0][0]
        assert daily_params.date_from == "2025-01-01"
        assert daily_params.date_to == "2025-01-07"

        mock_performance.list_campaigns.assert_called_once()
        campaign_params: CampaignQueryParams = mock_performance.list_campaigns.call_args[0][0]
        assert campaign_params.campaign_ids == ["111"]
        assert campaign_params.state == CampaignState.UNKNOWN

        mock_performance.submit_statistics.assert_called_once()
        stats_request: StatisticsRequest = mock_performance.submit_statistics.call_args[0][0]
        assert stats_request.campaigns == ["111"]
        assert stats_request.from_ == "2025-01-01T00:00:00Z"
        assert stats_request.to == "2025-01-07T23:59:59Z"

    @pytest.mark.asyncio
    async def test_success_search_promo_campaign(self, report_service: ReportService, mock_performance: AsyncMock, tmp_path) -> None:
        """Успешный сценарий: SEARCH_PROMO-кампания"""
        daily_csv = _make_csv_buffer([{"ID": "222"}], columns=["ID"])
        mock_performance.get_campaign_daily_stats_buffer.return_value = daily_csv

        mock_performance.list_campaigns.return_value = _make_campaigns_list(
            [_make_campaign("222", AdvObjectType.SEARCH_PROMO)]
        )

        search_promo_csv = _make_csv_buffer(
            [
                {
                    "Ozon ID": "222",
                    "Наименование": "Товар 2",
                    "Цена продажи": "1000,00",
                    "Расход, ₽": "50,00",
                    "Количество": "2",
                }
            ],
            columns=["Ozon ID", "Наименование", "Цена продажи", "Расход, ₽", "Количество"],
            service_lines=True,
        )
        mock_performance.submit_statistics.return_value = _make_statistics_request_id()
        mock_performance.wait_report.return_value = True
        mock_performance.download_statistics_buffer.return_value = search_promo_csv

        result, raw_cols = await report_service._collect_full_performance_data(  # type: ignore
            mock_performance, "2025-01-01", "2025-01-07", _prepare_report_dir(tmp_path)
        )

        assert not result.empty
        assert result.iloc[0]["ID Товара"] == 222
        assert result.iloc[0]["Доход (Продвижение в поиске)"] == 2000.0  # 1000 * 2
        assert result.iloc[0]["Расход (Продвижение в поиске)"] == 50.0

    @pytest.mark.asyncio
    async def test_success_zip_report(self, report_service: ReportService, mock_performance: AsyncMock, tmp_path) -> None:
        """Успешный сценарий: ZIP-отчёт с несколькими CSV"""
        daily_csv = _make_csv_buffer([{"ID": "111"}, {"ID": "222"}], columns=["ID"])
        mock_performance.get_campaign_daily_stats_buffer.return_value = daily_csv

        mock_performance.list_campaigns.return_value = _make_campaigns_list(
            [_make_campaign("111", AdvObjectType.SKU), _make_campaign("222", AdvObjectType.SKU)]
        )

        csv1 = _make_csv_buffer(
            [{"sku": "111", "Название товара": "Товар 1", "Расход, ₽, с НДС": "10,00", "Выручка, ₽": "100,00", "CTR (%)": "1,00"}],
            columns=["sku", "Название товара", "Расход, ₽, с НДС", "Выручка, ₽", "CTR (%)"],
            service_lines=True,
        )
        csv2 = _make_csv_buffer(
            [{"sku": "222", "Название товара": "Товар 2", "Расход, ₽, с НДС": "20,00", "Выручка, ₽": "200,00", "CTR (%)": "2,00"}],
            columns=["sku", "Название товара", "Расход, ₽, с НДС", "Выручка, ₽", "CTR (%)"],
            service_lines=True,
        )
        zip_buffer = _make_zip_buffer([csv1, csv2])
        mock_performance.submit_statistics.return_value = _make_statistics_request_id()
        mock_performance.wait_report.return_value = True
        mock_performance.download_statistics_buffer.return_value = zip_buffer

        result, raw_cols = await report_service._collect_full_performance_data(  # type: ignore
            mock_performance, "2025-01-01", "2025-01-07", _prepare_report_dir(tmp_path)
        )

        assert not result.empty
        assert len(result) == 2
        assert result[result["ID Товара"] == 111].iloc[0]["Доход (Трафареты/Вывод в топ)"] == 100.0
        assert result[result["ID Товара"] == 222].iloc[0]["Доход (Трафареты/Вывод в топ)"] == 200.0

    @pytest.mark.asyncio
    async def test_empty_campaigns(self, report_service: ReportService, mock_performance: AsyncMock, tmp_path) -> None:
        """Пустой список кампаний → пустой DataFrame"""
        daily_csv = _make_csv_buffer([], columns=["ID"])
        mock_performance.get_campaign_daily_stats_buffer.return_value = daily_csv

        result, raw_cols = await report_service._collect_full_performance_data( # type: ignore
            mock_performance, "2025-01-01", "2025-01-07", _prepare_report_dir(tmp_path)
        )

        assert result.empty
        assert list(result.columns) == ["ID Товара", "Наименование", "Расход", "Доход"]
        mock_performance.list_campaigns.assert_not_called()

    @pytest.mark.asyncio
    async def test_serialize_campaigns(self, report_service: ReportService, mock_performance: AsyncMock, tmp_path) -> None:
        """ALL_SKU_PROMO кампании должны перенаправляться в группу SKU"""
        test_campaigns: list[Campaign] = [
            Campaign(id="111", advObjectType=AdvObjectType.ALL_SKU_PROMO),
            Campaign(id="222", advObjectType=AdvObjectType.SKU),
        ]

        result = report_service._serialize_campaign_to_dict_with_type(  # type: ignore
            test_campaigns
        )

        # ALL_SKU_PROMO не должно оставаться отдельным типом
        assert "ALL_SKU_PROMO" not in result
        # Обе кампании должны попасть в группу SKU
        assert result.get("SKU") == ["111", "222"]

    @pytest.mark.asyncio
    async def test_banner_campaign_is_skipped_sku_kept(self, report_service: ReportService, mock_performance: AsyncMock, tmp_path) -> None:
        """BANNER-кампания пропускается, но SKU-кампания из того же сбора сохраняется.

        Регрессия: раньше NotImplementedError для BANNER ломал всю сборку
        even если были успешно обработаны SKU-кампании.
        """
        daily_csv = _make_csv_buffer([{"ID": "111"}, {"ID": "333"}], columns=["ID"])
        mock_performance.get_campaign_daily_stats_buffer.return_value = daily_csv
        mock_performance.list_campaigns.return_value = _make_campaigns_list(
            [
                _make_campaign("111", AdvObjectType.SKU),
                _make_campaign("333", AdvObjectType.BANNER),
            ]
        )
        mock_performance.submit_statistics.return_value = _make_statistics_request_id()
        mock_performance.wait_report.return_value = True
        sku_csv = _make_csv_buffer(
            [{"sku": "111", "Название товара": "Товар 1", "Расход, ₽, с НДС": "10,00", "Выручка, ₽": "100,00", "CTR (%)": "1,00"}],
            columns=["sku", "Название товара", "Расход, ₽, с НДС", "Выручка, ₽", "CTR (%)"],
            service_lines=True,
        )
        mock_performance.download_statistics_buffer.return_value = sku_csv

        result, raw_cols = await report_service._collect_full_performance_data(  # type: ignore
            mock_performance, "2025-01-01", "2025-01-07", _prepare_report_dir(tmp_path)
        )

        # SKU-данные не должны быть потеряны из-за BANNER-кампании
        assert not result.empty
        assert result[result["ID Товара"] == 111].iloc[0]["Расход (Трафареты/Вывод в топ)"] == 10.0

    @pytest.mark.asyncio
    async def test_api_error_returns_empty(self, report_service: ReportService, mock_performance: AsyncMock, tmp_path) -> None:
        """Ошибка API → пустой DataFrame"""
        mock_performance.get_campaign_daily_stats_buffer.side_effect = Exception("API error")

        result, raw_cols = await report_service._collect_full_performance_data(  # type: ignore
            mock_performance, "2025-01-01", "2025-01-07", _prepare_report_dir(tmp_path)
        )

        assert result.empty
        assert list(result.columns) == ["ID Товара", "Наименование", "Расход", "Доход"]

    @pytest.mark.asyncio
    async def test_wait_report_not_ready(self, report_service: ReportService, mock_performance: AsyncMock, tmp_path) -> None:
        """Отчёт не готов (wait_report=False) → пустой DataFrame, скачивание не вызывается"""
        daily_csv = _make_csv_buffer([{"ID": "111"}], columns=["ID"])
        mock_performance.get_campaign_daily_stats_buffer.return_value = daily_csv
        mock_performance.list_campaigns.return_value = _make_campaigns_list(
            [_make_campaign("111", AdvObjectType.SKU)]
        )
        mock_performance.submit_statistics.return_value = _make_statistics_request_id()
        mock_performance.wait_report.return_value = False

        result, raw_cols = await report_service._collect_full_performance_data(  # type: ignore
            mock_performance, "2025-01-01", "2025-01-07", _prepare_report_dir(tmp_path)
        )

        assert result.empty
        mock_performance.download_statistics_buffer.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_uuid_returns_empty(self, report_service: ReportService, mock_performance: AsyncMock, tmp_path) -> None:
        """Отсутствие UUID в ответе → RuntimeError перехвачен → пустой DataFrame"""
        daily_csv = _make_csv_buffer([{"ID": "111"}], columns=["ID"])
        mock_performance.get_campaign_daily_stats_buffer.return_value = daily_csv
        mock_performance.list_campaigns.return_value = _make_campaigns_list(
            [_make_campaign("111", AdvObjectType.SKU)]
        )
        mock_performance.submit_statistics.return_value = _make_statistics_request_id(uuid=None)
        mock_performance.wait_report.return_value = True

        result, raw_cols = await report_service._collect_full_performance_data(  # type: ignore
            mock_performance, "2025-01-01", "2025-01-07", _prepare_report_dir(tmp_path)
        )

        assert result.empty
        mock_performance.download_statistics_buffer.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_campaigns_split_into_groups(self, report_service: ReportService, mock_performance: AsyncMock, tmp_path) -> None:
        """Более 10 кампаний → разбиение на группы по 10"""
        campaign_ids = [str(i) for i in range(1, 13)]
        daily_csv = _make_csv_buffer([{"ID": cid} for cid in campaign_ids], columns=["ID"])
        mock_performance.get_campaign_daily_stats_buffer.return_value = daily_csv
        mock_performance.list_campaigns.return_value = _make_campaigns_list(
            [_make_campaign(cid, AdvObjectType.SKU) for cid in campaign_ids]
        )

        def _make_sku_csv(cids: list[str]) -> io.BytesIO:
            rows = [
                {"sku": cid, "Название товара": f"Товар {cid}", "Расход, ₽, с НДС": "1,00", "Выручка, ₽": "10,00", "CTR (%)": "1,00"}
                for cid in cids
            ]
            return _make_csv_buffer(
                rows,
                columns=["sku", "Название товара", "Расход, ₽, с НДС", "Выручка, ₽", "CTR (%)"],
                service_lines=True,
            )

        # Моки отвечают строго по запрошенным данным (как реальный API):
        # список кампаний — по запрошенным ID, отчёт — по отправленной группе.
        requested_groups: list[list[str]] = []

        def _list_campaigns_side_effect(params: CampaignQueryParams) -> CampaignsList:
            return _make_campaigns_list([_make_campaign(cid, AdvObjectType.SKU) for cid in params.campaign_ids])

        def _submit_side_effect(request: StatisticsRequest) -> StatisticsRequestID:
            requested_groups.append(list(request.campaigns))
            return _make_statistics_request_id()

        def _download_side_effect(*_args: Any, **_kwargs: Any) -> io.BytesIO:
            return _make_sku_csv(requested_groups.pop(0))

        mock_performance.list_campaigns.side_effect = _list_campaigns_side_effect
        mock_performance.submit_statistics.side_effect = _submit_side_effect
        mock_performance.wait_report.return_value = True
        mock_performance.download_statistics_buffer.side_effect = _download_side_effect

        result, raw_cols = await report_service._collect_full_performance_data(  # type: ignore
            mock_performance, "2025-01-01", "2025-01-07", _prepare_report_dir(tmp_path)
        )

        # Должно быть 2 группы (10 + 2)
        assert mock_performance.submit_statistics.call_count == 2
        assert not result.empty
        assert len(result) == 12

    @pytest.mark.asyncio
    async def test_correction_row_in_sku_report(self, report_service: ReportService, mock_performance: AsyncMock, tmp_path) -> None:
        """Строка 'Корректировка' в SKU-отчёте должна быть обработана"""
        daily_csv = _make_csv_buffer([{"ID": "111"}], columns=["ID"])
        mock_performance.get_campaign_daily_stats_buffer.return_value = daily_csv
        mock_performance.list_campaigns.return_value = _make_campaigns_list(
            [_make_campaign("111", AdvObjectType.SKU)]
        )

        sku_csv = _make_csv_buffer(
            [
                {"sku": "111", "Название товара": "Товар 1", "Расход, ₽, с НДС": "100,00", "Выручка, ₽": "500,00", "CTR (%)": "2,00"},
                {"sku": "Корректировка", "Название товара": "", "Расход, ₽, с НДС": "10,00", "Выручка, ₽": "0,00", "CTR (%)": "0,00"},
            ],
            columns=["sku", "Название товара", "Расход, ₽, с НДС", "Выручка, ₽", "CTR (%)"],
            service_lines=True,
        )
        mock_performance.submit_statistics.return_value = _make_statistics_request_id()
        mock_performance.wait_report.return_value = True
        mock_performance.download_statistics_buffer.return_value = sku_csv

        result, raw_cols = await report_service._collect_full_performance_data(  # type: ignore
            mock_performance, "2025-01-01", "2025-01-07", _prepare_report_dir(tmp_path)
        )

        assert not result.empty
        assert len(result) == 1
        # Расход = 100 + 10 (корректировка добавлена)
        assert result.iloc[0]["Расход (Трафареты/Вывод в топ)"] == 110.0
        assert result.iloc[0]["Доход (Трафареты/Вывод в топ)"] == 500.0


class TestSearchPromoCalculation:
    """«Цена продажи» есть не у всех товаров: метод должен переживать пропуски"""

    @pytest.mark.asyncio
    async def test_missing_price_column(self, report_service: ReportService) -> None:
        """Колонка «Цена продажи» отсутствует целиком → доход 0, расход учтён"""
        df = pd.DataFrame(
            [
                {"Ozon ID": "222", "Наименование": "Товар 2", "Расход, ₽": 50.0},
            ]
        )
        result = await report_service._calculate_sum_expenditure_from_search_promo_campaign(df)  # type: ignore
        assert not result.empty
        assert result.iloc[0]["Доход"] == 0.0
        assert result.iloc[0]["Расход"] == 50.0

    @pytest.mark.asyncio
    async def test_price_with_dashes_and_blanks(self, report_service: ReportService) -> None:
        """Прочерки/пустые значения в цене → валидные строки считаются, без падений"""
        df = pd.DataFrame(
            [
                {"Ozon ID": 1, "Наименование": "A", "Цена продажи": 1000.0, "Расход, ₽": 10.0, "Количество": 2},
                {"Ozon ID": 2, "Наименование": "B", "Цена продажи": "—", "Расход, ₽": 20.0, "Количество": 5},
                {"Ozon ID": 3, "Наименование": "C", "Цена продажи": "", "Расход, ₽": 30.0, "Количество": ""},
            ]
        )
        result = await report_service._calculate_sum_expenditure_from_search_promo_campaign(df)  # type: ignore
        assert len(result) == 3
        row1 = result[result["sku"] == 1].iloc[0]
        row2 = result[result["sku"] == 2].iloc[0]
        row3 = result[result["sku"] == 3].iloc[0]
        assert float(row1["Доход"]) == 2000.0  # 1000 × 2
        assert float(row1["Ср. Цена продажи"]) == 1000.0
        assert float(row2["Доход"]) == 0.0
        assert float(row2["Расход"]) == 20.0
        assert float(row3["Доход"]) == 0.0
        assert float(row3["Расход"]) == 30.0

    @pytest.mark.asyncio
    async def test_missing_quantity_column(self, report_service: ReportService) -> None:
        """Колонка «Количество» отсутствует → доход 0 (объём неизвестен), расход учтён"""
        df = pd.DataFrame(
            [
                {"Ozon ID": "222", "Наименование": "Товар 2", "Цена продажи": 1000.0, "Расход, ₽": 50.0},
            ]
        )
        result = await report_service._calculate_sum_expenditure_from_search_promo_campaign(df)  # type: ignore
        assert not result.empty
        assert result.iloc[0]["Доход"] == 0.0
        assert result.iloc[0]["Расход"] == 50.0

    @pytest.mark.asyncio
    async def test_partial_rows_without_price(self, report_service: ReportService) -> None:
        """Смешанный отчёт: товары без цены не теряются и не роняют соседей"""
        df = pd.DataFrame(
            [
                {"Ozon ID": 1, "Наименование": "A", "Цена продажи": 500.0, "Расход, ₽": 10.0, "Количество": 1},
                {"Ozon ID": 2, "Наименование": "B", "Цена продажи": nan, "Расход, ₽": 20.0, "Количество": 3},
            ]
        )
        result = await report_service._calculate_sum_expenditure_from_search_promo_campaign(df)  # type: ignore
        assert len(result) == 2
        assert float(result[result["sku"] == 1].iloc[0]["Доход"]) == 500.0
        assert float(result[result["sku"] == 2].iloc[0]["Доход"]) == 0.0
        assert float(result[result["sku"] == 2].iloc[0]["Расход"]) == 20.0


class TestDataIntegrity:
    """Агрегатная строка «Всего» и многоканальные расходы/доходы"""

    @pytest.mark.asyncio
    async def test_seller_data_filters_totals_row(self, report_service: ReportService, tmp_path) -> None:
        """Строка «Всего» из analytics API не должна попадать в отчёт"""
        seller = MagicMock()
        df = pd.DataFrame(
            [
                {"ID Товара": "123", "Наименование": "Товар A", "Заказано, ₽": 100.0},
                {"ID Товара": 456, "Наименование": "Товар B", "Заказано, ₽": 200.0},
                {"ID Товара": "Всего", "Наименование": "—", "Заказано, ₽": 300.0},
            ]
        )
        seller.process_full_analytics_report = AsyncMock(return_value=df)

        result = await report_service._collect_full_seller_data(
            seller, "2025-01-01", "2025-01-07", _prepare_report_dir(tmp_path)
        )

        # «Всего» отфильтрована, ключ приведён к int64 (для merge со складами)
        assert list(result["ID Товара"]) == [123, 456]
        assert str(result["ID Товара"].dtype) == "int64"

    def test_sum_channel_columns_multiple_channels(self, report_service: ReportService) -> None:
        """Суммируются ВСЕ каналы расходов, а не только первый найденный"""
        df = pd.DataFrame(
            {
                "Расход (Трафареты)": [100.0, nan],
                "Расход (Продвижение в поиске)": [50.0, 70.0],
                "Доход (Трафареты)": [500.0, nan],
            }
        )
        expense = report_service._sum_channel_columns(df, [c for c in df.columns if c.startswith("Расход")])  # type: ignore
        income = report_service._sum_channel_columns(df, [c for c in df.columns if c.startswith("Доход")])  # type: ignore
        # NaN в канале = товар не рекламировался в нём → 0, а не игнор канала
        assert expense.tolist() == [150.0, 70.0]
        assert income.tolist() == [500.0, 0.0]

    def test_sum_channel_columns_empty(self, report_service: ReportService) -> None:
        """Нет рекламных колонок → нулевая серия (не ошибка)"""
        df = pd.DataFrame({"A": [1, 2]})
        result = report_service._sum_channel_columns(df, [])  # type: ignore
        assert result.tolist() == [0.0, 0.0]

    def test_merge_key_normalization_fixes_stocks_join(self, report_service: ReportService) -> None:
        """Нормализация типов ключа делает merge со складами непустым.

        Воспроизводит продовой баг: seller ID — строки, stocks ID — int64,
        без нормализации столбец остатков становился полностью NaN.
        """
        merged_df = pd.DataFrame({"ID Товара": ["111", "222"], "Наименование": ["A", "B"]})
        stocks_df = pd.DataFrame({"ID Товара": [111], "Остаток (на складах)": [5]})

        for frame in (merged_df, stocks_df):
            frame["ID Товара"] = pd.to_numeric(frame["ID Товара"], errors="coerce").fillna(-1).astype("int64")
        result = pd.merge(merged_df, stocks_df, how="left", on=["ID Товара"])

        assert result["Остаток (на складах)"].iloc[0] == 5
        assert pd.isna(result["Остаток (на складах)"].iloc[1])


class TestHelperMethods:
    """Тесты вспомогательных методов ReportService"""

    def test_to_rfc3339_from(self) -> None:
        assert ReportService._to_rfc3339("2025-01-01", is_from=True) == "2025-01-01T00:00:00Z"  # type: ignore

    def test_to_rfc3339_to(self) -> None:
        assert ReportService._to_rfc3339("2025-01-01") == "2025-01-01T23:59:59Z"  # type: ignore

    def test_serialize_campaign_to_dict_with_type(self) -> None:
        campaigns = [
            _make_campaign("111", AdvObjectType.SKU),
            _make_campaign("222", AdvObjectType.SEARCH_PROMO),
            _make_campaign("333", AdvObjectType.SKU),
        ]
        result = ReportService._serialize_campaign_to_dict_with_type(campaigns)  # type: ignore
        assert result == {
            "SKU": ["111", "333"],
            "SEARCH_PROMO": ["222"],
        }

    def test_serialize_campaign_all_sku_promo_maps_to_sku(self) -> None:
        """ALL_SKU_PROMO должна объединяться с SKU, а не оставаться отдельным типом"""
        campaigns = [
            _make_campaign("111", AdvObjectType.ALL_SKU_PROMO),
            _make_campaign("222", AdvObjectType.SKU),
            _make_campaign("333", AdvObjectType.ALL_SKU_PROMO),
        ]
        result = ReportService._serialize_campaign_to_dict_with_type(campaigns)  # type: ignore
        assert result == {"SKU": ["111", "222", "333"]}

    def test_serialize_campaign_mixed_types(self) -> None:
        """Смешанные типы кампаний группируются корректно (как в продовом логе)"""
        campaigns = [
            _make_campaign("111", AdvObjectType.SKU),
            _make_campaign("222", AdvObjectType.SEARCH_PROMO),
            _make_campaign("333", AdvObjectType.ALL_SKU_PROMO),
            _make_campaign("444", AdvObjectType.BANNER),
        ]
        result = ReportService._serialize_campaign_to_dict_with_type(campaigns)  # type: ignore
        assert result == {
            "SKU": ["111", "333"],
            "SEARCH_PROMO": ["222"],
            "BANNER": ["444"],
        }

    def test_serialize_campaign_skips_none_type(self) -> None:
        """Кампании без типа пропускаются"""
        campaign = Campaign(id="111", advObjectType=None)
        result = ReportService._serialize_campaign_to_dict_with_type([campaign])  # type: ignore
        assert result == {}

    @pytest.mark.asyncio
    async def test_extract_df_from_csv_buffer(self, report_service: ReportService) -> None:
        """Извлечение DataFrame из CSV-буфера"""
        csv_buffer = _make_csv_buffer(
            [{"sku": "111", "Название товара": "Товар 1", "Расход, ₽, с НДС": "10,00", "Выручка, ₽": "100,00", "CTR (%)": "1,00"}],
            columns=["sku", "Название товара", "Расход, ₽, с НДС", "Выручка, ₽", "CTR (%)"],
            service_lines=True,
        )
        df: pd.DataFrame = await report_service._extract_df_from_buffer_response(csv_buffer)  # type: ignore
        assert df is not None
        assert not df.empty
        assert str(df.iloc[0]["sku"]) == "111"

    @pytest.mark.asyncio
    async def test_extract_df_from_zip_buffer(self, report_service: ReportService) -> None:
        """Извлечение DataFrame из ZIP-буфера"""
        csv1 = _make_csv_buffer(
            [{"sku": "111", "Название товара": "Товар 1", "Расход, ₽, с НДС": "10,00", "Выручка, ₽": "100,00", "CTR (%)": "1,00"}],
            columns=["sku", "Название товара", "Расход, ₽, с НДС", "Выручка, ₽", "CTR (%)"],
            service_lines=True,
        )
        csv2 = _make_csv_buffer(
            [{"sku": "222", "Название товара": "Товар 2", "Расход, ₽, с НДС": "20,00", "Выручка, ₽": "200,00", "CTR (%)": "2,00"}],
            columns=["sku", "Название товара", "Расход, ₽, с НДС", "Выручка, ₽", "CTR (%)"],
            service_lines=True,
        )
        zip_buffer = _make_zip_buffer([csv1, csv2])
        df = await report_service._extract_df_from_buffer_response(zip_buffer)  # type: ignore
        assert not df.empty
        assert len(df) == 2
    
    
    def test_generate_recommendations_priority(self, report_service: ReportService) -> None:
        """Рекомендации: нет остатка -> критический (4), убыток -> высокий (3), топ-товар -> средний (2)"""
        df = pd.DataFrame(
            [
                {"Остаток (на складах)": 0, "ROMI, %": 10, "ДРР (оплаченные), %": 5, "CR в заказы, %\n(Готовность к покупке)": 1},
                {"Остаток (на складах)": 100, "ROMI, %": -5, "ДРР (оплаченные), %": 8, "CR в заказы, %\n(Готовность к покупке)": 2},
                {"Остаток (на складах)": 100, "ROMI, %": 100, "ДРР (оплаченные), %": 5, "CR в заказы, %\n(Готовность к покупке)": 3},
            ]
        )
        result = report_service._generate_recommendations(df)  # type: ignore
        assert result.columns[-2:].tolist() == ["Рекомендация", "Приоритет"]
        assert result["Приоритет"].tolist() == [4, 3, 2]

    def test_generate_recommendations_handles_nan(self, report_service: ReportService) -> None:
        """NaN/None в метриках не должны ронять генерацию рекомендаций (приоритет 0)"""
        df = pd.DataFrame(
            [
                {"Остаток (на складах)": None, "ROMI, %": None, "ДРР (оплаченные), %": None, "CR в заказы, %\n(Готовность к покупке)": None}
            ]
        )
        result = report_service._generate_recommendations(df)  # type: ignore
        assert result.iloc[0]["Приоритет"] == 0
        assert result.iloc[0]["Рекомендация"] == "Без действий"

    def test_generate_recommendations_idempotent(self, report_service: ReportService) -> None:
        """Повторный вызов не должен перезаписывать уже созданные колонки"""
        df = pd.DataFrame(
            [{"Остаток (на складах)": 0, "ROMI, %": 1, "ДРР (оплаченные), %": 1, "CR в заказы, %\n(Готовность к покупке)": 1}]
        )
        first = report_service._generate_recommendations(df)  # type: ignore
        second = report_service._generate_recommendations(first)  # type: ignore
        assert second["Приоритет"].tolist() == first["Приоритет"].tolist()

    def test_add_benchmarks_creates_deviation_columns(self, report_service: ReportService) -> None:
        """Бенчмаркинг должен добавлять колонки отклонения от среднего по магазину"""
        df = pd.DataFrame(
            {"ДРР (оплаченные), %": [10.0, 30.0], "CR в заказы, %\n(Готовность к покупке)": [2.0, 6.0]}
        )
        result = report_service._add_benchmarks(df)  # type: ignore
        assert "ДРР (отклонение от среднего, п.п.)" in result.columns
        assert "CR в заказы (отклонение от среднего, п.п.)" in result.columns
        assert result["ДРР (отклонение от среднего, п.п.)"].iloc[0] == -10.0

    def test_add_z_scores(self, report_service: ReportService) -> None:
        """Z-оценка рассчитывается и имеет нулевое среднее для колонки без пропусков"""
        df = pd.DataFrame({"ROMI, %": [1.0, 1.0, 2.0]})
        result = report_service._add_z_scores(df, ["ROMI, %"])  # type: ignore
        assert "ROMI, % (Z-Score)" in result.columns
        assert round(result["ROMI, % (Z-Score)"].mean(), 2) == 0.0

    def test_apply_conditional_format_skips_missing_column(self, report_service: ReportService) -> None:
        """Хелпер не должен вызывать conditional_format для отсутствующей колонки"""
        df = pd.DataFrame({"A": [1, 2]})
        ws = MagicMock()
        wb = MagicMock()
        report_service._apply_conditional_format(df, ws, wb, "NO_SUCH_COL", "3_color_scale")  # type: ignore
        ws.conditional_format.assert_not_called()

    def test_apply_conditional_format_cell(self, report_service: ReportService) -> None:
        """Хелпер применяет cell-формат для корректной колонки"""
        df = pd.DataFrame({"ДРР (оплаченные), %": [1.0, 2.0]})
        ws = MagicMock()
        wb = MagicMock()
        report_service._apply_conditional_format(df, ws, wb, "ДРР (оплаченные), %", "cell", op=">", value=30)  # type: ignore
        ws.conditional_format.assert_called_once()
        wb.add_format.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_full_report_to_xlsx_v2_with_decision_columns(self, report_service: ReportService, tmp_path) -> None:
        """Полное форматирование не падает с новыми колонками (рекомендация/приоритет/бенчмарк)"""
        df = pd.DataFrame(
            {
                "ID Товара": [1, 2],
                "Заказано, ₽": [300, 100],
                "ROMI, %": [100, -10],
                "ДРР (оплаченные), %": [5, 9],
                "ДРР (продвижение), %": [6, 10],
                "ДРР (всего), %": [5, 10],
                "Остаток (на складах)": [5, 0],
                "CR в заказы, %\n(Готовность к покупке)": [2, 0],
                "Клики": [10, 10],
            }
        )
        report_service._generate_recommendations(df)  # type: ignore
        report_service._add_benchmarks(df)  # type: ignore
        report_service._add_z_scores(df, ["ROMI, %", "ДРР (оплаченные), %"])  # type: ignore
        path = tmp_path / "report"
        await report_service.format_full_report_to_xlsx_v2(df, str(path))  # type: ignore
        assert path.with_suffix(".xlsx").exists()
