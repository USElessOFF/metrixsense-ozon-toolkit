"""Отчёты: полный, статус, секции"""

from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from backend.app import config

from backend.app.adapters.metrix_adapter import MetrixAdapter
from backend.app.depends.db import get_metrix_adapter_for_user
from backend.app.depends.ozon import get_ozon_seller_client
from backend.app.exceptions import CircuitOpenError, SettingsError
from backend.app.ozon_seller import OzonSellerClient
from backend.app.pydantic_models.report_sections import (
    FinanceExpensesSectionResponse,
    PricesCommissionsSectionResponse,
    ProductCardsSectionResponse,
    SellerRatingSectionResponse,
    CashFlowSectionResponse,
    SearchQueriesSectionResponse,
    StockPlanningSectionResponse,
)
from backend.app.pydantic_models.reports import (
    CreatedReportResponse,
    ProductCardsRequest,
    ReportRequest,
    ReportStatusResponse,
)
from backend.app.pydantic_models.top_actions import TopActionsRequest, TopActionsResponse
from backend.app.services.report_service import ReportService
from backend.app.services.top_actions import TopActionsService

logger = structlog.get_logger(__name__)


def _http_status(exc: Exception) -> int:
    """Настройки → 422, предохранитель → 503, остальное → 400"""
    if isinstance(exc, SettingsError):
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    if isinstance(exc, CircuitOpenError):
        return status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_400_BAD_REQUEST


