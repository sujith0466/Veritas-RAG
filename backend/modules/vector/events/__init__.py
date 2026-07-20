"""Vector storage domain events package (`ADR-M3-001`)."""

from backend.modules.vector.events.payloads import (
    VectorDomainEvent,
    VectorEventPayload,
    create_vector_index_failed_payload,
    create_vector_indexed_payload,
)

__all__ = [
    "VectorDomainEvent",
    "VectorEventPayload",
    "create_vector_index_failed_payload",
    "create_vector_indexed_payload",
]
