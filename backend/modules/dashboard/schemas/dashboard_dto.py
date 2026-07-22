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

    tenant_id: str = Field(..., description="Tenant identifier")
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

    tenant_id: str = Field(..., description="Tenant identifier")
    active_tenants: int = Field(default=1, description="Number of active tenants")
    total_queries_last_24h: int = Field(
        default=0, description="Total AI queries executed over last 24 hours"
    )
    avg_reliability_score: float = Field(
        default=95.0, description="Current composite AI reliability score"
    )
    avg_confidence_score: float = Field(
        default=0.85, description="Average pre-generation confidence score"
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
