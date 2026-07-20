"""Retrieval Reliability domain event definitions (`schema_version: "1.0.0"`).

Enforces versioned domain event payloads across fallback routes (`retrieval.fallback_triggered`)
and circuit breaker trips (`retrieval.circuit_breaker_tripped`), bridging cleanly with `BaseEvent`
and `EventDispatcher` (`ADR-005`).
"""

from datetime import UTC, datetime
from typing import Any, Optional
import uuid
from pydantic import BaseModel, Field
from backend.core.events.base import BaseEvent
from backend.core.events.types import EventType


class RetrievalFallbackTriggeredPayload(BaseModel):
    """Payload schema for `retrieval.fallback_triggered` domain events (`schema_version: "1.0.0"`)."""

    schema_version: str = Field(default="1.0.0", description="Event payload schema version")
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique event instance ID")
    event_type: str = Field(
        default=str(EventType.RETRIEVAL_FALLBACK_TRIGGERED),
        description="Name of the domain event (`retrieval.fallback_triggered`)",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    tenant_id: str = Field(description="Tenant namespace ID")
    correlation_id: str = Field(description="Request tracing correlation ID")
    source_module: str = Field(
        default="backend.modules.reliability", description="Source domain module package path"
    )
    query_text: str = Field(description="Executed search query text")
    fallback_reason: str = Field(description="Reason that triggered fallback (e.g., QdrantTimeout, CircuitBreakerOpen)")
    duration_ms: float = Field(description="Execution latency in milliseconds")


class CircuitBreakerTrippedPayload(BaseModel):
    """Payload schema for `retrieval.circuit_breaker_tripped` domain events (`schema_version: "1.0.0"`)."""

    schema_version: str = Field(default="1.0.0", description="Event payload schema version")
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique event instance ID")
    event_type: str = Field(
        default=str(EventType.CIRCUIT_BREAKER_TRIPPED),
        description="Name of the domain event (`retrieval.circuit_breaker_tripped`)",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    tenant_id: str = Field(description="Tenant namespace ID")
    target_module: str = Field(description="Target service module (e.g., qdrant_hybrid)")
    failures: int = Field(description="Consecutive failure count triggering the trip")
    error_code: Optional[str] = Field(default=None, description="Error code that caused the trip")


def create_fallback_triggered_event(
    tenant_id: str,
    correlation_id: str,
    query_text: str,
    fallback_reason: str,
    duration_ms: float,
) -> BaseEvent:
    """Factory helper to generate wrapped `retrieval.fallback_triggered` BaseEvent."""
    payload = RetrievalFallbackTriggeredPayload(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        query_text=query_text,
        fallback_reason=fallback_reason,
        duration_ms=duration_ms,
    )
    return BaseEvent(
        event_type=EventType.RETRIEVAL_FALLBACK_TRIGGERED,
        payload=payload.model_dump(),
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source="backend.modules.reliability",
    )


def create_circuit_tripped_event(
    tenant_id: str,
    target_module: str,
    failures: int,
    error_code: Optional[str] = None,
) -> BaseEvent:
    """Factory helper to generate wrapped `retrieval.circuit_breaker_tripped` BaseEvent."""
    payload = CircuitBreakerTrippedPayload(
        tenant_id=tenant_id,
        target_module=target_module,
        failures=failures,
        error_code=error_code,
    )
    return BaseEvent(
        event_type=EventType.CIRCUIT_BREAKER_TRIPPED,
        payload=payload.model_dump(),
        tenant_id=tenant_id,
        source="backend.modules.reliability",
    )
