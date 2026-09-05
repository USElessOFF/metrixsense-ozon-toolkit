from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from backend.app.adapters.user_adapter import UserAdapter
from backend.app.config import settings
from backend.app.database import async_session, close_db, init_db
from backend.app.get_bg_tasks import background_tasks
from backend.app.services.sync_scheduler import shutdown_scheduler, start_scheduler

logger = structlog.get_logger(__name__)


async def _create_default_user() -> None:
    async with async_session() as session:
        adapter = UserAdapter(session)
        if not await adapter.user_exists(settings.DEFAULT_USERNAME):
            await adapter.create_user(
                settings.DEFAULT_USERNAME,
                settings.DEFAULT_PASSWORD,
            )
            logger.info(
                "Default user created",
                username=settings.DEFAULT_USERNAME,
            )
        else:
            logger.debug("Default user already exists")

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    logger.info(
        "Starting MetrixSense server",
        host=settings.HOST,
        port=settings.PORT,
        environment=settings.ENVIRONMENT,
    )
    await init_db()
    await _create_default_user()
    logger.info("Database initialized successfully")
    if settings.DEFAULT_PASSWORD == "metrixsense":
        logger.warning(
            "[MetrixSense] Default admin password is in use",
            username=settings.DEFAULT_USERNAME,
            host=settings.HOST,
            hint="Set DEFAULT_PASSWORD in backend/.env to secure the app",
        )
    start_scheduler()
    yield
    await shutdown_scheduler()
    logger.info("Shutting down MetrixSense server")
    if not background_tasks.is_empty():
        logger.info(
            "Waiting for background tasks to finish",
            pending_tasks=len(background_tasks._tasks), # type: ignore
        )
        await background_tasks.wait_until_empty()
    await close_db()
