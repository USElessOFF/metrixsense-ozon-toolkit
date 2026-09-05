
from __future__ import annotations

import bcrypt as _bcrypt
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from backend.app.models.user import User

from .base import BaseAdapter

logger = structlog.get_logger(__name__)


class UserAdapter(BaseAdapter):

    def __init__(self, session: AsyncSession):
        self.session = session
        super().__init__(self.session)

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int, load_secrets: bool = False) -> User | None:
        query = select(User).where(User.id == user_id)
        if load_secrets:
            query = query.outerjoin(User.secrets).options(contains_eager(User.secrets))
        result = await self.session.execute(query)
        return result.unique().scalar_one_or_none()

    async def create_user(self, username: str, password: str) -> User:
        hashed = await self.hash_password(password)
        user = User(
            username=username,
            password_hash=hashed,
        )
        return await self.create_object(user)

    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return _bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )

    async def hash_password(self, password: str) -> str:
        return _bcrypt.hashpw(
            password.encode("utf-8"),
            _bcrypt.gensalt(),
        ).decode("utf-8")

    async def authenticate(self, username: str, password: str) -> User | None:
        user = await self.get_by_username(username)
        if user and await self.verify_password(password, user.password_hash):
            return user
        return None

    async def create_default_user(self) -> User:
        existing = await self.get_by_username("metrixsense")
        if existing:
            logger.info("Default user already exists", username="metrixsense")
            return existing
        user = await self.create_user("metrixsense", "metrixsense")
        logger.info("Default user created", username="metrixsense", user_id=user.id)
        return user

    async def user_exists(self, username: str) -> bool:
        user = await self.get_by_username(username)
        return user is not None
