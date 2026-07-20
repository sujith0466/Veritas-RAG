"""Reliability Module Pydantic DTOs (`ADR-005`, `Phase 2 Milestone 5`).

Defines contracts for SLA-bounded retrieval, circuit breaker state, and fallback responses.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.modules.reliability.circuit_breaker.states import CircuitState


class SearchOptionsDTO(BaseModel):
    """Configuration parameters for reliability-guarded hybrid search."""

    query: str = Field(default="", description="Search query string")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of candidates to return")
    sla_budget_ms: float = Field(
        default=400.0, ge=50.0, le=5000.0, description="Max allowed execution latency before SLA breach"
    )
    enable_fallback: bool = Field(
        default=True, description="Whether to route to degraded BM25 path when circuit trips or times out"
    )
    enable_zero_result_recovery: bool = Field(
        default=True, description="Whether to trigger keyword broadening when initial query yields 0 results"
    )


class ReliableCandidateDTO(BaseModel):
    """Candidate chunk surfaced by the reliable retrieval gateway."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    document_id: str = Field(..., description="Parent document ID")
    document_version_id: str = Field(..., description="Document version ID")
    tenant_id: str = Field(..., description="Tenant namespace")
    content: str = Field(..., description="Chunk text content")
    score: float = Field(default=0.0, description="Final score (rerank or sparse fallback score)")
    rank: int = Field(default=1, ge=1, description="Final rank position")
    source: str = Field(default="hybrid", description="Source path (e.g., hybrid, fallback_bm25, zero_broadened)")
    is_fallback: bool = Field(default=False, description="True if candidate came from degraded fallback path")
    is_broadened: bool = Field(default=False, description="True if candidate came from zero-result recovery")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional chunk metadata")


class ReliableRetrievalResultDTO(BaseModel):
    """Unified response envelope returned by ReliabilityGateway."""

    query_text: str = Field(..., description="Original search query text")
    tenant_id: str = Field(..., description="Tenant namespace")
    correlation_id: str = Field(..., description="Request tracking correlation ID")
    candidates: List[ReliableCandidateDTO] = Field(default_factory=list, description="Ranked candidates")
    duration_ms: float = Field(default=0.0, ge=0.0, description="Total execution latency in milliseconds")
    is_sla_breached: bool = Field(default=False, description="True if duration_ms exceeded SLA budget")
    is_degraded_fallback: bool = Field(
        default=False, description="True if circuit breaker or timeout routed request to fallback path"
    )
    fallback_reason: Optional[str] = Field(default=None, description="Reason for degraded fallback route")
    is_zero_result_broadened: bool = Field(
        default=False, description="True if zero-result recovery broadened keywords"
    )


class CircuitBreakerStateDTO(BaseModel):
    """State snapshot of a target circuit breaker for a tenant."""

    tenant_id: str = Field(..., description="Tenant namespace")
    target: str = Field(..., description="Target service identifier (e.g., qdrant_hybrid)")
    state: CircuitState = Field(default=CircuitState.CLOSED, description="Current circuit state")
    failures: int = Field(default=0, ge=0, description="Consecutive failure count in current window")
    last_failure_timestamp: Optional[float] = Field(default=None, description="Unix timestamp of last failure")
    cooldown_ttl_seconds: int = Field(default=0, ge=0, description="Remaining seconds until HALF_OPEN transition")


class SLASummaryDTO(BaseModel):
    """Summary metrics of SLA compliance and degraded fallbacks for a tenant."""

    tenant_id: str = Field(..., description="Tenant namespace")
    total_queries: int = Field(default=0, ge=0, description="Total retrieval queries processed")
    breached_queries: int = Field(default=0, ge=0, description="Number of queries exceeding SLA budget")
    degraded_queries: int = Field(default=0, ge=0, description="Number of queries served via degraded fallback")
    sla_compliance_rate: float = Field(default=100.0, ge=0.0, le=100.0, description="Percentage of queries meeting SLA")
    p95_latency_ms: float = Field(default=0.0, ge=0.0, description="Estimated 95th percentile query latency in ms")
