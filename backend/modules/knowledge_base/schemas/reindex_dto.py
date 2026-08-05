from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ReindexRequestDTO(BaseModel):
    """Request DTO to initiate a vector re-indexing job."""

    target_model: str
    chunk_size_override: int | None = None
    force: bool = Field(default=False)


class ReindexJobDTO(BaseModel):
    """Job lifecycle status and progress tracking."""

    id: UUID
    workspace_id: UUID
    status: str  # INITIATED, STAGING_CREATED, INDEXING, VERIFYING, SWAPPING, COMPLETED, ROLLED_BACK, FAILED
    progress_percentage: float = Field(default=0.0)
    total_documents: int
    processed_documents: int
    total_vectors_indexed: int
    elapsed_time_seconds: int | None = None
    staging_collection: str
    previous_collection: str | None = None
    target_model: str
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
