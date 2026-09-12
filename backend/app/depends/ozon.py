"""DI-зависимости клиентов Ozon API.

Клиент создаётся на время HTTP-запроса (каждому роут-хэндлеру — свой),
закрытие соединения гарантировано через ``finally`` в генераторе.
Кэш AnalyticsCache хранит только данные, никогда — инфраструктурные объекты.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import structlog
from fastapi import Depends, HTTPException, status

from backend.app.adapters.metrix_adapter import MetrixAdapter
from backend.app.depends.db import get_metrix_adapter_for_user
from backend.app.ozon_seller import OzonSellerClient

logger = structlog.get_logger(__name__)


async def get_ozon_seller_client(
    db: MetrixAdapter = Depends(get_metrix_adapter_for_user),  # noqa: B008
) -> AsyncGenerator[OzonSellerClient, None]:
    """Seller API клиент текущего пользователя из сохранённых секретов"""
    secrets = await db.get_secrets()
    if not (secrets and secrets.seller_client_id and secrets.seller_api_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seller API secrets are required. Configure them first (/api/secrets).",
        )
    if not secrets.seller_client_id.strip().isdigit():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Client-Id должен быть положительным целым числом (см. кабинет Ozon). Текущее значение некорректно.",
        )
    client = OzonSellerClient(
        client_id=secrets.seller_client_id,
        api_key=secrets.seller_api_key,
    )
    try:
        yield client
    finally:
        await client.close()
