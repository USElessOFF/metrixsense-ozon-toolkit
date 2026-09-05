"""Начальная схема MetrixSense (состояние до cost_price_share).

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-27

Схема соответствует релизу до внедрения Alembic: существующие локальные БД
штампуются этой ревизией (alembic stamp), после чего накатываются 0002+.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "ozon_secrets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seller_client_id", sa.String(length=100), nullable=True),
        sa.Column("seller_api_key", sa.String(length=100), nullable=True),
        sa.Column("performance_client_id", sa.String(length=100), nullable=True),
        sa.Column("performance_secret", sa.String(length=150), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_ozon_secrets_user_id"), "ozon_secrets", ["user_id"], unique=False)

    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tax_system", sa.String(length=20), nullable=False),
        sa.Column("ad_budget_percent", sa.Float(), nullable=False),
        sa.Column("logistics_cost", sa.Float(), nullable=False),
        sa.Column("fbo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_user_settings_user_id"), "user_settings", ["user_id"], unique=False)

    op.create_table(
        "report_requests_ozon",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_uuid", sa.String(length=36), nullable=False),
        sa.Column("date_from", sa.DateTime(), nullable=False),
        sa.Column("date_to", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("info", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        op.f("ix_report_requests_ozon_user_id"), "report_requests_ozon", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_report_requests_ozon_request_uuid"),
        "report_requests_ozon",
        ["request_uuid"],
        unique=True,
    )

    op.create_table(
        "analytics_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cache_key", sa.String(length=255), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        op.f("ix_analytics_cache_cache_key"), "analytics_cache", ["cache_key"], unique=True
    )


def downgrade() -> None:
    op.drop_table("analytics_cache")
    op.drop_table("report_requests_ozon")
    op.drop_table("user_settings")
    op.drop_table("ozon_secrets")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")