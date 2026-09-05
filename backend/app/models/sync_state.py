from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import mapped_column

from .base import Base


class SyncState(Base):
    __tablename__ = "sync_state"

    section = mapped_column(String(50), primary_key=True)
    last_sync_at = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_date_to = mapped_column(DateTime(timezone=True), nullable=True)
    status = mapped_column(String(20), default="pending", nullable=False)
    error_message = mapped_column(String(500), nullable=True)
    retry_count = mapped_column(Integer, default=0, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    @property
    def is_stale(self) -> bool:
        if self.last_sync_at is None:
            return True
        from datetime import timedelta
        from backend.app.config import settings
        threshold = self.last_sync_at + timedelta(seconds=settings.SYNC_MAX_INTERVAL_SECONDS)
        return datetime.now(tz=timezone.utc) > threshold
