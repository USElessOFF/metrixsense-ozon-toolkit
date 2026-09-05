"""Добавление cost_price_share в user_settings.

Revision ID: 0002_add_cost_price_share
Revises: 0001_initial_schema
Create Date: 2026-08-27

Доля себестоимости от цены продажи — пользовательская настройка
юнит-экономики (Ozon API не отдаёт закупочную цену).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_cost_price_share"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.add_column(
            sa.Column("cost_price_share", sa.Float(), nullable=False, server_default="0.5")
        )


def downgrade() -> None:
    with op.batch_alter_table("user_settings") as batch_op:
        batch_op.drop_column("cost_price_share")