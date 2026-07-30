"""Data Transfer Objects (`DTOs`) for the Hybrid Retrieval Engine.

Defines strict request/response payloads for search queries, candidate evaluation,
reciprocal rank fusion (`RRF`), cross-encoder reranking, and stage breakdown timers.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.modules.retrieval.schemas.filter_dsl import (
    CompressionOptionsDTO, FilterDSL)


class SearchRequestDTO(BaseModel):
    """Request DTO for executing hybrid retrieval and sandbox evaluations."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Search query string (sanitized and bounded to 2000 chars per RET_001).",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of final reranked evidence items to return (`1..100`).",
    )
    limit_dense: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Candidate pool size retrieved from Qdrant dense search (`10..200`).",
    )
    limit_sparse: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Candidate pool size retrieved from BM25 sparse search (`10..200`).",
    )
    rrf_k: int = Field(
        default=60,
        ge=1,
        le=200,
        description="Reciprocal Rank Fusion smoothing parameter (`ADR-M4-001`, default 60).",
    )
    dedup_similarity_threshold: float = Field(
        default=0.92,
        ge=0.5,
        le=1.0,
        description="Cosine/Jaccard similarity threshold for near-duplicate filtering (`ADR-M4-002`).",
    )
    filter_dsl: FilterDSL | None = Field(
        default=None,
        description="Structured Domain Specific Language for metadata filtering.",
    )
    compression_options: CompressionOptionsDTO | None = Field(
        default=None,
        description="Options for context compression.",
    )

    model_config = ConfigDict(from_attributes=True)


class CandidatePointDTO(BaseModel):
    """Raw retrieved candidate point from dense (`Qdrant`) or sparse (`BM25`) stages."""

    chunk_id: UUID = Field(..., description="Unique ID of the DocumentChunk.")
    document_id: UUID = Field(..., description="Parent document ID.")
    document_version_id: UUID = Field(..., description="Document version ID.")
    tenant_id: str = Field(..., description="Strict tenant namespace ID.")
    content: str = Field(..., description="Normalized chunk text content.")
    score: float = Field(..., description="Raw similarity or TF-IDF score.")
    source: str = Field(..., description="Retrieval source: `dense` or `sparse`.")
    rank: int = Field(
        ..., ge=1, description="1-indexed rank position in source candidate list."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional payload metadata."
    )

    model_config = ConfigDict(from_attributes=True)


class RankedEvidenceDTO(BaseModel):
    """Merged, deduplicated, and reranked evidence item passed to future engines."""

    chunk_id: UUID = Field(..., description="Unique ID of the DocumentChunk.")
    document_id: UUID = Field(..., description="Parent document ID.")
    document_version_id: UUID = Field(..., description="Document version ID.")
    tenant_id: str = Field(..., description="Strict tenant namespace ID.")
    content: str = Field(..., description="Normalized chunk text content.")
    compressed_content: str | None = Field(
        default=None, description="Compressed chunk text content."
    )
    compression_ratio: float | None = Field(
        default=None, description="Length ratio (compressed / original)."
    )
    dense_rank: int | None = Field(
        default=None, description="Rank in dense candidates (`None` if missing)."
    )
    sparse_rank: int | None = Field(
        default=None, description="Rank in sparse candidates (`None` if missing)."
    )
    rrf_score: float = Field(
        ..., description="Reciprocal Rank Fusion merged score (`ADR-M4-001`)."
    )
    raw_rerank_score: float | None = Field(
        default=None,
        description="Raw cross-encoder output score or logit (`None` if bypassed).",
    )
    normalized_relevance_score: float | None = Field(
        default=None,
        description="Provider-independent probability bounded [0,1] (`None` if bypassed).",
    )
    final_rank: int = Field(
        ..., ge=1, description="Final 1-indexed ordering after reranking."
    )
    matched_sources: list[str] = Field(
        default_factory=list,
        description="Sources that discovered this chunk (e.g. `['dense', 'sparse']`).",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Chunk attributes and breadcrumb metadata."
    )

    model_config = ConfigDict(from_attributes=True)


class RetrievalStageBreakdownDTO(BaseModel):
    """Execution latency breakdown timers across all hybrid stages (`in milliseconds`)."""

    dense_ms: float = Field(default=0.0, description="Dense vector search latency.")
    sparse_ms: float = Field(
        default=0.0, description="Sparse keyword matching latency."
    )
    rrf_fusion_ms: float = Field(
        default=0.0, description="RRF rank fusion & deduplication latency."
    )
    dedup_ms: float = Field(default=0.0, description="Deduplication latency.")
    rerank_ms: float = Field(
        default=0.0, description="Cross-encoder reranking latency."
    )
    compression_ms: float = Field(
        default=0.0, description="Context compression latency."
    )
    total_ms: float = Field(
        default=0.0, description="Total end-to-end orchestration latency."
    )

    model_config = ConfigDict(from_attributes=True)


