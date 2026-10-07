from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

ModelT = TypeVar("ModelT", bound=DeclarativeBase)


@dataclass(slots=True)
class SqlAlchemyRepository(Generic[ModelT]):
    """Small repository base; domain-specific repositories should wrap this.

    Do not expose raw SQLAlchemy models as API contracts.
    """

    session: AsyncSession
    model_type: type[ModelT]

    async def get(self, object_id: object) -> ModelT | None:
        return await self.session.get(self.model_type, object_id)

    def select_all(self) -> Select[tuple[ModelT]]:
        return select(self.model_type)

    def add(self, model: ModelT) -> ModelT:
        self.session.add(model)
        return model

    async def flush(self) -> None:
        await self.session.flush()
