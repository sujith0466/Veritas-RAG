"""Upload endpoint response and session schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Response returned upon accepting a document upload (`POST /api/v1/documents/upload`)."""

    document_id: uuid.UUID = Field(description="Unique document aggregate ID")
    version_id: uuid.UUID = Field(description="Version record ID")
    job_id: uuid.UUID = Field(description="Background processing job tracking ID")
    status: str = Field(default="PENDING", description="Initial processing status")
    filename: str = Field(description="Sanitized storage filename")
    original_filename: str = Field(description="Original user-provided filename")
    file_size_bytes: int = Field(description="File size in bytes")
    created_at: datetime = Field(description="Timestamp when upload was accepted")
