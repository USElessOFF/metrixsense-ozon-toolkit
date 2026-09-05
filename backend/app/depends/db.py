"""Зависимости базы данных — get_db_session, get_metrix_adapter_for_user"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.metrix_adapter import MetrixAdapter
from backend.app.adapters.user_adapter import UserAdapter
from backend.app.database import get_db_session
from backend.app.models.user import User

from .auth import get_current_user


async def get_metrix_adapter_for_user(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> AsyncGenerator[MetrixAdapter, None]:
    """Зависимость, предоставляющая MetrixAdapter, привязанный к аутентифицированному пользователю"""
    yield MetrixAdapter(session, user_id=current_user.id)

async def get_user_adapter(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> AsyncGenerator[UserAdapter, None]:
    """Зависимость, предоставляющая UserAdapter"""
    yield UserAdapter(session)
