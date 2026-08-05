from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeBaseOverviewDTO(BaseModel):
    """Comprehensive workspace summary for the knowledge base."""

    workspace_id: UUID
    total_documents: int = Field(default=0)
    active_documents: int = Field(default=0)
    total_chunks: int = Field(default=0)
    total_vectors_in_qdrant: int = Field(default=0)
    total_storage_bytes: int = Field(default=0)
    mime_type_distribution: dict[str, int] = Field(default_factory=dict)
    stale_document_count: int = Field(default=0)
    last_indexed_at: datetime | None = None


class DocumentKnowledgeStatusDTO(BaseModel):
    """Document-level indexing and chunk metadata."""

    document_id: UUID
    version_id: UUID
    filename: str
    status: str
    chunk_count: int = Field(default=0)
    is_stale: bool = Field(default=False)
    freshness_score: float = Field(default=100.0)
    last_indexed_at: datetime | None = None


class ChunkInspectionDetailDTO(BaseModel):
    """Detailed chunk metadata."""

    chunk_id: UUID
    document_id: UUID
    version_id: UUID
    point_id: str
    snippet: str
    token_count: int
    vector_state: str  # e.g., 'SYNCED', 'PENDING', 'FAILED'
    page_number: int | None = None
    bounding_box: dict[str, float] | None = None


class VectorParityValidationDTO(BaseModel):
    """1:1 parity audit between PostgreSQL chunks and Qdrant points."""

    workspace_id: UUID
    postgres_active_chunk_count: int
    qdrant_point_count: int
    is_in_parity: bool
    discrepancy_count: int
    last_audit_at: datetime = Field(default_factory=datetime.utcnow)
