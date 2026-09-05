"""Локальный справочник габаритов товара (product_dimensions).

Revision ID: 0003_product_dimensions
Revises: 0002_add_cost_price_share
Create Date: 2026-08-27

Ozon Seller API не отдаёт габариты упаковки L×W×H — продавец загружает их
вручную для точного расчёта тарифа логистики (в т.ч. oversized-зон).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_product_dimensions"
down_revision: Union[str, None] = "0002_add_cost_price_share"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_dimensions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sku", sa.BigInteger(), nullable=False),
        sa.Column("length_mm", sa.Integer(), nullable=True),
        sa.Column("width_mm", sa.Integer(), nullable=True),
        sa.Column("height_mm", sa.Integer(), nullable=True),
        sa.Column("weight_g", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "sku", name="uq_product_dimensions_user_sku"),
    )
    op.create_index(
        op.f("ix_product_dimensions_user_id"), "product_dimensions", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_product_dimensions_sku"), "product_dimensions", ["sku"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_product_dimensions_sku"), table_name="product_dimensions")
    op.drop_index(op.f("ix_product_dimensions_user_id"), table_name="product_dimensions")
    op.drop_table("product_dimensions")