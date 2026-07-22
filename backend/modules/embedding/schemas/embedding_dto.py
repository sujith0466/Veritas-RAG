"""Pydantic v2 DTO schemas for the Embedding Pipeline.

Provides validation and serialization models across REST API requests/responses,
job tracking progress detail, provider registry information, and tenant KPI metrics.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import (AliasChoices, BaseModel, ConfigDict, Field,
                      field_validator)


class EmbeddingProcessRequestDTO(BaseModel):
    """Request DTO to trigger batch embedding for a document version."""

    document_id: uuid.UUID = Field(description="Target Document UUID")
    document_version_id: uuid.UUID = Field(description="Target Document Version UUID")
    provider: str | None = Field(
        default=None,
        description="Optional provider override ('openai', 'cohere', 'local')",
    )
    model_name: str | None = Field(
        default=None,
        description="Optional model identifier override (e.g. 'text-embedding-3-large')",
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Number of chunks to vectorize per API request batch",
    )
    force_reembed: bool = Field(
        default=False,
        description="If True, bypasses idempotency hash check and re-generates vectors",
    )

    model_config = ConfigDict(extra="forbid")


class EmbeddingJobDTO(BaseModel):
    """Summary representation of an asynchronous embedding job."""

    job_id: uuid.UUID = Field(
        validation_alias=AliasChoices("job_id", "id"), description="Unique job UUID"
    )
    tenant_id: str = Field(description="Tenant namespace ID")
    document_id: uuid.UUID = Field(description="Parent Document UUID")
    document_version_id: uuid.UUID = Field(description="Target Document Version UUID")
    status: str = Field(
        description="Job status ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')"
    )
    provider: str = Field(description="Embedding provider used")
    model_name: str = Field(description="Embedding model used")
    total_chunks: int = Field(description="Total chunks in this document version")
    processed_chunks: int = Field(
        default=0, description="Chunks successfully vectorized or retrieved from cache"
    )
    failed_chunks: int = Field(
        default=0, description="Chunks that failed vectorization"
    )
    total_tokens_consumed: int = Field(
        default=0, description="Tokens billed during job execution"
    )
    error_message: str | None = Field(
        default=None, description="Error message if job failed"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Job creation timestamp",
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Job last update timestamp",
    )

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def format_datetime(cls, v: Any) -> str:
        if v is None:
            return datetime.now(UTC).isoformat()
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)

    @field_validator(
        "processed_chunks", "failed_chunks", "total_tokens_consumed", mode="before"
    )
    @classmethod
    def default_zero(cls, v: Any) -> int:
        return v if v is not None else 0

    @property
    def progress_percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total_chunks == 0:
            return 100.0 if self.status == "COMPLETED" else 0.0
        return round((self.processed_chunks / self.total_chunks) * 100.0, 2)

    model_config = ConfigDict(from_attributes=True)


class EmbeddingJobDetailDTO(EmbeddingJobDTO):
    """Extended inspection detail for an embedding job including progress rate and breakdown."""

    is_cached_hit_count: int = Field(
        default=0,
        description="Chunks fulfilled via exact content hash hit without API calls",
    )
    metadata_json: dict[str, Any] | None = Field(
        default=None, description="Additional job execution metrics"
    )


class PaginatedJobResponse(BaseModel):
    """Paginated list of tenant embedding jobs."""

    items: list[EmbeddingJobDTO] = Field(description="Page of job summaries")
    total: int = Field(description="Total matching jobs")
    page: int = Field(description="Current page index (1-indexed)")
    size: int = Field(description="Page size")
    pages: int = Field(description="Total pages available")


class ProviderModelInfoDTO(BaseModel):
    """Information regarding a single model supported by a provider."""

    model_name: str = Field(description="Exact model identifier")
    dimension: int = Field(description="Vector array dimensionality")
    max_input_tokens: int = Field(description="Maximum token limit per chunk")
    is_default: bool = Field(
        default=False, description="Whether this is the provider's default model"
    )


class ProviderInfoDTO(BaseModel):
    """Information regarding an embedding provider registered in the factory."""

    provider: str = Field(description="Provider code ('openai', 'cohere', 'local')")
    display_name: str = Field(description="Human-readable provider name")
    description: str = Field(
        description="Brief summary of provider capabilities and latency characteristics"
    )
    is_available: bool = Field(
        default=True, description="Whether provider is active and credentials exist"
    )
    models: list[ProviderModelInfoDTO] = Field(
        description="List of supported models and dimensions"
    )


class EmbeddingMetricsDTO(BaseModel):
    """Tenant-level token budget consumption and vector inventory KPIs."""

    tenant_id: str = Field(description="Tenant namespace ID")
    monthly_token_quota: int = Field(description="Total monthly allocated token budget")
    total_tokens_consumed: int = Field(
        description="Total tokens consumed across all jobs"
    )
    remaining_tokens: int = Field(description="Remaining token budget")
    total_vectors_stored: int = Field(
        description="Total active vectors staged in chunk_embeddings"
    )
    active_jobs_count: int = Field(
        description="Count of currently PENDING or PROCESSING jobs"
    )
    completed_jobs_count: int = Field(description="Count of COMPLETED jobs")
    failed_jobs_count: int = Field(description="Count of FAILED jobs")
    provider_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Distribution map of vectors stored by provider (e.g., {'openai': 1200, 'cohere': 300})",
    )
