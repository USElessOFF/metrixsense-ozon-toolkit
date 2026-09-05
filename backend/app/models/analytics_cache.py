
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AnalyticsCache(Base):

    __tablename__ = "analytics_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
