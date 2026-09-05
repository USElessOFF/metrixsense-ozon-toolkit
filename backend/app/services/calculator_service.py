from __future__ import annotations

import structlog

from backend.app.adapters.metrix_adapter import MetrixAdapter
from backend.app.exceptions import SettingsError
from backend.app.ozon_seller import OzonSellerClient
from backend.app.pydantic_models.calculator import (
    CalculatorCostLine,
    CalculatorRequest,
    CalculatorResult,
)
from backend.app.tax import INCOME_MINUS_EXPENSE_SYSTEMS, get_tax_rate

logger = structlog.get_logger(__name__)


class CalculatorService:
    def __init__(self, db: MetrixAdapter):
        self.db = db

    async def calculate(
        self,
        request: CalculatorRequest,
        seller: OzonSellerClient | None,
    ) -> CalculatorResult:
        user_settings = await self.db.get_settings()
        tax_system = user_settings.tax_system
        tax_rate = get_tax_rate(tax_system)
        warnings: list[str] = []
        source: dict = {}

        if request.mode == "existing":
            if seller is None:
                raise SettingsError("Seller API keys required for existing mode")
            source = await seller.get_product_info_prices_from_sku(request.sku)
            if source is None:
                raise SettingsError(f"Product {request.sku} not found in prices API")

        sale_price, sale_source = self._resolve_sale_price(request, source, warnings)
        commission_pct, commission_src = self._resolve_commission(request, source, user_settings, sale_price, warnings)
        acquiring_pct = self._resolve_acquiring(request, source)
        logistics, logistics_src = self._resolve_logistics(request, source, user_settings, warnings)
        ad_pct, ad_src = self._resolve_ad_budget(request, user_settings)

        revenue = sale_price
        lines: list[CalculatorCostLine] = []
        self._add_line(lines, "Комиссия Ozon", revenue * commission_pct / 100, commission_src)
        acquiring_src = (
            "api"
            if (request.mode == "existing" and request.acquiring_percent is None and source.get("acquiring_percent") is not None)
            else "manual"
        )
        self._add_line(lines, "Эквайринг", revenue * acquiring_pct / 100, acquiring_src)
        self._add_line(lines, "Логистика", logistics, logistics_src)
        self._add_line(lines, "Реклама", revenue * ad_pct / 100, ad_src)
        self._add_line(lines, "Закупка", request.purchase_price, "manual")

        total_costs = sum(line.amount for line in lines)
        pre_tax = revenue - total_costs
        if tax_system in INCOME_MINUS_EXPENSE_SYSTEMS:
            tax = max(0.0, pre_tax) * tax_rate
        else:
            tax = revenue * tax_rate
        profit = pre_tax - tax
        margin = (profit / revenue * 100) if revenue > 0 else 0.0
        markup = (profit / request.purchase_price * 100) if request.purchase_price > 0 else 0.0

        result = CalculatorResult(
            mode=request.mode,
            sku=request.sku,
            revenue=round(revenue, 2),
            cost_lines=lines,
            total_costs=round(total_costs, 2),
            pre_tax_profit=round(pre_tax, 2),
            tax=round(tax, 2),
            tax_system=tax_system,
            profit=round(profit, 2),
            margin_percent=round(margin, 2),
            markup_percent=round(markup, 2),
            warnings=warnings,
        )
        logger.info(
            "::calculate_unit_economics",
            mode=request.mode,
            sku=request.sku,
            revenue=result.revenue,
            total_costs=result.total_costs,
            profit=result.profit,
            margin=result.margin_percent,
            cost_lines=[line.model_dump() for line in result.cost_lines],
        )
        return result

    def _resolve_sale_price(
        self, request: CalculatorRequest, source: dict, warnings: list[str]
    ) -> tuple[float, str]:
        if request.sale_price is not None:
            api_price = source.get("price")
            if api_price is not None and api_price != request.sale_price:
                warnings.append(f"Указана своя цена продажи (в API: {api_price})")
            return request.sale_price, "manual"
        api_price = source.get("price")
        if api_price is None:
            raise SettingsError("Укажите sale_price — цена продажи не найдена в API")
        return api_price, "api"

    def _resolve_commission(
        self, request: CalculatorRequest, source: dict, user_settings, sale_price: float, warnings: list[str]
    ) -> tuple[float, str]:
        if request.commission_percent is not None:
            return request.commission_percent, "manual"
        api_pct = (
            source.get("commission_fbo_percent")
            if user_settings.fbo
            else source.get("commission_fbs_percent")
        )
        if api_pct is not None:
            return api_pct, "api"
        warnings.append("Комиссия Ozon не найдена — принята 0%")
        return 0.0, "default"

    def _resolve_acquiring(self, request: CalculatorRequest, source: dict) -> float:
        if request.acquiring_percent is not None:
            return request.acquiring_percent
        return source.get("acquiring_percent") or 0.0

    def _resolve_logistics(self, request: CalculatorRequest, source: dict, user_settings, warnings: list[str]) -> tuple[float, str]:
        if request.logistics_cost is not None:
            return request.logistics_cost, "manual"
        api_log = (
            source.get("logistics_fbo_mid")
            if user_settings.fbo
            else source.get("logistics_fbs_first_mile_mid")
        )
        if api_log is not None:
            return api_log, "api"
        if user_settings.logistics_cost is not None:
            warnings.append(f"Логистика из API недоступна — использована настройка ({user_settings.logistics_cost} ₽)")
            return user_settings.logistics_cost, "settings"
        warnings.append("Логистика не указана и настройки нет — принята 0 ₽")
        return 0.0, "default"

    def _resolve_ad_budget(self, request: CalculatorRequest, user_settings) -> tuple[float, str]:
        if request.ad_budget_percent is not None:
            return request.ad_budget_percent, "manual"
        if user_settings.ad_budget_percent is not None:
            return user_settings.ad_budget_percent, "settings"
        return 0.0, "default"

    @staticmethod
    def _add_line(lines: list[CalculatorCostLine], name: str, amount: float, source: str) -> None:
        if amount:
            lines.append(CalculatorCostLine(name=name, amount=round(amount, 2), source=source))
