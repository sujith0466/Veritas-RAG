"""Bulk Upload Schemas."""

import uuid
from typing import Any
from pydantic import BaseModel, ConfigDict


class BulkUploadFile(BaseModel):
    """Represents a single file intent for bulk upload."""
    
    filename: str
    size_bytes: int
    mime_type: str


class BulkUploadRequest(BaseModel):
    """Request payload to initiate a bulk upload batch."""
    
    files: list[BulkUploadFile]


class PresignedUrlDTO(BaseModel):
    """Presigned URL details for a single file upload."""
    
    filename: str
    url: str
    fields: dict[str, Any]
    document_id: uuid.UUID


class BulkUploadResponse(BaseModel):
    """Response containing presigned URLs for a new bulk batch."""
    
    batch_id: uuid.UUID
    presigned_urls: list[PresignedUrlDTO]


class BatchProgressResponse(BaseModel):
    """Progress status of an active batch."""
    
    batch_id: uuid.UUID
    status: str
    completed_jobs: int
    total_jobs: int
    percentage: float
