from __future__ import annotations

import structlog

from backend.app.adapters.metrix_adapter import MetrixAdapter
from backend.app.ozon_seller import OzonSellerClient
from backend.app.pydantic_models.top_actions import TopActionItem, TopActionsRequest, TopActionsResponse
from backend.app.services.report_service import ReportService

logger = structlog.get_logger(__name__)

_PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _parse_range_min(range_str: str | None) -> float | None:
    """min из строки формата '123.45–200.0'"""
    if not range_str:
        return None
    try:
        return float(range_str.split("\u2013")[0].strip())
    except ValueError:
        return None


class TopActionsService:
    def __init__(self, db: MetrixAdapter):
        self.db = db
        self.report = ReportService(db)

    async def get_top_actions(
        self, seller: OzonSellerClient, request: TopActionsRequest
    ) -> TopActionsResponse:
        actions: list[TopActionItem] = []

        planning = await self.report.get_stock_planning_section(seller)
        actions.extend(self._stock_actions(planning))

        prices = await self.report.get_prices_commissions_section(seller)
        actions.extend(self._high_costs_action(prices))

        if request.date_from and request.date_to:
            queries = await self.report.get_search_queries_section(
                seller, request.date_from, request.date_to
            )
            actions.extend(self._search_action(queries))

        actions.sort(key=lambda a: _PRIORITY_RANK.get(a.priority, 9))

        response = TopActionsResponse(
            section="top_actions",
            generated_at=planning.generated_at,
            row_count=len(actions),
            actions=actions,
        )
        logger.info(
            "::top_actions built",
            actions=[{"type": a.action_type, "priority": a.priority, "sku_count": a.sku_count} for a in actions],
        )
        return response

    def _stock_actions(self, planning) -> list[TopActionItem]:
        actions: list[TopActionItem] = []
        critical = [row for row in planning.data if row.priority == "critical"]
        if critical:
            units = sum(row.recommended_units or 0 for row in critical)
            actions.append(
                TopActionItem(
                    action_type="restock",
                    title=f"Критический остаток у {len(critical)} товаров — пополните",
                    priority="critical",
                    sku_count=len(critical),
                    skus=[row.sku for row in critical if row.sku is not None][:20],
                    impact=f"Рекомендуется отгрузить {units} шт",
                    details={
                        "total_units_to_ship": units,
                        "due_by": sorted([row.due_by for row in critical if row.due_by])[:3],
                    },
                )
            )

        dead = [
            row
            for row in planning.data
            if (row.current_stock or 0) > 0 and (row.ads is None or row.ads == 0)
        ]
        if dead:
            frozen_units = sum(row.current_stock or 0 for row in dead)
            actions.append(
                TopActionItem(
                    action_type="dead_stock",
                    title=f"{len(dead)} товаров без продаж — замороженный остаток",
                    priority="medium",
                    sku_count=len(dead),
                    skus=[row.sku for row in dead if row.sku is not None][:20],
                    impact=f"Заморожено {frozen_units} шт",
                    details={"frozen_units": frozen_units},
                )
            )
        return actions

    def _high_costs_action(self, prices) -> list[TopActionItem]:
        heavy = []
        for row in prices.data:
            if not row.price or row.price <= 0:
                continue
            logistics_min = _parse_range_min(row.logistics_fbo_range)
            commission = ((row.commission_fbo_percent or 0) + (row.acquiring_percent or 0)) / 100 * row.price
            costs = commission + (logistics_min or 0)
            share = costs / row.price
            if share > 0.45:
                heavy.append((row.product_id, row.price, round(share * 100, 1)))
        if not heavy:
            return []
        heavy.sort(key=lambda x: x[2], reverse=True)
        worst_share = heavy[0][2]
        return [
            TopActionItem(
                action_type="high_costs",
                title=f"Расходы Ozon съедают до {worst_share}% цены у {len(heavy)} товаров",
                priority="high",
                sku_count=len(heavy),
                skus=[pid for pid, _, _ in heavy[:20]],
                impact="Пересмотрите цену или схему продажи",
                details={"sku_share": {str(pid): share for pid, _, share in heavy[:20]}},
            )
        ]

    def _search_action(self, queries) -> list[TopActionItem]:
        potential = [
            row for row in queries.data
            if (row.unique_search_users or 0) >= 50 and not row.gmv
        ]
        if not potential:
            return []
        potential.sort(key=lambda r: r.unique_search_users or 0, reverse=True)
        total_searches = sum(row.unique_search_users or 0 for row in potential)
        return [
            TopActionItem(
                action_type="search_no_sales",
                title=f"Спрос есть, продаж нет: {len(potential)} поисковых фраз",
                priority="medium",
                sku_count=len({row.sku for row in potential if row.sku is not None}),
                skus=sorted({row.sku for row in potential if row.sku is not None})[:20],
                impact=f"{total_searches} поисков без единого заказа",
                details={
                    "total_searches": total_searches,
                    "top_phrases": [row.phrase for row in potential[:10] if row.phrase],
                },
            )
        ]
