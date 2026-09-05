
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .ozon_secrets import OzonSecrets
    from .product_dimensions import ProductDimensions
    from .report_request import ReportRequestOzon
    from .user_settings import UserSettings


class User(Base):

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    secrets: Mapped[list[OzonSecrets]] = relationship(back_populates="user", cascade="all, delete-orphan")
    settings: Mapped[list[UserSettings]] = relationship(back_populates="user", cascade="all, delete-orphan")
    report_requests: Mapped[list[ReportRequestOzon]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    product_dimensions: Mapped[list["ProductDimensions"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
