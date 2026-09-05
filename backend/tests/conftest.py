"""Shared fixtures for MetrixSense API tests"""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

# --- Test environment: must be set BEFORE importing app/database ---
# Database.py/engine создаются при импорте с settings.DATABASE_URL — по-этому
# подменяем через env до импорта, а не мутируем settings после.
_TMP_DB = Path(tempfile.mkdtemp()) / "metrixsense.test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
# Никаких реальных ключей Ozon в тестах: live-вызовы только при -m live.
os.environ["OZON_SELLER_CLIENT_ID"] = ""
os.environ["OZON_SELLER_API_KEY"] = ""
os.environ["OZON_PERFORMANCE_CLIENT_ID"] = ""
os.environ["OZON_PERFORMANCE_SECRET"] = ""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app.adapters.user_adapter import UserAdapter
from backend.app.config import settings
from backend.app.database import async_session, engine
from backend.app.main import app
from backend.app.models import Base


@pytest_asyncio.fixture(scope="session")
async def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    """Создать схему БД и дефолтного пользователя один раз на сессию.

    session-scope: не пересоздавать таблицы для каждого теста (быстро и
    без риска блокировок при parallel/последовательном запуске).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        adapter = UserAdapter(session)
        if not await adapter.user_exists(settings.DEFAULT_USERNAME):
            await adapter.create_user(settings.DEFAULT_USERNAME, settings.DEFAULT_PASSWORD)
            await session.commit()

    yield


@pytest_asyncio.fixture
async def client(setup_db) -> AsyncGenerator[AsyncClient, None]:
    """Test client with fresh app instance (schema + default user already loaded)"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, Any]:
    resp = await client.post(
        "/auth/login",
        json={"username": settings.DEFAULT_USERNAME, "password": settings.DEFAULT_PASSWORD},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

pytest_plugins = ('pytest_asyncio')
