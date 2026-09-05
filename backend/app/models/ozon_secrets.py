
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .user import User


class OzonSecrets(Base):

    __tablename__ = "ozon_secrets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seller_client_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seller_api_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    performance_client_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    performance_secret: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="secrets")
