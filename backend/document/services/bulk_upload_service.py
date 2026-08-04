"""Bulk Upload Service.

Handles coordination of multiple file uploads, presigned URLs, and batch progress tracking.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.redis_client import redis_client
from backend.document.models.bulk_batch import BulkBatch
from backend.document.repositories.bulk_batch_repository import BulkBatchRepository


class BulkUploadService:
    """Service for managing bulk upload batches."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the service."""
        self.session = session
        self.repository = BulkBatchRepository(session)

    async def create_batch(
        self, tenant_id: str, user_id: uuid.UUID, total_jobs: int
    ) -> BulkBatch:
        """Create a new bulk upload batch."""
        batch = BulkBatch(
            tenant_id=tenant_id,
            created_by_user_id=user_id,
            status="PENDING",
            total_jobs=total_jobs,
        )
        self.session.add(batch)
        await self.session.flush()
        await self.session.refresh(batch)

        # Initialize progress tracking in Redis
        await redis_client.set(f"batch_progress:{batch.id}", 0)
        return batch

    async def get_batch(
        self, batch_id: uuid.UUID, tenant_id: str
    ) -> BulkBatch | None:
        """Fetch a batch by ID."""
        return await self.repository.get_by_id_and_tenant(batch_id, tenant_id)

    async def cancel_batch(
        self, batch_id: uuid.UUID, tenant_id: str
    ) -> bool:
        """Cancel an ongoing batch."""
        batch = await self.get_batch(batch_id, tenant_id)
        if not batch:
            return False

        # Set cancellation flag in Redis
        await redis_client.set(f"bulk_cancel:{batch_id}", "1", ex=86400)
        await self.repository.update_status(batch_id, "CANCELLED")
        await self.session.flush()
        return True

    async def get_progress(
        self, batch_id: uuid.UUID, tenant_id: str
    ) -> dict:
        """Get the real-time progress of a batch."""
        batch = await self.get_batch(batch_id, tenant_id)
        if not batch:
            return {"error": "Not Found"}

        progress_str = await redis_client.get(f"batch_progress:{batch_id}")
        completed = int(progress_str) if progress_str else 0
        return {
            "batch_id": batch_id,
            "status": batch.status,
            "completed_jobs": completed,
            "total_jobs": batch.total_jobs,
            "percentage": (completed / batch.total_jobs * 100) if batch.total_jobs > 0 else 0
        }
