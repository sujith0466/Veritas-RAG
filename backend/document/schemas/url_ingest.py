from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from backend.document.models.status import DocumentStatus

if TYPE_CHECKING:
    from datetime import datetime
    import uuid


class UrlIngestRequest(BaseModel):
    """Payload for submitting a website URL for ingestion."""

    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Public HTTP or HTTPS website URL to ingest",
        examples=["https://docs.python.org/3/"],
    )
    user_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional user-defined key-value metadata to attach to the document",
    )


class UrlIngestResponse(BaseModel):
    """Response returned upon accepting a URL ingestion request."""

    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID = Field(description="Unique document aggregate root ID")
    version_id: uuid.UUID = Field(description="Initial version ID")
    job_id: uuid.UUID | None = Field(default=None, description="Asynchronous processing job ID")
    source_url: str = Field(description="Normalized canonical source URL")
    status: str = Field(description="Current document status (e.g. PENDING, READY, FETCHING)")
    is_existing: bool = Field(
        default=False,
        description="Whether this source was already ingested for the tenant",
    )
    created_at: datetime = Field(description="Timestamp when URL ingestion was recorded")


class UrlRefreshResponse(BaseModel):
    """Response returned upon requesting a refresh of an existing website source."""

    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID = Field(description="Document ID")
    version_id: uuid.UUID = Field(description="New staged version ID")
    job_id: uuid.UUID = Field(description="Background processing job tracking ID")
    status: str = Field(default=DocumentStatus.PENDING, description="Staged job status")
    message: str = Field(
        default="Website refresh job scheduled. Existing knowledge remains active during processing.",
        description="Status description",
    )
