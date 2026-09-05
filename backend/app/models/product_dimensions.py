
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .user import User


class ProductDimensions(Base):

    __tablename__ = "product_dimensions"
    __table_args__ = (
        UniqueConstraint("user_id", "sku", name="uq_product_dimensions_user_sku"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SKU может превышать диапазон int32 — используем BIGINT.
    sku: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    length_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="product_dimensions")
