"""Generic Async ORM Base Repository.

Provides standard CRUD operations (get, list, create, update, soft/hard delete)
backed by SQLAlchemy 2.0 `AsyncSession` and `BaseModel`.
"""

from collections.abc import Sequence
from typing import Any, Generic, TypeVar
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import BaseModel, ImmutableBaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)
ImmutableModelType = TypeVar("ImmutableModelType", bound=ImmutableBaseModel)



class BaseRepository(Generic[ModelType]):
    """Generic async repository providing CRUD operations for ORM entities."""

    def __init__(self, session: AsyncSession, model_class: type[ModelType]) -> None:
        self.session = session
        self.model_class = model_class

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelType | None:
        """Fetch a single active (non-deleted) entity by its UUID."""
        stmt = select(self.model_class).where(
            self.model_class.id == entity_id,
            self.model_class.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[ModelType]:
        """Fetch a paginated list of active (non-deleted) entities."""
        stmt = (
            select(self.model_class)
            .where(self.model_class.is_deleted.is_(False))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, **kwargs: Any) -> ModelType:
        """Create and persist a new entity instance."""
        instance = self.model_class(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, instance: ModelType, **kwargs: Any) -> ModelType:
        """Update fields on an existing entity instance."""
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def soft_delete(self, instance: ModelType) -> None:
        """Mark an entity as deleted without removing row from database."""
        instance.is_deleted = True
        await self.session.flush()

    async def hard_delete(self, instance: ModelType) -> None:
        """Permanently delete an entity row from the database."""
        await self.session.delete(instance)
        await self.session.flush()


class ImmutableBaseRepository(Generic[ImmutableModelType]):
    """Generic async repository for append-only / immutable ORM entities (WORM compliant).

    Provides ONLY insertion (`create`) and retrieval (`get_by_id`, `get_all`).
    Explicitly DOES NOT implement `update`, `soft_delete`, or `hard_delete`.
    """

    def __init__(
        self, session: AsyncSession, model_class: type[ImmutableModelType]
    ) -> None:
        self.session = session
        self.model_class = model_class

    async def get_by_id(self, entity_id: uuid.UUID) -> ImmutableModelType | None:
        """Fetch an immutable entity by its UUID."""
        stmt = select(self.model_class).where(self.model_class.id == entity_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self, skip: int = 0, limit: int = 100
    ) -> Sequence[ImmutableModelType]:
        """Fetch a paginated list of immutable entities."""
        stmt = select(self.model_class).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, **kwargs: Any) -> ImmutableModelType:
        """Create and persist a new immutable entity instance."""
        instance = self.model_class(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance
