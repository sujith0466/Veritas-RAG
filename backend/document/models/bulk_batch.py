"""Bulk Batch Entity Model.

Groups multiple processing jobs into a single logical batch for tracking.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class BulkBatch(BaseModel):
    """Aggregate root for a bulk upload batch."""

    __tablename__ = "bulk_batches"

    tenant_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50), index=True, default="PENDING", nullable=False
    )
    total_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Progress will be tracked dynamically via Redis, but we can store final states here or track partial success.

    def __repr__(self) -> str:
        return f"<BulkBatch(id={self.id}, status='{self.status}', total={self.total_jobs})>"
