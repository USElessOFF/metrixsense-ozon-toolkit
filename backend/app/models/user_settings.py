
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .user import User

from .base import Base


class UserSettings(Base):

    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tax_system: Mapped[str] = mapped_column(String(20), nullable=False, default="usn_6")
    ad_budget_percent: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    logistics_cost: Mapped[float] = mapped_column(Float, nullable=False, default=150.0)
    # Ozon не отдаёт закупочную цену — себестоимость как доля от выручки
    cost_price_share: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    fbo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="settings")
