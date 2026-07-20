"""Document Chunk & Chunk Relationship Entity Models.

Represents the core chunking domain entities with doubly-linked sequential navigation,
hierarchical parent/child links, stable content hashes, and structured metadata.
"""

from typing import Any
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import BaseModel


class DocumentChunk(BaseModel):
    """Normalized, doubly-linked, and validated text chunk belonging to a document version."""

    __tablename__ = "document_chunks"

    tenant_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    strategy_used: Mapped[str] = mapped_column(String(50), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Doubly-linked sequential graph pointers & hierarchical linking
    parent_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    previous_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True
    )
    next_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True
    )

    page_numbers: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    section_path: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_embedded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ORM relationships
    parent_chunk: Mapped["DocumentChunk | None"] = relationship(
        "DocumentChunk", remote_side="DocumentChunk.id", foreign_keys=[parent_chunk_id]
    )
    previous_chunk: Mapped["DocumentChunk | None"] = relationship(
        "DocumentChunk", remote_side="DocumentChunk.id", foreign_keys=[previous_chunk_id]
    )
    next_chunk: Mapped["DocumentChunk | None"] = relationship(
        "DocumentChunk", remote_side="DocumentChunk.id", foreign_keys=[next_chunk_id]
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, doc_id={self.document_id}, idx={self.chunk_index}, strategy='{self.strategy_used}')>"


class ChunkRelationship(BaseModel):
    """Multi-parent and cross-reference relationship edge across chunks in the knowledge graph."""

    __tablename__ = "chunk_relationships"

    tenant_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(
        String(50), nullable=False  # e.g., 'parent_child', 'sequential', 'table_cell', 'cross_ref'
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    source_chunk: Mapped["DocumentChunk"] = relationship("DocumentChunk", foreign_keys=[source_chunk_id])
    target_chunk: Mapped["DocumentChunk"] = relationship("DocumentChunk", foreign_keys=[target_chunk_id])

    def __repr__(self) -> str:
        return f"<ChunkRelationship(src={self.source_chunk_id}, tgt={self.target_chunk_id}, type='{self.relationship_type}')>"
