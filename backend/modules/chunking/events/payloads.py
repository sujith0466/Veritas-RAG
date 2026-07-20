"""Chunking Domain Events definitions.

Enforces versioned domain event payloads across chunk creation, failure, and deletion (`schema_version: "1.0.0"`).
"""

from datetime import UTC, datetime
from typing import Any
import uuid

from pydantic import BaseModel, Field


class ChunkEventPayload(BaseModel):
    """Base schema for all versioned chunking domain events (`schema_version: "1.0.0"`)."""

    schema_version: str = Field(default="1.0.0", description="Event payload schema version")
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique event instance ID")
    event_type: str = Field(description="Name of the domain event")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    tenant_id: str = Field(description="Tenant namespace ID")
    document_id: uuid.UUID = Field(description="Document ID")
    document_version_id: uuid.UUID | None = Field(default=None, description="Document Version ID")
    job_id: uuid.UUID | None = Field(default=None, description="Processing job ID")
    data: dict[str, Any] = Field(default_factory=dict, description="Event-specific payload metrics and details")


def create_chunk_event(
    event_type: str,
    tenant_id: str,
    document_id: uuid.UUID,
    document_version_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    data: dict[str, Any] | None = None,
) -> ChunkEventPayload:
    """Factory helper to generate canonical versioned chunking domain event payloads."""
    return ChunkEventPayload(
        event_type=event_type,
        tenant_id=tenant_id,
        document_id=document_id,
        document_version_id=document_version_id,
        job_id=job_id,
        data=data or {},
    )


# Canonical Event Type Constants
EVENT_DOCUMENT_CHUNKED = "DocumentChunked"
EVENT_CHUNKING_FAILED = "ChunkingFailed"
EVENT_CHUNK_DELETED = "ChunkDeleted"
