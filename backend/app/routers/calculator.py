"""Калькулятор плановой юнит-экономики"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException

from backend.app.adapters.metrix_adapter import MetrixAdapter
from backend.app.depends.db import get_metrix_adapter_for_user
from backend.app.exceptions import SettingsError
from backend.app.ozon_seller import OzonSellerClient
from backend.app.pydantic_models.calculator import CalculatorRequest, CalculatorResult
from backend.app.services.calculator_service import CalculatorService

logger = structlog.get_logger(__name__)


def get_calculator_router() -> APIRouter:
    router = APIRouter(prefix="/api", tags=["calculator"])

    @router.post("/calculator", response_model=CalculatorResult)
    async def calculate_unit_economics(
        body: CalculatorRequest,
        db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
    ) -> CalculatorResult:
        """Маржа до закупки: разбор расходов, налог, прибыль (existing — по SKU из API, manual — вручную)"""
        service = CalculatorService(db)
        seller: OzonSellerClient | None = None
        try:
            if body.mode == "existing":
                secrets = await db.get_secrets()
                if not (secrets and secrets.seller_client_id and secrets.seller_api_key):
                    raise HTTPException(
                        status_code=400,
                        detail="Seller API ключи не настроены — сохраните их или используйте manual режим",
                    )
                seller = OzonSellerClient(secrets.seller_client_id, secrets.seller_api_key)
            return await service.calculate(body, seller)
        except SettingsError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Calculator failed", mode=body.mode, sku=body.sku, error=str(e))
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            if seller is not None:
                await seller.close()

    return router
