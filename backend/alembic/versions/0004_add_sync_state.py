"""Состояние автосинхронизации секций (sync_state).

Revision ID: 0004_add_sync_state
Revises: 0003_product_dimensions
Create Date: 2026-09-05

Хранит курсор последней успешной синхронизации по каждой секции
(prices, cards, financial, rating, search_queries, stocks) и статус для
восстановления после сбоя/перезапуска: приложение помнит, на чём остановилось,
и дотягивает пропущенное, не начиная сначала.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_sync_state"
down_revision: Union[str, None] = "0003_product_dimensions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sync_state",
        sa.Column("section", sa.String(50), primary_key=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_date_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), default="pending", nullable=False),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("retry_count", sa.Integer(), default=0, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_sync_state_status"), "sync_state", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sync_state_status"), table_name="sync_state")
    op.drop_table("sync_state")
