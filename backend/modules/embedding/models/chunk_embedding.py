"""Chunk Embedding ORM Model (`ChunkEmbedding`).

Stores high-dimensional dense vector arrays (`JSONB`) generated from `DocumentChunk` records,
alongside content hashes (`content_hash`) to enable zero-call idempotency checks (`ADR-M2-001`, `ADR-M2-002`).
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import BaseModel


class ChunkEmbedding(BaseModel):
    """ORM entity storing generated vector arrays staged in PostgreSQL prior to Qdrant indexing (M3)."""

    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "chunk_id", name="uq_chunk_embeddings_tenant_chunk"
        ),
        Index(
            "ix_chunk_embeddings_tenant_hash_model_idx",
            "tenant_id",
            "content_hash",
            "provider",
            "model_name",
        ),
        Index(
            "ix_chunk_embeddings_tenant_doc_ver_idx", "tenant_id", "document_version_id"
        ),
    )

    tenant_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_vector: Mapped[list[float] | Any] = mapped_column(JSONB, nullable=False)

    chunk: Mapped[Any] = relationship("DocumentChunk", foreign_keys=[chunk_id])

    def __repr__(self) -> str:
        return f"<ChunkEmbedding(id={self.id}, chunk_id={self.chunk_id}, dim={self.dimension}, provider='{self.provider}')>"
