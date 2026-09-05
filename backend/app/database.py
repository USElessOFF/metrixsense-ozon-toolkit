"""Управление движком базы данных и сессиями для SQLite"""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from types import TracebackType

import structlog
from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.config import settings

logger = structlog.get_logger(__name__)


BASE_REVISION = "0001_initial_schema"

BACKEND_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
ALEMBIC_SCRIPT_LOCATION = BACKEND_DIR / "alembic"


def _sqlite_file_path() -> Path:
    """Файл БД из настроек: DB_PATH, при заданном DATABASE_URL — из URL"""
    try:
        database = make_url(settings.DATABASE_URL).database
    except Exception:  # noqa: BLE001 — некорректный URL не должен ронять старт
        database = None
    if database and database != ":memory:":
        return Path(database)
    return Path(settings.DB_PATH)


def _enable_pragma_connect(dbapi_connection: sqlite3.Connection, _connection_record: object = None) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.close()


DB_PATH = _sqlite_file_path()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
SQLITE_URL = settings.DATABASE_URL

engine = create_async_engine(
    SQLITE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False},
)

event.listen(engine.sync_engine, "connect", _enable_pragma_connect)

async_session = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class AsyncSessionContextManager:
    def __init__(self, session_generator) -> None:
        self.session_generator = session_generator
        self.session = None

    async def __aenter__(self):
        self.session = await self.session_generator.__anext__()
        return self.session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.session is None:
            return
        if exc_type:
            await self.session.rollback()
        else:
            await self.session.commit()
        await self.session.close()


async def get_async_context_session() -> AbstractAsyncContextManager[AsyncSession]:
    async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
        async with async_session() as session:
            yield session
    return AsyncSessionContextManager(get_async_session())


def _make_alembic_config() -> Config:
    """Конфигурация Alembic с URL из настроек приложения"""
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    cfg.attributes["db_url"] = settings.DATABASE_URL
    return cfg


def _is_legacy_db_without_alembic() -> bool:
    if not DB_PATH.exists():
        return False
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.warning("[MetrixSense] Legacy DB check failed", error=str(e))
        return False
    return "users" in tables and "alembic_version" not in tables


async def init_db() -> None:
    cfg = _make_alembic_config()
    if _is_legacy_db_without_alembic():
        logger.info(
            "[MetrixSense] Legacy DB detected — stamping base revision",
            revision=BASE_REVISION,
        )
        command.stamp(cfg, BASE_REVISION)
    command.upgrade(cfg, "head")
    logger.info("[MetrixSense] Database initialized (alembic head)", path=str(DB_PATH.resolve()))


async def close_db() -> None:
    await engine.dispose()
    logger.info("[MetrixSense] Database connection closed")