class RetrievalResultDTOv2(BaseModel):
    """Standardized response payload for `/api/v1/retrieval/search` v2."""

    query_text: str = Field(..., description="Executed query string.")
    tenant_id: str = Field(..., description="Tenant namespace ID.")
    correlation_id: str = Field(..., description="Unique request tracing ID.")
    top_k_requested: int = Field(..., description="Requested top_k count.")
    dense_candidates_count: int = Field(
        ..., description="Candidates returned from dense search."
    )
    sparse_candidates_count: int = Field(
        ..., description="Candidates returned from sparse search."
    )
    unique_candidates_merged: int = Field(
        ..., description="Unique candidates after RRF union and deduplication."
    )
    final_evidence: list[RankedEvidenceDTO] = Field(
        ..., description="Final ordered evidence set."
    )
    stage_latencies: RetrievalStageBreakdownDTO = Field(
        ..., description="Execution latency breakdown across stages."
    )
    dedup_removed_count: int = Field(
        default=0, description="Number of items removed during deduplication."
    )
    filter_applied: bool = Field(
        default=False, description="Whether a filter DSL was applied."
    )

    model_config = ConfigDict(from_attributes=True)


class SearchSandboxResponseDTO(BaseModel):
    """Side-by-side comparative response payload for `/api/v1/retrieval/sandbox` (`ADR-005`)."""

    query_text: str = Field(..., description="Executed query string.")
    tenant_id: str = Field(..., description="Tenant namespace ID.")
    correlation_id: str = Field(..., description="Unique request tracing ID.")
    dense_results: list[CandidatePointDTO] = Field(
        ..., description="Top candidates directly from Qdrant vector search."
    )
    sparse_results: list[CandidatePointDTO] = Field(
        ..., description="Top candidates directly from BM25 keyword matching."
    )
    rrf_merged_results: list[RankedEvidenceDTO] = Field(
        ..., description="Candidate list after RRF fusion and near-duplicate removal."
    )
    final_reranked_results: list[RankedEvidenceDTO] = Field(
        ..., description="Final top_k items evaluated by cross-encoder reranker."
    )
    stage_latencies: RetrievalStageBreakdownDTO = Field(
        ..., description="Execution latency timers."
    )

    model_config = ConfigDict(from_attributes=True)


class RetrievalQueryLogDTO(BaseModel):
    """DTO representing a historical query execution log record."""

    id: UUID = Field(..., description="Log entry UUID.")
    tenant_id: str = Field(..., description="Tenant namespace ID.")
    correlation_id: str = Field(..., description="Request tracing correlation ID.")
    query_text: str = Field(..., description="Executed query string.")
    dense_candidate_count: int = Field(
        ..., description="Number of dense candidates retrieved."
    )
    sparse_candidate_count: int = Field(
        ..., description="Number of sparse candidates retrieved."
    )
    merged_unique_count: int = Field(
        ..., description="Unique candidates after fusion/dedup."
    )
    final_top_k: int = Field(
        ..., description="Number of final evidence items returned."
    )
    total_duration_ms: float = Field(
        ..., description="Total execution duration in milliseconds."
    )
    stage_breakdown_json: dict[str, Any] = Field(
        ..., description="Breakdown of stage latencies (`JSONB`)."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of execution.",
    )

    model_config = ConfigDict(from_attributes=True)


class RetrievalMetricsDTO(BaseModel):
    """DTO summarizing tenant hybrid search KPIs across execution history."""

    tenant_id: str = Field(..., description="Tenant namespace ID.")
    total_queries_executed: int = Field(
        default=0, description="Total search queries run."
    )
    avg_total_duration_ms: float = Field(
        default=0.0, description="Average total query latency."
    )
    p95_total_duration_ms: float = Field(
        default=0.0, description="P95 execution latency."
    )
    avg_dense_candidates: float = Field(
        default=0.0, description="Average dense candidates returned."
    )
    avg_sparse_candidates: float = Field(
        default=0.0, description="Average sparse candidates returned."
    )
    avg_merged_candidates: float = Field(
        default=0.0, description="Average unique merged candidates."
    )
    stage_latencies_avg: RetrievalStageBreakdownDTO = Field(
        default_factory=RetrievalStageBreakdownDTO,
        description="Average latency per stage.",
    )

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Phase 3 backward-compatible aliases
# ---------------------------------------------------------------------------
RetrievalResultDTO = RetrievalResultDTOv2
RetrievalCandidateDTO = CandidatePointDTO
