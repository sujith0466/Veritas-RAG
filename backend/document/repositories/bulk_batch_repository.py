"""Repository for BulkBatch entity."""

import uuid
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models.bulk_batch import BulkBatch
from backend.repositories.base_repository import BaseRepository


class BulkBatchRepository(BaseRepository[BulkBatch]):
    """Repository for managing BulkBatch entities."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository."""
        super().__init__(BulkBatch, session)

    async def get_by_id_and_tenant(
        self, batch_id: uuid.UUID, tenant_id: str
    ) -> Optional[BulkBatch]:
        """Fetch a batch by ID ensuring tenant isolation."""
        stmt = select(BulkBatch).where(
            BulkBatch.id == batch_id, BulkBatch.tenant_id == tenant_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self, batch_id: uuid.UUID, status: str
    ) -> Optional[BulkBatch]:
        """Update the status of a bulk batch."""
        stmt = (
            update(BulkBatch)
            .where(BulkBatch.id == batch_id)
            .values(status=status)
            .returning(BulkBatch)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
