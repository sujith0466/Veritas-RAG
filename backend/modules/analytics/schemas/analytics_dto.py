"""Pydantic v2 Data Transfer Objects for Query Analytics & Reliability Intelligence (`Phase 4 Milestone 1`)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsFilterDTO(BaseModel):
    """Filter parameters for querying analytics metrics and history."""

    model_config = ConfigDict(frozen=True)

    tenant_id: str = Field(..., description="Tenant identifier namespace")
    start_time: datetime | None = Field(None, description="Start timestamp filter")
    end_time: datetime | None = Field(None, description="End timestamp filter")
    interval: str = Field("daily", description="Time bucket interval: hourly, daily, weekly")
    outcome_filter: str | None = Field(None, description="Optional filter on query outcome status")


class QueryHistoryItemDTO(BaseModel):
    """Detailed record of a single processed AI query."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique record identifier")
    tenant_id: str = Field(..., description="Tenant namespace")
    correlation_id: str = Field(..., description="Trace correlation identifier")
    query_text: str = Field(..., description="Original user query text")
    outcome: str = Field(..., description="Final execution outcome status")
    confidence_score: float | None = Field(None, description="Pre-generation confidence score (0-1)")
    hallucination_score: float | None = Field(None, description="Post-generation hallucination score (0-1)")
    reliability_score: float | None = Field(None, description="Unified reliability score out of 100")
    retry_attempts: int = Field(0, description="Number of query rewrite retry attempts")
    total_duration_ms: float = Field(..., description="Total execution latency in milliseconds")
    is_safe_to_serve: bool = Field(True, description="Whether the answer passed claim validation")
    created_at: datetime = Field(..., description="Timestamp when query was recorded")


class QueryHistoryListDTO(BaseModel):
    """Paginated list of query execution records."""

    model_config = ConfigDict(frozen=True)

    items: list[QueryHistoryItemDTO] = Field(default_factory=list, description="List of query history records")
    total: int = Field(..., description="Total records matching filter")
    page: int = Field(1, description="Current page index (1-indexed)")
    page_size: int = Field(50, description="Number of items per page")


class QueryTrendsDTO(BaseModel):
    """Time-series query trend aggregations over a specified interval."""

    model_config = ConfigDict(frozen=True)

    timestamps: list[str] = Field(default_factory=list, description="Time bucket labels (e.g. ISO date strings)")
    query_counts: list[int] = Field(default_factory=list, description="Number of queries processed per bucket")
    avg_confidence_scores: list[float] = Field(default_factory=list, description="Average confidence score per bucket")
    avg_reliability_scores: list[float] = Field(default_factory=list, description="Average reliability score per bucket")


class SuccessRateDTO(BaseModel):
    """Aggregate success, failure, and retry statistics."""

    model_config = ConfigDict(frozen=True)

    total_queries: int = Field(..., description="Total number of queries analyzed")
    success_count: int = Field(..., description="Number of successfully served queries")
    clarification_count: int = Field(..., description="Number of queries requiring clarification")
    failure_count: int = Field(..., description="Number of aborted or failed queries")
    retry_count: int = Field(..., description="Number of queries that triggered at least one retry")
    success_rate_percentage: float = Field(..., description="Percentage of queries succeeding without abortion")
    avg_retries_per_query: float = Field(..., description="Average number of retry loops triggered per query")


class LatencyAnalyticsDTO(BaseModel):
    """Latency percentile and average distribution metrics."""

    model_config = ConfigDict(frozen=True)

    p50_ms: float = Field(..., description="50th percentile (median) latency in milliseconds")
    p90_ms: float = Field(..., description="90th percentile latency in milliseconds")
    p95_ms: float = Field(..., description="95th percentile latency in milliseconds")
    p99_ms: float = Field(..., description="99th percentile latency in milliseconds")
    avg_ms: float = Field(..., description="Mean execution latency across all analyzed queries")


class ConfidenceAnalyticsDTO(BaseModel):
    """Summary statistics for pre-generation confidence evaluation."""

    model_config = ConfigDict(frozen=True)

    avg_confidence: float = Field(..., description="Mean pre-generation confidence score")
    min_confidence: float = Field(..., description="Minimum recorded confidence score")
    max_confidence: float = Field(..., description="Maximum recorded confidence score")
    high_confidence_count: int = Field(..., description="Count of queries with score >= 0.75")
    medium_confidence_count: int = Field(..., description="Count of queries with score between 0.40 and 0.75")
    low_confidence_count: int = Field(..., description="Count of queries with score < 0.40")


class ReliabilityHistoryDTO(BaseModel):
    """Historical timeline of unified reliability scores."""

    model_config = ConfigDict(frozen=True)

    timestamps: list[str] = Field(default_factory=list, description="Time bucket labels")
    scores: list[float] = Field(default_factory=list, description="Mean reliability score per bucket")
    moving_average_scores: list[float] = Field(default_factory=list, description="3-bucket moving average of reliability scores")


