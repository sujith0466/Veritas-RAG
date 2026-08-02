"""Document Domain Events definitions.

Enforces versioned domain event payloads across all lifecycle state transitions (`schema_version: "1.0.0"`).
"""

from datetime import UTC, datetime
from typing import Any
import uuid

from pydantic import BaseModel, Field


class DomainEventPayload(BaseModel):
    """Base schema for all versioned document domain events."""

    schema_version: str = Field(
        default="1.0.0", description="Event payload schema version"
    )
    event_id: uuid.UUID = Field(
        default_factory=uuid.uuid4, description="Unique event instance ID"
    )
    event_type: str = Field(description="Name of the domain event")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    tenant_id: str = Field(description="Tenant namespace ID")
    document_id: uuid.UUID = Field(description="Document ID")
    job_id: uuid.UUID | None = Field(default=None, description="Processing job ID")
    data: dict[str, Any] = Field(
        default_factory=dict, description="Event-specific payload data"
    )


def create_domain_event(
    event_type: str,
    tenant_id: str,
    document_id: uuid.UUID,
    job_id: uuid.UUID | None = None,
    data: dict[str, Any] | None = None,
) -> DomainEventPayload:
    """Factory helper to generate a canonical, versioned domain event payload."""
    return DomainEventPayload(
        event_type=event_type,
        tenant_id=tenant_id,
        document_id=document_id,
        job_id=job_id,
        data=data or {},
    )


# Canonical Event Type Constants
EVENT_DOCUMENT_UPLOADED = "DocumentUploaded"
EVENT_DOCUMENT_VALIDATED = "DocumentValidated"
EVENT_DOCUMENT_STORED = "DocumentStored"
EVENT_METADATA_EXTRACTED = "MetadataExtracted"
EVENT_TEXT_EXTRACTED = "TextExtracted"
EVENT_OCR_COMPLETED = "OCRCompleted"
EVENT_DOCUMENT_PROCESSED = "DocumentProcessed"
EVENT_DOCUMENT_FAILED = "DocumentFailed"
