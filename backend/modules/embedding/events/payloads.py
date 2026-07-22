"""Embedding Domain Events definitions.

Enforces versioned domain event payloads (`schema_version: "1.0.0"`) across job initiation,
batch progress, completion, and failure (`ADR-M2-003`), bridging cleanly with `BaseEvent` / `EventDispatcher`.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.core.events.base import BaseEvent


class EmbeddingEventPayload(BaseModel):
    """Base schema for all versioned embedding domain events (`schema_version: "1.0.0"`)."""

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
    document_version_id: uuid.UUID | None = Field(
        default=None, description="Document Version ID"
    )
    job_id: uuid.UUID | None = Field(default=None, description="Embedding job ID")
    data: dict[str, Any] = Field(
        default_factory=dict, description="Event-specific payload metrics and details"
    )


def create_embedding_event(
    event_type: str,
    tenant_id: str,
    document_id: uuid.UUID,
    document_version_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    data: dict[str, Any] | None = None,
) -> EmbeddingEventPayload:
    """Factory helper to generate canonical versioned embedding domain event payloads."""
    return EmbeddingEventPayload(
        event_type=event_type,
        tenant_id=tenant_id,
        document_id=document_id,
        document_version_id=document_version_id,
        job_id=job_id,
        data=data or {},
    )


@dataclass(frozen=True)
class EmbeddingDomainEvent(BaseEvent):
    """Event wrapper containing the versioned domain payload for EventDispatcher bus distribution."""

    payload: EmbeddingEventPayload | None = None


# Canonical Event Type Constants
EVENT_EMBEDDING_STARTED = "EmbeddingStarted"
EVENT_EMBEDDING_PROGRESS = "EmbeddingProgress"
EVENT_EMBEDDING_COMPLETED = "EmbeddingCompleted"
EVENT_EMBEDDING_FAILED = "EmbeddingFailed"
