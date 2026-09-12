
import structlog
from fastapi import APIRouter, Depends

from backend.app.adapters.metrix_adapter import MetrixAdapter
from backend.app.depends.db import get_metrix_adapter_for_user
from backend.app.ozon_performance import OzonPerformanceClient
from backend.app.ozon_seller import OzonSellerClient
from backend.app.pydantic_models.secrets import SecretsResponse, SecretsUpdate
from backend.app.security import decrypt, mask


def get_secrets_router() -> APIRouter:
    router = APIRouter(prefix="/api", tags=["secrets"])
    logger = structlog.get_logger(__name__)

    @router.get("/secrets", response_model=SecretsResponse)
    async def get_secrets(db: MetrixAdapter = Depends(get_metrix_adapter_for_user)):  # noqa: B008
        """Сохранённые секреты Ozon API для текущего пользователя (маскированные)"""
        secrets = await db.get_secrets()
        if not secrets:
            return SecretsResponse()

        seller_valid = False
        performance_valid = False
        try:
            if secrets.seller_client_id and secrets.seller_api_key:
                c = OzonSellerClient(secrets.seller_client_id, secrets.seller_api_key)
                seller_valid = await c.check_connection()
                await c.close()
        except Exception:
            seller_valid = False
        try:
            if secrets.performance_client_id and secrets.performance_secret:
                c = OzonPerformanceClient(secrets.performance_client_id, secrets.performance_secret)
                performance_valid = await c.check_connection()
                await c.close()
        except Exception:
            performance_valid = False

        return SecretsResponse(
            seller_client_id=mask(secrets.seller_client_id),
            seller_api_key=mask(secrets.seller_api_key),
            performance_client_id=mask(secrets.performance_client_id),
            performance_secret=mask(secrets.performance_secret),
            seller_valid=seller_valid,
            performance_valid=performance_valid,
        )

    @router.post("/secrets", response_model=SecretsResponse)
    async def create_secrets(data: SecretsUpdate, db: MetrixAdapter = Depends(get_metrix_adapter_for_user)):  # noqa: B008
        """Создать или обновить секреты Ozon API для текущего пользователя"""
        update_data = data.model_dump(exclude_none=True)
        orm = await db.update_secrets(update_data)
        return SecretsResponse(
            seller_client_id=mask(decrypt(orm.seller_client_id)),
            seller_api_key=mask(decrypt(orm.seller_api_key)),
            performance_client_id=mask(decrypt(orm.performance_client_id)),
            performance_secret=mask(decrypt(orm.performance_secret)),
            seller_valid=False,
            performance_valid=False,
        )

    @router.put("/secrets", response_model=SecretsResponse)
    async def update_secrets(data: SecretsUpdate, db: MetrixAdapter = Depends(get_metrix_adapter_for_user)):  # noqa: B008
        """Обновить секреты Ozon API и проверить их для текущего пользователя"""
        update_data = data.model_dump(exclude_none=True)
        secrets = await db.update_secrets(update_data)

        seller_valid = False
        performance_valid = False

        if data.seller_client_id and data.seller_api_key:
            seller = OzonSellerClient(data.seller_client_id, data.seller_api_key)
            try:
                seller_valid = await seller.check_connection()
            except Exception as e:  # noqa: BLE001 — невалидные ключи не должны ронять ручку (500)
                logger.warning("Seller keys check failed", error=str(e))
                seller_valid = False
            finally:
                await seller.close()

        if data.performance_client_id and data.performance_secret:
            perf = OzonPerformanceClient(data.performance_client_id, data.performance_secret)
            try:
                performance_valid = await perf.check_connection()
            except Exception as e:  # noqa: BLE001
                logger.warning("Performance keys check failed", error=str(e))
                performance_valid = False
            finally:
                await perf.close()

        return SecretsResponse(
            seller_client_id=secrets.seller_client_id,
            seller_api_key=secrets.seller_api_key,
            performance_client_id=secrets.performance_client_id,
            performance_secret=secrets.performance_secret,
            seller_valid=seller_valid,
            performance_valid=performance_valid,
        )

    @router.delete("/secrets")
    async def delete_secrets(db: MetrixAdapter = Depends(get_metrix_adapter_for_user)):  # noqa: B008
        await db.clear_secrets()
        return {"status": "deleted"}

    return router
