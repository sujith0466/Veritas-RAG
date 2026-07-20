"""Processing status polling schemas (`GET /api/v1/documents/{id}/status`)."""

from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class JobDTO(BaseModel):
    """Background job tracking state summary."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_id: uuid.UUID | None = None
    status: str
    current_step: str
    retry_count: int
    max_retries: int
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ProcessingStatusResponse(BaseModel):
    """Lightweight processing status polling response."""

    document_id: uuid.UUID = Field(description="Document ID")
    status: str = Field(description="Current status (PENDING, VALIDATING, EXTRACTING, PROCESSED, FAILED)")
    current_step: str = Field(description="Current active pipeline step")
    progress_percent: int = Field(default=0, description="Estimated progress percentage (0-100)")
    retry_count: int = Field(default=0, description="Number of retry attempts executed")
    error_code: str | None = Field(default=None, description="Error code if failed")
    error_message: str | None = Field(default=None, description="Human-readable error if failed")
    updated_at: datetime = Field(description="Timestamp of last status update")
