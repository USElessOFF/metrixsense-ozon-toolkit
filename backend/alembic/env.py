"""Alembic environment для MetrixSense (async SQLAlchemy)."""

from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

# Гарантируем доступность пакета `backend` при запуске alembic из любого места.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from alembic import context  # noqa: E402
from sqlalchemy import pool  # noqa: E402
from sqlalchemy.engine import Connection  # noqa: E402
from sqlalchemy.ext.asyncio import async_engine_from_config  # noqa: E402

from backend.app.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """URL БД: программная перезапись (database.py) или значение из ini."""
    url = config.attributes.get("db_url")
    if url:
        return str(url)
    return config.get_main_option("sqlalchemy.url") or ""


def run_migrations_offline() -> None:
    """Режим offline: генерация SQL-скрипта без подключения к БД."""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite не умеет ALTER у части операций — batch-режим обязателен
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        {"sqlalchemy.url": _get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def _run_sync_migrations() -> None:
    """Миграции на sync-драйвере, когда init_db вызывается из работающего loop.

    Alembic `command.upgrade` выполняется из async-кода приложения
    (database.init_db внутри lifespan): asyncio.run() в этой ситуации запрещён,
    поэтому для SQLite используем sync-драйвер (sqlite://).
    """
    from sqlalchemy import create_engine

    url = _get_url().replace("+aiosqlite", "")
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


def run_migrations_online() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(run_async_migrations())
    else:
        _run_sync_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()