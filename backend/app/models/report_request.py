
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .user import User


class ReportStatus(str, Enum):

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportType(str, Enum):

    FULL = "full_report"
    DAILY = "daily_report"


class ReportRequestOzon(Base):

    __tablename__ = "report_requests_ozon"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    request_uuid: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4())
    )
    date_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    date_to: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ReportStatus.PENDING.value)
    type: Mapped[ReportType] = mapped_column(String(20), nullable=False)
    info: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="report_requests")