def get_reports_router() -> APIRouter:
    router = APIRouter(prefix="/api/reports", tags=["reports"])

    @router.post(
        "/full",
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_full_report(
        data: ReportRequest,
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> CreatedReportResponse:
        """Создать полный отчёт"""
        service = ReportService(db)
        try:
            report_request = await service.create_report_full_report(data.date_from, data.date_to)
        except SettingsError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            logger.error("Report creation failed", error=str(e))
            raise HTTPException(status_code=400, detail=str(e))
        return CreatedReportResponse.model_validate(report_request, from_attributes=True)

    # Секции: синхронные блоки для веба, DI-клиент на запрос

    @router.get(
        "/sections/prices-commissions",
        response_model=PricesCommissionsSectionResponse,
    )
    async def get_prices_commissions(
        seller: OzonSellerClient = Depends(get_ozon_seller_client),  # noqa: B008
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> PricesCommissionsSectionResponse:
        """Цены и комиссии Ozon по товарам (/v5/product/info/prices)"""
        service = ReportService(db)
        try:
            return await service.get_prices_commissions_section(seller)
        except Exception as e:
            logger.error("Prices/commissions section failed", error=str(e))
            raise HTTPException(status_code=_http_status(e), detail=str(e))

    @router.post(
        "/sections/product-cards",
        response_model=ProductCardsSectionResponse,
    )
    async def get_product_cards(
        body: ProductCardsRequest | None = None,
        seller: OzonSellerClient = Depends(get_ozon_seller_client),  # noqa: B008
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> ProductCardsSectionResponse:
        """Карточки товаров: комиссии, объёмный вес, цены (/v3/product/info/list)"""
        service = ReportService(db)
        try:
            sku_list = body.sku if body else None
            return await service.get_product_cards_section(seller, sku_list)
        except Exception as e:
            logger.error("Product cards section failed", error=str(e))
            raise HTTPException(status_code=_http_status(e), detail=str(e))

    @router.post(
        "/sections/finance-expenses",
        response_model=FinanceExpensesSectionResponse,
    )
    async def get_finance_expenses(
        data: ReportRequest,
        seller: OzonSellerClient = Depends(get_ozon_seller_client),  # noqa: B008
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> FinanceExpensesSectionResponse:
        """Финансовые начисления по отправлениям (/v3/finance/transaction/list + totals)"""
        service = ReportService(db)
        try:
            return await service.get_finance_expenses_section(
                seller, data.date_from, data.date_to
            )
        except Exception as e:
            logger.error("Finance expenses section failed", error=str(e))
            raise HTTPException(status_code=_http_status(e), detail=str(e))

    @router.get(
        "/sections/seller-rating",
        response_model=SellerRatingSectionResponse,
    )
    async def get_seller_rating(
        seller: OzonSellerClient = Depends(get_ozon_seller_client),  # noqa: B008
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> SellerRatingSectionResponse:
        """Рейтинг продавца (/v1/rating/summary)"""
        service = ReportService(db)
        try:
            return await service.get_seller_rating_section(seller)
        except Exception as e:
            logger.error("Seller rating section failed", error=str(e))
            raise HTTPException(status_code=_http_status(e), detail=str(e))

    @router.get(
        "/sections/stocks",
        response_model=StockPlanningSectionResponse,
    )
    async def get_stock_planning(
        seller: OzonSellerClient = Depends(get_ozon_seller_client),  # noqa: B008
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> StockPlanningSectionResponse:
        """Планирование поставок: остатки, дни запаса, рекомендуемая поставка (/v1/analytics/turnover/stocks)"""
        service = ReportService(db)
        try:
            return await service.get_stock_planning_section(seller)
        except Exception as e:
            logger.error("Stock planning section failed", error=str(e))
            raise HTTPException(status_code=_http_status(e), detail=str(e))

    @router.post(
        "/sections/search-queries",
        response_model=SearchQueriesSectionResponse,
    )
    async def get_search_queries(
        data: ReportRequest,
        seller: OzonSellerClient = Depends(get_ozon_seller_client),  # noqa: B008
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> SearchQueriesSectionResponse:
        """Поисковые фразы: показы, позиции, конверсии (/v1/analytics/product-queries)"""
        service = ReportService(db)
        try:
            return await service.get_search_queries_section(
                seller, data.date_from, data.date_to
            )
        except Exception as e:
            logger.error("Search queries section failed", error=str(e))
            raise HTTPException(status_code=_http_status(e), detail=str(e))

    @router.post(
        "/sections/cashflow",
        response_model=CashFlowSectionResponse,
    )
    async def get_cashflow(
        data: ReportRequest,
        seller: OzonSellerClient = Depends(get_ozon_seller_client),  # noqa: B008
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> CashFlowSectionResponse:
        """ДДС-журнал: все операции периода, приход/расход, бегущий баланс"""
        service = ReportService(db)
        try:
            return await service.get_cashflow_section(
                seller, data.date_from, data.date_to
            )
        except Exception as e:
            logger.error("Cashflow section failed", error=str(e))
            raise HTTPException(status_code=_http_status(e), detail=str(e))

    @router.post(
        "/top-actions",
        response_model=TopActionsResponse,
    )
    async def get_top_actions(
        body: TopActionsRequest | None = None,
        seller: OzonSellerClient = Depends(get_ozon_seller_client),  # noqa: B008
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> TopActionsResponse:
        """Агрегированные действия: остатки, замороженный сток, дорогие расходы, спрос без продаж"""
        service = TopActionsService(db)
        try:
            return await service.get_top_actions(
                seller, body or TopActionsRequest()
            )
        except Exception as e:
            logger.error("Top actions failed", error=str(e))
            raise HTTPException(status_code=400, detail=str(e))

    # /requests/ — от коллизий с /sections/*
    @router.get(
        "/requests/latest",
        response_model=ReportStatusResponse,
    )
    async def get_latest_report_status(
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> ReportStatusResponse:
        """Последний отчётный запрос пользователя — UI восстанавливает статус после перезагрузки"""
        service = ReportService(db)
        report = await service.get_latest_report()
        if report is None:
            raise HTTPException(status_code=404, detail="No report requests yet")
        return ReportStatusResponse.model_validate(report, from_attributes=True)

    @router.get(
        "/requests/{request_id}",
        response_model=ReportStatusResponse,
    )
    async def get_report_status(
        request_id: str,
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> ReportStatusResponse:
        """Статус отчёта"""
        service = ReportService(db)
        report = await service.get_report(request_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        return ReportStatusResponse.model_validate(report, from_attributes=True)

    @router.get(
        "/requests",
        response_model=list[ReportStatusResponse],
    )
    async def list_reports(
        limit: int = 20,
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> list[ReportStatusResponse]:
        """Последние отчёты пользователя (новые сверху) — для истории в UI"""
        service = ReportService(db)
        reports = await service.list_reports(min(limit, 100))
        return [ReportStatusResponse.model_validate(r, from_attributes=True) for r in reports]

    @router.get(
        "/requests/{request_id}/download",
    )
    async def download_report(
        request_id: str,
        fmt: str = "xlsx",
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> FileResponse:
        """Скачать готовый отчёт (xlsx или csv); файл отдаётся только владельцу"""
        service = ReportService(db)
        report = await service.get_report(request_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        if report.status != "completed":
            raise HTTPException(status_code=409, detail="Report is not completed yet")
        fmt = fmt.lower()
        if fmt not in {"xlsx", "csv"}:
            raise HTTPException(status_code=422, detail="fmt must be xlsx or csv")
        path = Path(config.PROJECT_ROOT) / "files" / request_id / f"full_report.{fmt}"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Report file not found")
        return FileResponse(
            path,
            filename=f"metrixsense_report_{request_id[:8]}.{fmt}",
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if fmt == "xlsx"
                else "text/csv"
            ),
        )

    @router.get(
        "/requests/{request_id}/data",
        response_model=list[dict],
    )
    async def get_report_data(
        request_id: str,
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> list[dict]:
        """Данные готового отчёта (строки unit-экономики) — для сравнения в UI"""
        service = ReportService(db)
        report = await service.get_report(request_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        if report.status != "completed":
            raise HTTPException(status_code=409, detail="Report is not completed yet")
        data = await service.get_report_data(request_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Report data not found")
        return data

    return router
