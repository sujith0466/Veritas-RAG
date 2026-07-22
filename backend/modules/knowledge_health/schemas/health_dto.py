"""Pydantic DTO contracts for Knowledge Health & Lifecycle Management (`ADR-005`)."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScanType(StrEnum):
    """Supported health scan execution types."""

    ORPHAN_SWEEP = "ORPHAN_SWEEP"  # Sweep unreferenced DB chunks and Qdrant points
    PARITY_AUDIT = "PARITY_AUDIT"  # Audit 1:1 count parity between DB and Qdrant
    STALE_DETECTOR = (
        "STALE_DETECTOR"  # Detect chunks with drifted embedding model configs
    )
    ALL = "ALL"  # Execute all health checks sequentially


class ScanStatus(StrEnum):
    """Lifecycle status of a scheduled or manual health scan job."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class HealthScanRequestDTO(BaseModel):
    """Request payload for initiating a health scan (`POST /api/v1/knowledge-health/scans`)."""

    scan_type: ScanType = Field(
        default=ScanType.ALL, description="Type of health check to run."
    )

    model_config = ConfigDict(from_attributes=True)


class HealthScanJobDTO(BaseModel):
    """Detailed result status and metrics for a health scan job."""

    id: UUID = Field(..., description="Unique ID of the scan job.")
    tenant_id: str = Field(..., description="Tenant namespace ID.")
    scan_type: ScanType = Field(..., description="Executed scan type.")
    status: ScanStatus = Field(..., description="Current job execution status.")
    orphans_found: int = Field(
        default=0, description="Total orphaned items identified."
    )
    orphans_purged: int = Field(
        default=0, description="Total orphaned items successfully cleaned up."
    )
    stale_chunks_found: int = Field(
        default=0, description="Total stale chunks identified needing re-embedding."
    )
    parity_status: str = Field(
        default="UNKNOWN",
        description="Parity check status string (e.g. 'SYNCED (100 == 100)').",
    )
    duration_ms: float = Field(
        default=0.0, description="Total execution duration in milliseconds."
    )
    error_message: str | None = Field(
        default=None, description="Error explanation if job failed."
    )
    created_at: datetime = Field(..., description="Job initiation timestamp.")
    updated_at: datetime = Field(..., description="Job last modification timestamp.")

    model_config = ConfigDict(from_attributes=True)


class ParityAuditDTO(BaseModel):
    """Immediate real-time count parity result (`GET /api/v1/knowledge-health/parity`)."""

    tenant_id: str = Field(..., description="Tenant namespace ID.")
    pg_chunk_count: int = Field(
        ..., description="Active embedded chunks in PostgreSQL."
    )
    qdrant_point_count: int = Field(
        ..., description="Total points indexed in Qdrant collection."
    )
    is_synced: bool = Field(..., description="True if counts match precisely 1:1.")
    parity_status: str = Field(..., description="Human-readable status summary.")
    checked_at: datetime = Field(..., description="Timestamp of the audit.")

    model_config = ConfigDict(from_attributes=True)


class PurgeSummaryDTO(BaseModel):
    """Execution summary of a two-phase document purge (`DELETE /api/v1/knowledge-health/purge/{id}`)."""

    document_id: UUID = Field(..., description="Purged document ID.")
    tenant_id: str = Field(..., description="Tenant namespace ID.")
    qdrant_points_deleted: int = Field(
        ..., description="Count of points removed from Qdrant vector store."
    )
    pg_chunks_deleted: int = Field(
        ..., description="Count of chunk rows removed from PostgreSQL."
    )
    is_fully_purged: bool = Field(
        ..., description="True if both phases completed successfully."
    )
    duration_ms: float = Field(..., description="Execution duration in milliseconds.")

    model_config = ConfigDict(from_attributes=True)


class ModelRotationRequestDTO(BaseModel):
    """Request payload to rotate embedding model configuration (`POST /api/v1/knowledge-health/rotate-model`)."""

    new_provider: str = Field(
        ..., description="Target embedding provider (`e.g., 'cohere'`)."
    )
    new_model: str = Field(
        ..., description="Target embedding model (`e.g., 'embed-english-v3.0'`)."
    )

    model_config = ConfigDict(from_attributes=True)


class MigrationJobDTO(BaseModel):
    """Status summary of an active or completed model rotation migration job."""

    job_id: UUID = Field(..., description="Unique migration job ID.")
    tenant_id: str = Field(..., description="Tenant namespace ID.")
    target_provider: str = Field(..., description="Target embedding provider.")
    target_model: str = Field(..., description="Target embedding model.")
    stale_chunks_enqueued: int = Field(
        ..., description="Total stale chunks enqueued for re-embedding."
    )
    status: str = Field(..., description="Migration job state (`e.g., 'PROCESSING'`).")
    started_at: datetime = Field(..., description="Migration initiation timestamp.")

    model_config = ConfigDict(from_attributes=True)
