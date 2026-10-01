"""Data Transfer Objects for aggregated Dashboard and Knowledge Intelligence metrics."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeStageMetric(BaseModel):
    """Metric breakdown for a pipeline processing stage."""

    model_config = ConfigDict(frozen=True)

    stage_name: str
    avg_duration_ms: float
    success_count: int
    failure_count: int


class KnowledgeIntelligenceSummaryDTO(BaseModel):
    """Aggregated intelligence summary of the knowledge layer foundation."""

    model_config = ConfigDict(frozen=True)

    tenant_id: str | None = Field(default=None, description="Tenant identifier")
    total_documents: int = Field(default=0, description="Total documents ingested")
    processed_documents: int = Field(
        default=0, description="Successfully processed documents"
    )
    failed_documents: int = Field(
        default=0, description="Documents failed processing or validation"
    )
    validation_pass_rate: float = Field(
        default=100.0, description="Percentage of documents passing strict validation"
    )

    total_chunks: int = Field(default=0, description="Total knowledge chunks created")
    avg_tokens_per_chunk: float = Field(
        default=0.0, description="Average token count per chunk"
    )
    chunk_strategy_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown of chunks by strategy (fixed_token, semantic, hierarchical)",
    )

    total_embeddings: int = Field(
        default=0, description="Total vector embeddings generated"
    )
    total_embedding_tokens_consumed: int = Field(
        default=0, description="Total LLM API tokens consumed for embeddings"
    )
    active_embedding_provider: str = Field(
        default="openai", description="Default active embedding provider"
    )
    active_embedding_model: str = Field(
        default="text-embedding-3-large", description="Default active embedding model"
    )

    vector_collections_count: int = Field(
        default=0, description="Active Qdrant collections"
    )
    vector_cluster_status: str = Field(
        default="green", description="Qdrant cluster health status (green, yellow, red)"
    )
    total_vector_points: int = Field(
        default=0, description="Total indexed points across vector collections"
    )

    stage_latencies: list[KnowledgeStageMetric] = Field(
        default_factory=list, description="Average processing stage durations"
    )
    recent_health_scans: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recent cluster health, parity, or orphan sweep jobs",
    )
    parity_audit_status: str = Field(
        default="PARITY_CONFIRMED",
        description="Database vs Qdrant vector count parity status",
    )


class ExecutiveDashboardActivityDTO(BaseModel):
    """Activity event for executive timeline."""

    model_config = ConfigDict(frozen=True)

    id: str
    timestamp: str
    event_type: str
    title: str
    description: str
    status: str
    confidence_score: float | None = None
    duration_ms: float | None = None


class ExecutiveDashboardAlertDTO(BaseModel):
    """Security alert or hallucination intervention alert."""

    model_config = ConfigDict(frozen=True)

    id: str
    timestamp: str
    alert_type: str
    severity: str
    query_snippet: str
    reason: str


class ExecutiveDashboardDTO(BaseModel):
    """Aggregated high-level metrics for the executive overview dashboard."""

    model_config = ConfigDict(frozen=True)

    tenant_id: str | None = Field(default=None, description="Tenant identifier")
    active_tenants: int = Field(default=1, description="Number of active tenants")
    time_window: str = Field(default="24h", description="Selected aggregation time window")
    total_queries: int = Field(default=0, description="Total AI queries executed in window")
    total_queries_last_24h: int = Field(
        default=0, description="Total AI queries executed over last 24 hours"
    )
    avg_reliability_score: float | None = Field(
        default=None, description="Current composite AI reliability score"
    )
    avg_confidence_score: float | None = Field(
        default=None, description="Average pre-generation confidence score"
    )
    avg_latency_ms: float | None = Field(
        default=None, description="Average query execution latency in milliseconds"
    )
    blocked_hallucinations_last_24h: int = Field(
        default=0, description="Number of queries aborted to prevent hallucination"
    )
    clarification_rate: float = Field(
        default=0.0,
        description="Percentage of queries triggering clarification prompts",
    )
    system_status: str = Field(
        default="OPERATIONAL", description="Overall system operational status"
    )

    recent_activity: list[ExecutiveDashboardActivityDTO] = Field(
        default_factory=list, description="Recent query and verification events"
    )
    security_alerts: list[ExecutiveDashboardAlertDTO] = Field(
        default_factory=list,
        description="Recent security interventions and hallucination aborts",
    )


class TrustDistributionDTO(BaseModel):
    verified_trusted: float = Field(..., ge=0.0, le=100.0)
    degraded_caution: float = Field(..., ge=0.0, le=100.0)
    unreliable_reject: float = Field(..., ge=0.0, le=100.0)


class SLAComplianceReportDTO(BaseModel):
    tenant_id: str
    window: str
    sla_compliance_rate: float = Field(..., ge=0.0, le=100.0)
    trust_distribution: TrustDistributionDTO


class HallucinationTrendDTO(BaseModel):
    timestamp: str
    interception_rate: float
    total_queries: int


class AuditExportRequestDTO(BaseModel):
    tenant_id: str
    window: str
    mask_pii: bool = True


class AuditExportBundleDTO(BaseModel):
    download_url: str
    checksum_sha256: str
    record_count: int


class LiveDashboardEventDTO(BaseModel):
    tenant_id: str
    event_type: str
    payload: dict


class CommandHealthComponentDTO(BaseModel):
    name: str
    status: str
    latency_ms: float | None = None
    detail: str | None = None


class CommandSystemHealthDTO(BaseModel):
    status: str
    components: list[CommandHealthComponentDTO] = Field(default_factory=list)


class CommandKpisDTO(BaseModel):
    total_queries: int = 0
    avg_reliability_score: float | None = None
    avg_confidence_score: float | None = None
    avg_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    self_correction_rate: float = 0.0
    clarification_rate: float = 0.0
    hallucination_prevention_count: int = 0
    active_tenants: int = 1
    active_workspaces: int = 1


class CommandReliabilityTrendPointDTO(BaseModel):
    timestamp: str
    reliability: float
    query_count: int


class CommandLatencyPercentilesDTO(BaseModel):
    p50_ms: float | None = None
    p90_ms: float | None = None
    p95_ms: float | None = None
    p99_ms: float | None = None
    avg_ms: float | None = None


class CommandOutcomesBreakdownDTO(BaseModel):
    success_count: int = 0
    aborted_hallucination_count: int = 0
    aborted_low_confidence_count: int = 0
    clarification_count: int = 0
    no_relevant_chunks_count: int = 0
    policy_violation_count: int = 0
    total_count: int = 0


class CommandKnowledgeHealthDTO(BaseModel):
    total_documents: int = 0
    processed_documents: int = 0
    failed_documents: int = 0
    total_chunks: int = 0
    total_embeddings: int = 0
    pending_jobs: int = 0
    failed_jobs: int = 0
    vector_status: str = "green"


class CommandCenterDTO(BaseModel):
    """Consolidated Command Center payload for Enterprise AI Reliability."""

    model_config = ConfigDict(frozen=True)

    tenant_id: str
    time_window: str
    system_health: CommandSystemHealthDTO
    kpis: CommandKpisDTO
    reliability_trend: list[CommandReliabilityTrendPointDTO] = Field(default_factory=list)
    latency_percentiles: CommandLatencyPercentilesDTO
    outcomes: CommandOutcomesBreakdownDTO
    knowledge_health: CommandKnowledgeHealthDTO
    alerts: list[ExecutiveDashboardAlertDTO] = Field(default_factory=list)


class QueryExecutionLedgerItemDTO(BaseModel):
    """Individual execution summary row in the admin execution ledger."""

    id: str
    correlation_id: str
    query_text: str
    outcome: str
    confidence_score: float | None = None
    reliability_score: float | None = None
    hallucination_score: float | None = None
    retry_attempts: int = 0
    duration_ms: float
    is_safe_to_serve: bool = True
    timestamp: str
    has_retrieval_trace: bool = False


class QueryExecutionLedgerDTO(BaseModel):
    """Paginated execution ledger response."""

    items: list[QueryExecutionLedgerItemDTO] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0
    time_window: str = "24h"


class RetrievalTraceDetailDTO(BaseModel):
    """Hybrid retrieval stage metrics and candidate counts."""

    dense_candidate_count: int = 0
    sparse_candidate_count: int = 0
    merged_unique_count: int = 0
    final_top_k: int = 0
    retrieval_duration_ms: float = 0.0
    stage_breakdown: dict[str, Any] = Field(default_factory=dict)


class QueryExecutionTraceDTO(BaseModel):
    """Deep forensic trace for an individual AI query execution."""

    id: str
    correlation_id: str
    tenant_id: str
    query_text: str
    outcome: str
    confidence_score: float | None = None
    reliability_score: float | None = None
    hallucination_score: float | None = None
    retry_attempts: int = 0
    total_duration_ms: float
    is_safe_to_serve: bool = True
    timestamp: str
    retrieval: RetrievalTraceDetailDTO | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)


