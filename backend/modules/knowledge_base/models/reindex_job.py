from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class VectorReindexJob(BaseModel):
    """
    Tracks the lifecycle and progress of a blue-green vector re-indexing operation.
    Extends BaseModel which provides id, created_at, updated_at, is_deleted.
    """

    __tablename__ = "vector_reindex_jobs"

    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), index=True, nullable=False)

    # Lifecycle status: INITIATED, PROCESSING, VERIFYING, COMPLETED, FAILED, CANCELLED, ROLLED_BACK
    status: Mapped[str] = mapped_column(String, nullable=False, default="INITIATED")

    source_alias: Mapped[str] = mapped_column(String, nullable=False)
    staging_collection: Mapped[str] = mapped_column(String, nullable=False)
    previous_collection: Mapped[str | None] = mapped_column(String, nullable=True)

    target_model: Mapped[str] = mapped_column(String, nullable=False)

    total_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_vectors_indexed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    parity_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
