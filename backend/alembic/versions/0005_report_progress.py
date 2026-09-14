"""Прогресс компиляции отчёта (report_requests_ozon.progress).

Revision ID: 0005_report_progress
Revises: 0004_add_sync_state
Create Date: 2026-09-12

0–100 %: UI показывает бар компиляции полного отчёта.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_report_progress"
down_revision: Union[str, None] = "0004_add_sync_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "report_requests_ozon",
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("report_requests_ozon", "progress")