"""Hybrid Retrieval Engine domain event definitions (`schema_version: "1.0.0"`).

Enforces versioned domain event payloads across query retrieval completions (`QueryRetrieved`),
bridging cleanly with `BaseEvent` and `EventDispatcher` (`ADR-005`).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
import uuid

from pydantic import BaseModel, Field

from backend.core.events.base import BaseEvent
from backend.core.events.types import EventType


class QueryRetrievedPayload(BaseModel):
    """Canonical payload schema for `QueryRetrieved` domain events (`schema_version: "1.0.0"`)."""

    schema_version: str = Field(default="1.0.0", description="Event payload schema version")
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique event instance ID")
    event_type: str = Field(
        default=str(EventType.QUERY_RETRIEVED),
        description="Name of the domain event (`query.retrieved` or `QueryRetrieved`)",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    tenant_id: str = Field(description="Tenant namespace ID")
    correlation_id: str = Field(description="Request tracing correlation ID")
    source_module: str = Field(
        default="backend.modules.retrieval", description="Source domain module package path"
    )
    query_text: str = Field(description="Executed query string")
    top_k_requested: int = Field(description="Requested top_k count")
    dense_candidates_found: int = Field(description="Dense candidates retrieved")
    sparse_candidates_found: int = Field(description="Sparse candidates retrieved")
    unique_merged_candidates: int = Field(description="Unique merged candidates after RRF/dedup")
    reranker_model: str = Field(description="Cross-encoder model name")
    duration_ms: float = Field(description="Total end-to-end execution duration in ms")
    stage_latencies: dict[str, Any] = Field(
        default_factory=dict, description="Execution latency breakdown across stages"
    )


def create_query_retrieved_payload(
    tenant_id: str,
    correlation_id: str,
    query_text: str,
    top_k: int,
    dense_count: int,
    sparse_count: int,
    merged_count: int,
    reranker_model: str,
    duration_ms: float,
    stage_latencies: dict[str, Any] | None = None,
) -> QueryRetrievedPayload:
    """Factory helper to generate `QueryRetrieved` domain event payload."""
    return QueryRetrievedPayload(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        query_text=query_text,
        top_k_requested=top_k,
        dense_candidates_found=dense_count,
        sparse_candidates_found=sparse_count,
        unique_merged_candidates=merged_count,
        reranker_model=reranker_model,
        duration_ms=duration_ms,
        stage_latencies=stage_latencies or {},
    )


@dataclass(frozen=True)
class RetrievalDomainEvent(BaseEvent):
    """Event wrapper containing versioned retrieval payload for EventDispatcher bus distribution."""

    event_type: EventType = EventType.QUERY_RETRIEVED
    payload: QueryRetrievedPayload | None = None