class SearchAnalyticsDTO(BaseModel):
    """Aggregated retrieval stage metrics correlated with query history."""

    model_config = ConfigDict(frozen=True)

    total_searches: int = Field(..., description="Total hybrid searches executed")
    avg_dense_candidates: float = Field(..., description="Average dense candidates retrieved per query")
    avg_sparse_candidates: float = Field(..., description="Average sparse candidates retrieved per query")
    avg_merged_unique: float = Field(..., description="Average unique candidates after RRF merging")
    avg_retrieval_duration_ms: float = Field(..., description="Average duration of retrieval phase in milliseconds")
    stage_breakdowns: dict[str, Any] = Field(default_factory=dict, description="Detailed stage latency averages")


class StageTraceDTO(BaseModel):
    """Execution latency breakdown across individual pipeline stages."""

    model_config = ConfigDict(frozen=True)

    stage_name: str = Field(..., description="Name of the pipeline stage")
    duration_ms: float = Field(..., description="Duration taken by the stage in milliseconds")
    status: str = Field("COMPLETED", description="Stage execution outcome status")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional stage execution diagnostics")


class RetrievalCandidateTraceDTO(BaseModel):
    """Forensic breakdown of retrieved context candidates."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str = Field(..., description="Knowledge chunk identifier")
    document_title: str = Field("Unknown Document", description="Source document title")
    content_snippet: str = Field(..., description="Snippet of chunk text")
    dense_score: float = Field(0.0, description="Dense vector cosine similarity score")
    sparse_score: float = Field(0.0, description="Sparse BM25 matching score")
    rrf_rank: int = Field(0, description="Reciprocal Rank Fusion merged rank")
    rerank_score: float | None = Field(None, description="Cross-encoder reranking score")


class ConfidenceSignalTraceDTO(BaseModel):
    """Forensic signals driving the pre-generation confidence score."""

    model_config = ConfigDict(frozen=True)

    signal_name: str = Field(..., description="Name of confidence signal")
    weight: float = Field(..., description="Signal weight in calculation")
    score: float = Field(..., description="Calculated signal score (0-1)")
    explanation: str = Field(..., description="Human-readable explanation of the score")


class SelfCorrectionTraceDTO(BaseModel):
    """Diagnostic trace of self-correction or query rewrite steps."""

    model_config = ConfigDict(frozen=True)

    attempt_number: int = Field(..., description="Iteration attempt index (1-indexed)")
    trigger_reason: str = Field(..., description="Reason why self-correction was triggered")
    rewritten_query: str | None = Field(None, description="Query after rewrite attempt")
    action_taken: str = Field(..., description="Action executed during this iteration")
    duration_ms: float = Field(..., description="Time spent on this correction iteration")


class QueryTraceDetailDTO(BaseModel):
    """Complete forensic inspection trace for a single query execution."""

    model_config = ConfigDict(frozen=True)

    record: QueryHistoryItemDTO = Field(..., description="Base query execution record")
    stage_traces: list[StageTraceDTO] = Field(default_factory=list, description="Stage latency waterfall")
    retrieval_candidates: list[RetrievalCandidateTraceDTO] = Field(default_factory=list, description="Retrieved candidates breakdown")
    confidence_signals: list[ConfidenceSignalTraceDTO] = Field(default_factory=list, description="Confidence calculation breakdown")
    self_corrections: list[SelfCorrectionTraceDTO] = Field(default_factory=list, description="Self-correction iteration timeline")


class QuerySandboxRequestDTO(BaseModel):
    """Request payload for testing query execution inside the sandbox console."""

    model_config = ConfigDict(frozen=True)

    query_text: str = Field(..., description="Query string to test")
    retrieval_strategy: str = Field("hybrid", description="Retrieval strategy: hybrid, dense_only, sparse_only")
    top_k: int = Field(5, ge=1, le=20, description="Number of candidates to retrieve")
    confidence_threshold: float = Field(0.75, ge=0.0, le=1.0, description="Pre-generation safety threshold")
    enable_reranking: bool = Field(True, description="Whether to run cross-encoder reranking")
    enable_self_correction: bool = Field(True, description="Whether to allow query rewrite loops")


class QuerySandboxResponseDTO(BaseModel):
    """Response returned from executing a query in the sandbox console."""

    model_config = ConfigDict(frozen=True)

    correlation_id: str = Field(..., description="Assigned trace correlation ID")
    outcome: str = Field(..., description="Execution outcome status")
    final_answer: str = Field(..., description="Generated answer text or intervention notice")
    trace_detail: QueryTraceDetailDTO = Field(..., description="Complete forensic diagnostics")
