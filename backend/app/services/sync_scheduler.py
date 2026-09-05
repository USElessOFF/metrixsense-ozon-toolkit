from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from backend.app.config import settings
from backend.app.database import async_session
from backend.app.models.sync_state import SyncState

logger = structlog.get_logger(__name__)

SECTIONS = ["prices", "cards", "financial", "rating", "search_queries", "stocks"]

_sync_scheduler: AsyncIOScheduler | None = None


def _get_scheduler() -> AsyncIOScheduler:
    global _sync_scheduler
    if _sync_scheduler is None:
        jobstores = {"default": SQLAlchemyJobStore(url=settings.DATABASE_URL.replace("sqlite+aiosqlite", "sqlite"))}
        _sync_scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            timezone="UTC",
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600},
        )
    return _sync_scheduler


async def _load_state(section: str) -> SyncState:
    async with async_session() as session:
        result = await session.execute(select(SyncState).where(SyncState.section == section))
        state = result.scalar_one_or_none()
        if state is None:
            state = SyncState(section=section, status="pending")
            session.add(state)
            await session.commit()
        return state


async def _update_state(section: str, **kw: Any) -> None:
    async with async_session() as session:
        result = await session.execute(select(SyncState).where(SyncState.section == section))
        state = result.scalar_one_or_none()
        if state is None:
            state = SyncState(section=section, **kw)
            session.add(state)
        else:
            for k, v in kw.items():
                setattr(state, k, v)
        await session.commit()


async def _sync_section(section: str) -> None:
    state = await _load_state(section)
    if state.status == "in_progress":
        return
    await _update_state(section, status="in_progress", error_message=None)
    try:
        date_to = datetime.now(tz=timezone.utc) - timedelta(days=settings.SYNC_OZON_DELAY_DAYS)
        if state.last_synced_date_to:
            date_from = state.last_synced_date_to
        else:
            date_from = date_to - timedelta(days=settings.SYNC_INITIAL_DAYS)
        date_from = max(date_from, date_to - timedelta(days=settings.SYNC_MAX_DAYS_PER_RUN))
        logger.info("sync section", section=section, date_from=date_from.date(), date_to=date_to.date())
        await _update_state(section, status="ok", last_sync_at=datetime.now(tz=timezone.utc), last_synced_date_to=date_to, retry_count=0)
    except Exception as e:
        retry = state.retry_count + 1
        status = "failed" if retry >= settings.SYNC_MAX_RETRIES else "pending"
        await _update_state(section, status=status, error_message=str(e)[:500], retry_count=retry)
        logger.error("sync section failed", section=section, retry=retry, error=str(e))
        if status == "failed":
            raise


async def trigger_initial_sync() -> None:
    if not settings.SYNC_ENABLED:
        return
    for section in SECTIONS:
        await _update_state(section, status="pending", retry_count=0)
    scheduler = _get_scheduler()
    if not scheduler.running:
        scheduler.start()
    if not scheduler.get_job("initial_sync"):
        from apscheduler.triggers.date import DateTrigger
        scheduler.add_job(
            _run_all_sections,
            DateTrigger(run_date=datetime.now(tz=timezone.utc) + timedelta(seconds=2)),
            id="initial_sync",
            name="Initial sync after onboarding",
            replace_existing=True,
        )


def start_scheduler() -> None:
    if not settings.SYNC_ENABLED:
        logger.info("sync scheduler disabled")
        return
    scheduler = _get_scheduler()
    if not scheduler.get_job("daily_sync"):
        scheduler.add_job(
            _run_all_sections,
            CronTrigger(hour=settings.SYNC_CRON_HOUR, minute=settings.SYNC_CRON_MINUTE),
            id="daily_sync",
            name="Daily sync of all sections",
            replace_existing=True,
        )
    if not scheduler.running:
        scheduler.start()
        logger.info("sync scheduler started", cron=f"{settings.SYNC_CRON_HOUR}:{settings.SYNC_CRON_MINUTE:02d} UTC")


async def _run_all_sections() -> None:
    for section in SECTIONS:
        try:
            await _sync_section(section)
        except Exception:
            pass


async def shutdown_scheduler() -> None:
    global _sync_scheduler
    if _sync_scheduler and _sync_scheduler.running:
        _sync_scheduler.shutdown(wait=True, timeout=30)
        logger.info("sync scheduler stopped")
    _sync_scheduler = None
