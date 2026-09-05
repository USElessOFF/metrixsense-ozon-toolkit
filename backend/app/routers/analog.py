"""Поиск аналогов товаров"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.adapters.metrix_adapter import MetrixAdapter
from backend.app.depends.db import get_metrix_adapter_for_user
from backend.app.depends.ozon import get_ozon_seller_client
from backend.app.pydantic_models.analog import AnalogsResponse
from backend.app.services.analog_finder import AnalogFinderService

logger = structlog.get_logger(__name__)


def get_analog_router() -> APIRouter:
    router = APIRouter(prefix="/api", tags=["analog-finder"])

    @router.get("/analogs", response_model=AnalogsResponse)
    async def get_analogs(
        sku: int = Query(..., description="SKU товара, для которого ищем аналоги."),
        top: int = Query(default=10, ge=1, le=50, description="Сколько аналогов вернуть."),
        min_similarity: float = Query(default=0.1, ge=0.0, le=1.0, description="Минимальная близость названий."),
        seller=Depends(get_ozon_seller_client),  # noqa: B008
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> AnalogsResponse:
        """Похожие товары каталога: TF-IDF по названиям + цена аналога"""
        service = AnalogFinderService(db)
        try:
            return await service.find_analogs(seller, sku=sku, top_n=top, min_similarity=min_similarity)
        except Exception as e:
            logger.error("Analog finder failed", sku=sku, error=str(e))
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            await seller.close()

    return router
