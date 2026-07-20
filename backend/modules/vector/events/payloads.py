"""Vector Storage Foundation domain event definitions (`schema_version: "1.0.0"`).

Enforces versioned domain event payloads across Qdrant point batch indexing successes (`VectorsIndexed`)
and failures (`VectorIndexFailed`), bridging cleanly with `BaseEvent` and `EventDispatcher`.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
import uuid

from pydantic import BaseModel, Field

from backend.core.events.base import BaseEvent
from backend.core.events.types import EventType


class VectorEventPayload(BaseModel):
    """Base schema for versioned vector storage domain events (`schema_version: "1.0.0"`)."""

    schema_version: str = Field(default="1.0.0", description="Event payload schema version")
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique event instance ID")
    event_type: str = Field(description="Name of the domain event (`vector.indexed` or `vector.index_failed`)")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    tenant_id: str = Field(description="Tenant namespace ID")
    document_id: uuid.UUID = Field(description="Document ID")
    document_version_id: uuid.UUID = Field(description="Document Version ID")
    collection_name: str = Field(description="Target Qdrant collection name")
    data: dict[str, Any] = Field(default_factory=dict, description="Event-specific payload metrics (`points_count`, `dimension`, or `error_code`)")


def create_vector_indexed_payload(
    tenant_id: str,
    document_id: uuid.UUID | str,
    document_version_id: uuid.UUID | str,
    collection_name: str,
    points_count: int,
    dimension: int,
) -> VectorEventPayload:
    """Factory helper to generate `VectorsIndexed` domain event payload."""
    doc_uuid = document_id if isinstance(document_id, uuid.UUID) else uuid.UUID(str(document_id))
    ver_uuid = document_version_id if isinstance(document_version_id, uuid.UUID) else uuid.UUID(str(document_version_id))
    return VectorEventPayload(
        event_type=str(EventType.VECTORS_INDEXED),
        tenant_id=tenant_id,
        document_id=doc_uuid,
        document_version_id=ver_uuid,
        collection_name=collection_name,
        data={
            "points_count": points_count,
            "dimension": dimension,
        },
    )


def create_vector_index_failed_payload(
    tenant_id: str,
    document_id: uuid.UUID | str,
    document_version_id: uuid.UUID | str,
    collection_name: str,
    error_code: str,
    error_message: str,
) -> VectorEventPayload:
    """Factory helper to generate `VectorIndexFailed` domain event payload."""
    doc_uuid = document_id if isinstance(document_id, uuid.UUID) else uuid.UUID(str(document_id))
    ver_uuid = document_version_id if isinstance(document_version_id, uuid.UUID) else uuid.UUID(str(document_version_id))
    return VectorEventPayload(
        event_type=str(EventType.VECTORS_INDEX_FAILED),
        tenant_id=tenant_id,
        document_id=doc_uuid,
        document_version_id=ver_uuid,
        collection_name=collection_name,
        data={
            "error_code": error_code,
            "error_message": error_message,
        },
    )


@dataclass(frozen=True)
class VectorDomainEvent(BaseEvent):
    """Event wrapper containing versioned vector storage payload for EventDispatcher bus distribution."""

    payload: VectorEventPayload | None = None
