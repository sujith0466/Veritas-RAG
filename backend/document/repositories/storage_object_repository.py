"""Storage Object persistence repository (`StorageObjectRepository`).

Isolates database tracking for physical object metadata (`checksum_sha256`, `object_key`, `file_size_bytes`).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models.storage_object import StorageObject


class StorageObjectRepository:
    """Repository for CRUD operations on StorageObject records."""

    async def create(self, obj: StorageObject, session: AsyncSession) -> StorageObject:
        """Persist a new StorageObject metadata entry."""
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        return obj

    async def get_by_id(
        self, obj_id: uuid.UUID, session: AsyncSession
    ) -> StorageObject | None:
        """Fetch a StorageObject by its ID."""
        stmt = select(StorageObject).where(
            StorageObject.id == obj_id, StorageObject.is_deleted.is_(False)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_key(
        self, object_key: str, session: AsyncSession
    ) -> StorageObject | None:
        """Fetch a StorageObject by its unique object_key."""
        stmt = select(StorageObject).where(
            StorageObject.object_key == object_key, StorageObject.is_deleted.is_(False)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
