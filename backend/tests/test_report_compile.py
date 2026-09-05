"""Интеграционный тест компиляции полного отчёта Ozon (реальные API-вызовы).

Помечен pytest.mark.live: реальные запросы к Ozon API и длительный
таймаут (3600 с) — запускается только явно, pytest -m live.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv
from httpx import AsyncClient

from backend.app.config import settings
from backend.app.get_bg_tasks import background_tasks
from backend.app.models.report_request import ReportStatus

pytestmark = pytest.mark.live

TIMEOUT = 3600


def _load_credentials_from_env() -> None:
    """Подгрузить учётные данные Ozon из .env.example, если окружение пустое"""
    if all(
        [
            settings.OZON_SELLER_CLIENT_ID,
            settings.OZON_SELLER_API_KEY,
            settings.OZON_PERFORMANCE_CLIENT_ID,
            settings.OZON_PERFORMANCE_SECRET,
        ]
    ):
        return
    backend_dir = Path(__file__).resolve().parents[1]
    env_file = backend_dir / ".env.example"
    if env_file.exists():
        load_dotenv(env_file, override=True)
        settings.OZON_SELLER_CLIENT_ID = os.getenv("OZON_SELLER_CLIENT_ID", "")
        settings.OZON_SELLER_API_KEY = os.getenv("OZON_SELLER_API_KEY", "")
        settings.OZON_PERFORMANCE_CLIENT_ID = os.getenv("OZON_PERFORMANCE_CLIENT_ID", "")
        settings.OZON_PERFORMANCE_SECRET = os.getenv("OZON_PERFORMANCE_SECRET", "")


def _has_real_credentials() -> bool:
    """Проверить, заданы ли реальные учётные данные Ozon в окружении"""
    _load_credentials_from_env()
    return bool(
        settings.OZON_SELLER_CLIENT_ID
        and settings.OZON_SELLER_API_KEY
        and settings.OZON_PERFORMANCE_CLIENT_ID
        and settings.OZON_PERFORMANCE_SECRET
    )


@pytest.fixture
async def setup_secrets(client: AsyncClient, auth_headers: dict[str, Any]) -> None:
    """Записать секреты Ozon из настроек окружения в БД для тестового пользователя"""
    if not _has_real_credentials():
        return
    resp = await client.put(
        "/api/secrets",
        headers=auth_headers,
        json={
            "seller_client_id": settings.OZON_SELLER_CLIENT_ID,
            "seller_api_key": settings.OZON_SELLER_API_KEY,
            "performance_client_id": settings.OZON_PERFORMANCE_CLIENT_ID,
            "performance_secret": settings.OZON_PERFORMANCE_SECRET,
        },
    )
    assert resp.status_code == 200, f"Не удалось сохранить секреты: {resp.text}"


async def _wait_report_completed(
    client: AsyncClient,
    auth_headers: dict[str, Any],
    request_id: str,
    timeout: int = 600,
) -> str:
    """Ожидать завершения компиляции отчёта, опрашивая статус.

    Статус отчёта запрашивается по маршруту /api/reports/requests/{request_id}.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    last_status: str | None = None
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(
            f"/api/reports/requests/{request_id}", headers=auth_headers
        )
        assert resp.status_code == 200, f"Ошибка получения статуса: {resp.text}"
        data = resp.json()
        status = data["status"]
        if status != last_status:
            print(
                f"\n[STATUS] Статус репорта изменился > {request_id}: {status} — "
                f"{data.get('info', 'No information yet')}"
            )
            last_status = status
        if status == ReportStatus.COMPLETED.value:
            return status
        if status == ReportStatus.FAILED.value:
            raise AssertionError(
                f"Компиляция отчёта завершилась ошибкой: {data.get('info')}"
            )
        print(
            f"\n[STATUS] Статус репорта не изменился, ожидаем > {request_id}: {status} — "
            f"{data.get('info', 'No information yet')}"
        )
        await asyncio.sleep(10)
    raise AssertionError(f"Таймаут ожидания компиляции отчёта ({timeout} сек)")


async def _wait_background_tasks(timeout: int = 60) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while not background_tasks.is_empty() and asyncio.get_event_loop().time() < deadline:
        print(f"\n[BG] Ожидание фоновых задач... осталось: {len(background_tasks._tasks)}")
        await asyncio.sleep(5)
    if not background_tasks.is_empty():
                print("\n[BG] Таймаут ожидания фоновых задач — задачи всё ещё выполняются")


@pytest.mark.skipif(
    not _has_real_credentials(),
    reason="Реальные учётные данные Ozon не заданы в .env — пропуск интеграционного теста",
)
async def test_compile_full_report_with_real_api(
    client: AsyncClient,
    auth_headers: dict[str, Any],
    setup_secrets: None,
) -> None:
    """Полный цикл: создать отчёт → дождаться компиляции → проверить успешный статус.

    Создаёт отчёт за последние 7 дней через POST /api/reports/full
    (ожидает 202 Accepted с request_uuid), затем опрашивает
    GET /api/reports/requests/{request_id} до статуса completed.
    """
    date_to = datetime.now(timezone.utc).date()
    date_from = date_to - timedelta(days=7)
    resp = await client.post(
        "/api/reports/full",
        headers=auth_headers,
        json={"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
    )
    assert resp.status_code == 202, f"Не удалось создать отчёт: {resp.text}"
    request_id = resp.json()["request_uuid"]

    # Проверяем, что отчёт создан и находится в статусе pending/in_progress
    status_resp = await client.get(
        f"/api/reports/requests/{request_id}", headers=auth_headers
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] in {
        ReportStatus.PENDING.value,
        ReportStatus.IN_PROGRESS.value,
    }

    # Дожидаемся завершения обеих фоновых задач (seller + performance)
    await _wait_background_tasks(timeout=120)

    # Опрашиваем статус до завершения
    final_status = await _wait_report_completed(
        client, auth_headers, request_id, timeout=TIMEOUT
    )
    assert final_status == ReportStatus.COMPLETED.value
