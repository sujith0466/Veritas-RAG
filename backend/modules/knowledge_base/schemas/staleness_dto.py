from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class StalenessPolicyDTO(BaseModel):
    """Configurable workspace staleness parameters."""

    max_age_days: int = Field(default=90)
    decay_model: str = Field(default="exponential")  # "exponential" or "linear"
    inactivity_threshold_days: int = Field(default=30)
    auto_stale_flagging: bool = Field(default=False)


class StaleDocumentItemDTO(BaseModel):
    """Stale document metadata."""

    document_id: UUID
    filename: str
    age_days: int
    freshness_score: float
    is_expired: bool
    last_updated_at: datetime


class StalenessReportDTO(BaseModel):
    """Aggregate staleness analytics."""

    workspace_id: UUID
    total_documents: int
    stale_count: int
    stale_ratio: float
    aging_distribution: dict[str, int]  # e.g. "0-30 days": 10, "31-90 days": 5, ">90 days": 2
    stale_documents: list[StaleDocumentItemDTO]


class BulkRemediationRequestDTO(BaseModel):
    """Remediation actions."""

    document_ids: list[UUID]
    action: Literal["MARK_REVIEWED", "ARCHIVE", "REPROCESS"]


class BulkRemediationResultDTO(BaseModel):
    """Counts of modified, archived, and queued documents."""

    modified_count: int = Field(default=0)
    archived_count: int = Field(default=0)
    queued_count: int = Field(default=0)
    failed_count: int = Field(default=0)
