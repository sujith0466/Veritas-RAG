"""Document Domain Pydantic DTOs & Schemas.

Includes the canonical Document Manifest DTO, response schemas, and detail views.
"""

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field


class StageMetricDTO(BaseModel):
    """Processing stage duration and execution details."""

    stage: str = Field(description="Stage name (e.g. validation, storage, extraction, ocr)")
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: float = Field(default=0.0, description="Duration in milliseconds")
    status: str = Field(default="COMPLETED")
    error_message: str | None = None


class DocumentManifestDTO(BaseModel):
    """Canonical Document Manifest generated upon successful pipeline execution."""

    manifest_version: str = Field(default="1.0.0", description="Manifest schema version")
    document_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int
    tenant_id: str
    owner_user_id: uuid.UUID | None
    filename: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    checksum_sha256: str
    storage_provider: str
    original_storage_key: str
    normalized_text_path: str | None = None
    metadata_json_path: str | None = None
    page_count: int = 0
    word_count: int = 0
    language: str | None = None
    encoding: str | None = None
    stage_metrics: list[StageMetricDTO] = Field(default_factory=list)
    extraction_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class DocumentVersionDTO(BaseModel):
    """Version detail summary schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    storage_object_id: uuid.UUID
    content_hash: str
    extracted_text_path: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime


class DocumentResponse(BaseModel):
    """Standard summary response representation of a Document aggregate."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    owner_user_id: uuid.UUID | None = None
    filename: str
    original_filename: str
    status: str
    latest_version_id: uuid.UUID | None = None
    word_count: int = 0
    page_count: int = 0
    language: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(DocumentResponse):
    """Extended document representation including version history and canonical manifest."""

    versions: list[DocumentVersionDTO] = Field(default_factory=list)
    manifest: DocumentManifestDTO | None = None


class DocumentListResponse(BaseModel):
    """Paginated document list response."""

    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int
    pages: int
