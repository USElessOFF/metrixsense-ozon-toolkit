"""Тесты агрегированных Top-действий"""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.app.services.top_actions import TopActionsService, _parse_range_min


class TestParseRangeMin:
    def test_parse_en_dash(self):
        assert _parse_range_min("123.45\u2013200.0") == 123.45

    def test_parse_none_and_garbage(self):
        assert _parse_range_min(None) is None
        assert _parse_range_min("abc") is None


class TestHighCosts:
    def _prices(self, rows):
        section = MagicMock()
        section.data = rows
        return section

    def _row(self, product_id=1, price=1000.0, commission=10.0, acquiring=1.5, logistics_range="100.0\u2013200.0"):
        row = MagicMock()
        row.product_id = product_id
        row.price = price
        row.commission_fbo_percent = commission
        row.acquiring_percent = acquiring
        row.logistics_fbo_range = logistics_range
        return row

    def test_heavy_cost_detected(self):
        """Расходы > 45% цены попадают в действие"""
        svc = TopActionsService(MagicMock())
        # 10% + 1.5% = 115 руб + логистика 100 = 215/1000 = 21.5% — не должно
        ok = self._row(product_id=1, price=1000, commission=10, logistics_range="100.0\u2013200.0")
        # 30% = 300 + логистика 200 = 500/1000 = 50% — должно
        heavy = self._row(product_id=2, price=1000, commission=30, logistics_range="200.0\u2013300.0")
        actions = svc._high_costs_action(self._prices([ok, heavy]))
        assert len(actions) == 1
        assert actions[0].action_type == "high_costs"
        assert actions[0].skus == [2]

    def test_sorted_by_worst_share(self):
        svc = TopActionsService(MagicMock())
        rows = [
            self._row(product_id=1, price=1000, commission=50, logistics_range="200.0\u2013300.0"),
            self._row(product_id=2, price=1000, commission=46, logistics_range="200.0\u2013300.0"),
        ]
        actions = svc._high_costs_action(self._prices(rows))
        assert actions[0].skus[0] == 1  # худшая доля — первой


class TestStockActions:
    def _planning(self, rows):
        section = MagicMock()
        section.data = rows
        section.generated_at = MagicMock()
        return section

    def _prow(self, sku=1, current_stock=10, ads=2.0, priority="critical", due_by="2026-09-15", units=100):
        row = MagicMock()
        row.sku = sku
        row.current_stock = current_stock
        row.ads = ads
        row.priority = priority
        row.due_by = due_by
        row.recommended_units = units
        row.needs_reorder = priority in ("critical", "low")
        return row

    def test_restock_action_critical_only(self):
        svc = TopActionsService(MagicMock())
        rows = [
            self._prow(sku=1, priority="critical", units=100),
            self._prow(sku=2, priority="normal", units=0),
        ]
        actions = svc._stock_actions(self._planning(rows))
        restock = next(a for a in actions if a.action_type == "restock")
        assert restock.sku_count == 1
        assert restock.impact == "Рекомендуется отгрузить 100 шт"

    def test_dead_stock_action(self):
        svc = TopActionsService(MagicMock())
        rows = [
            self._prow(sku=1, current_stock=50, ads=0.0, priority="no-velocity", units=0),
            self._prow(sku=2, current_stock=0, ads=3.0, priority="critical", units=90),
        ]
        actions = svc._stock_actions(self._planning(rows))
        dead = next(a for a in actions if a.action_type == "dead_stock")
        assert dead.sku_count == 1
        assert dead.impact == "Заморожено 50 шт"
