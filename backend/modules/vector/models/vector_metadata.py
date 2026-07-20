"""Vector Index Metadata ORM Model (`VectorIndexMetadata`).

Tracks synchronization health, status transitions (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`),
and point counts for document version embeddings inside self-hosted Qdrant collections (`ADR-M3-001`).
"""

from typing import Any
import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class VectorIndexMetadata(BaseModel):
    """ORM entity tracking index synchronization state between PostgreSQL and Qdrant (`ADR-M3-001`)."""

    __tablename__ = "vector_index_metadata"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "document_version_id",
            "collection_name",
            name="uq_vector_index_tenant_ver_col",
        ),
        Index("ix_vector_metadata_tenant_status_idx", "tenant_id", "status"),
        Index("ix_vector_metadata_doc_ver_idx", "document_id", "document_version_id"),
    )

    tenant_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    collection_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    points_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("status", "PENDING")
        kwargs.setdefault("points_count", 0)
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<VectorIndexMetadata(id={self.id}, collection='{self.collection_name}', "
            f"status='{self.status}', points={self.points_count})>"
        )
