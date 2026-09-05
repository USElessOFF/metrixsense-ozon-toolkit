"""Базовый DAL: транзакции + retry"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, TypeVar

import structlog
from sqlalchemy import Result, Select, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.app.models.base import Base

logger = structlog.get_logger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


def _default_exception() -> str:
    return "unknown exception"


db_retry = retry(
    retry=retry_if_exception_type(SQLAlchemyError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=lambda retry_state: logger.warning(
        "Database retry",
        attempt=retry_state.attempt_number,
        exception=str(getattr(retry_state.outcome, "exception", _default_exception)()),
    ),
)


class BaseAdapter:
    """DAL с ретраями"""

    def __init__(self, session: AsyncSession):
        self.session = session

    @asynccontextmanager
    async def _managed_transaction(self, commit: bool = True):
        try:
            yield self.session
            if commit:
                await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            logger.error("Transaction failed", error=str(e))
            raise

    def _iterate(self, items: list[ModelType] | ModelType) -> list[ModelType]:
        if not isinstance(items, list):
            return [items]
        return list(items)

    @db_retry
    async def execute_statement(self, statement: Select[Any], *, commit: bool = True) -> Result[Any]:
        async with self._managed_transaction(commit=commit) as session:
            result = await session.execute(statement)
            return result

    @db_retry
    async def refresh_object(self, instance: Base) -> None:
        await self.session.refresh(instance)

    @db_retry
    async def update_object(
        self, what_upd: ModelType, update_dict: dict[str, Any], *, commit: bool = True
    ) -> ModelType:
        async with self._managed_transaction(commit=commit) as session:
                for key, value in update_dict.items():
                    setattr(what_upd, key, value)
                merged = await session.merge(what_upd)
                logger.info("Object updated", object_repr=str(merged))
        if commit:
            await self.session.refresh(merged)
        return merged

    @db_retry
    async def delete_object(self, instance: Base, *, commit: bool = True) -> None:
        async with self._managed_transaction(commit=commit) as session:
            await session.delete(instance)

    @db_retry
    async def bulk_delete_object(self, instances: list[Base], *, commit: bool = True) -> None:
        async with self._managed_transaction(commit=commit) as session:
            for obj in instances:
                await session.delete(obj)

    @db_retry
    async def create_object(self, instance: ModelType, *, commit: bool = True) -> ModelType:
        async with self._managed_transaction(commit=commit) as session:
            session.add(instance)
        if commit:
            await self.session.refresh(instance)
        return instance

    @db_retry
    async def get_by_pk(self, model_class: type[ModelType], pk_id: Any) -> ModelType | None:
        result = await self.session.get(model_class, pk_id)
        return result

    async def get_first_by_field(
        self, model_class: type[ModelType], field: str, value: Any
    ) -> ModelType | None:
        if not hasattr(model_class, field):
            raise TypeError(f"Model {model_class.__name__} has no field '{field}'")
        statement = select(model_class).where(getattr(model_class, field) == value)
        results = await self.execute_statement(statement)
        return results.scalar_one_or_none()

    async def get_all(self, model_class: type[ModelType]) -> list[ModelType]:
        statement = select(model_class)
        results = await self.execute_statement(statement)
        return list(results.scalars().all())
