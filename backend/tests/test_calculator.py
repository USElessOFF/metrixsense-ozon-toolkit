"""Тесты калькулятора плановой юнит-экономики"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.exceptions import SettingsError
from backend.app.pydantic_models.calculator import CalculatorRequest
from backend.app.services.calculator_service import CalculatorService


def _service(user_settings: Any) -> tuple[CalculatorService, MagicMock]:
    db = MagicMock()
    db.get_settings = AsyncMock(return_value=user_settings)
    return CalculatorService(db), db


def _settings(fbo: bool = True, ad_pct: float | None = 5.0, logistics: float | None = None):
    s = MagicMock()
    s.tax_system = "usn_6"
    s.fbo = fbo
    s.ad_budget_percent = ad_pct
    s.logistics_cost = logistics
    return s


class TestCalculatorManual:
    @pytest.mark.asyncio
    async def test_usn6_full_breakdown(self):
        """УСН 6%: налог с выручки; все расходы построчно"""
        svc, _ = _service(_settings(ad_pct=5.0))
        req = CalculatorRequest(
            mode="manual", purchase_price=400, sale_price=1000,
            commission_percent=10, logistics_cost=100, acquiring_percent=1.5,
        )
        result = await svc.calculate(req, seller=None)
        # расходы: комиссия 100 + эквайринг 15 + логистика 100 + реклама 50 + закупка 400 = 665
        assert result.total_costs == 665.0
        assert result.pre_tax_profit == 335.0
        assert result.tax == 60.0  # 1000 * 0.06
        assert result.profit == 275.0
        assert result.margin_percent == 27.5
        assert result.markup_percent == round(275 / 400 * 100, 2)

    @pytest.mark.asyncio
    async def test_usn15_negative_base_tax_zero(self):
        """УСН доходы-расходы: убыточная база -> налог 0"""
        svc, _ = _service(_settings(ad_pct=0.0))
        svc.db.get_settings.return_value.tax_system = "usn_15"
        req = CalculatorRequest(
            mode="manual", purchase_price=900, sale_price=1000,
            commission_percent=10, logistics_cost=100,
        )
        result = await svc.calculate(req, seller=None)
        # pre_tax = 1000 - 900 - 100 - 100 = -100 -> налог 0
        assert result.pre_tax_profit == -100.0
        assert result.tax == 0.0
        assert result.profit == -100.0

    @pytest.mark.asyncio
    async def test_manual_requires_sale_price(self):
        """Manual без цены продажи -> 422 (SettingsError)"""
        svc, _ = _service(_settings(ad_pct=5.0))
        req = CalculatorRequest(mode="manual", purchase_price=100)
        with pytest.raises(SettingsError):
            await svc.calculate(req, seller=None)

    @pytest.mark.asyncio
    async def test_ad_budget_override(self):
        """ad_budget_percent в запросе переопределяет настройку"""
        svc, _ = _service(_settings(ad_pct=5.0))
        req = CalculatorRequest(
            mode="manual", purchase_price=100, sale_price=1000,
            ad_budget_percent=20,
        )
        result = await svc.calculate(req, seller=None)
        ads_line = next(line for line in result.cost_lines if line.name == "Реклама")
        assert ads_line.amount == 200.0
        assert ads_line.source == "manual"


class TestCalculatorExisting:
    @pytest.mark.asyncio
    async def test_existing_pulls_from_api(self):
        """Existing: комиссия/логистика/цена берутся из API по SKU"""
        seller = MagicMock()
        seller.get_product_info_prices_from_sku = AsyncMock(return_value={
            "product_id": 42,
            "offer_id": "ART",
            "price": 1000.0,
            "commission_fbo_percent": 12.0,
            "commission_fbs_percent": 14.0,
            "acquiring_percent": 1.5,
            "logistics_fbo_mid": 90.0,
            "logistics_fbs_first_mile_mid": 120.0,
            "volume_weight_l": 2.0,
        })
        svc, _ = _service(_settings(fbo=True, ad_pct=5.0))
        req = CalculatorRequest(mode="existing", sku=111, purchase_price=300)
        result = await svc.calculate(req, seller=seller)
        assert result.revenue == 1000.0
        commission = next(line for line in result.cost_lines if line.name == "Комиссия Ozon")
        assert commission.amount == 120.0  # 12% FBO
        assert commission.source == "api"
        logistics = next(line for line in result.cost_lines if line.name == "Логистика")
        assert logistics.amount == 90.0

    @pytest.mark.asyncio
    async def test_existing_sku_not_found(self):
        """SKU не найден в prices API -> SettingsError"""
        seller = MagicMock()
        seller.get_product_info_prices_from_sku = AsyncMock(return_value=None)
        svc, _ = _service(_settings())
        req = CalculatorRequest(mode="existing", sku=999, purchase_price=100)
        with pytest.raises(SettingsError):
            await svc.calculate(req, seller=seller)

    @pytest.mark.asyncio
    async def test_existing_without_seller_raises(self):
        """Existing без ключей -> SettingsError"""
        svc, _ = _service(_settings())
        req = CalculatorRequest(mode="existing", sku=1, purchase_price=100)
        with pytest.raises(SettingsError):
            await svc.calculate(req, seller=None)
