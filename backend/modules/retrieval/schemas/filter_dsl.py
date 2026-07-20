"""Filter DSL (`Domain Specific Language`) for Metadata Filtering.

Defines the structure for query-time metadata filtering, date ranges,
fusion options, and context compression options.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DateRangeFilter(BaseModel):
    """Filter condition for a specific date range."""
    start: datetime = Field(..., description="Start of date range (inclusive).")
    end: datetime = Field(..., description="End of date range (inclusive).")

    @field_validator("end")
    @classmethod
    def check_date_range(cls, v: datetime, info: Any) -> datetime:
        if "start" in info.data and v < info.data["start"]:
            raise ValueError("end date must be after start date")
        return v

    model_config = ConfigDict(from_attributes=True)


class FilterDSL(BaseModel):
    """Structured Domain Specific Language for metadata filtering."""
    
    tenant_id: str | None = Field(
        default=None,
        description="Tenant ID. Injected server-side from JWT, do not accept from client."
    )
    document_ids: list[UUID] | None = Field(
        default=None, description="Filter to specific document IDs."
    )
    source_types: list[str] | None = Field(
        default=None, description="Filter by source types (e.g. ['pdf', 'markdown'])."
    )
    date_range: DateRangeFilter | None = Field(
        default=None, description="Filter by document creation/update date range."
    )
    metadata_eq: dict[str, str] | None = Field(
        default=None, description="Exact match key-value filters for custom metadata."
    )
    metadata_contains: dict[str, str] | None = Field(
        default=None, description="Substring match key-value filters for custom metadata."
    )

    model_config = ConfigDict(from_attributes=True)


class FusionOptionsDTO(BaseModel):
    """Options for Reciprocal Rank Fusion."""
    k: int = Field(default=60, ge=1, le=200, description="RRF smoothing parameter.")

    model_config = ConfigDict(from_attributes=True)


class CompressionOptionsDTO(BaseModel):
    """Options for context compression stage."""
    enabled: bool = Field(default=True, description="Enable context compression.")
    max_tokens_per_chunk: int = Field(default=512, ge=50, le=2000, description="Max tokens per compressed chunk.")
    min_relevance_score: float = Field(default=0.3, ge=0.0, le=1.0, description="Minimum relevance threshold for sentence extraction.")

    model_config = ConfigDict(from_attributes=True)


class CompressedEvidenceDTO(BaseModel):
    """Result of context compression."""
    original_chunk_id: UUID = Field(..., description="ID of original chunk.")
    compressed_content: str = Field(..., description="Compressed text content.")
    compression_ratio: float = Field(..., description="Length ratio (compressed / original).")

    model_config = ConfigDict(from_attributes=True)
