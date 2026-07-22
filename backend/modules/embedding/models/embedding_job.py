"""Embedding Job ORM Model (`EmbeddingJob`).

Tracks asynchronous batch vectorization jobs across tenant namespaces,
recording progress counters (`processed_chunks / total_chunks`), token consumption, and status transitions.
"""

import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class EmbeddingJob(BaseModel):
    """ORM entity tracking asynchronous batch embedding jobs."""

    __tablename__ = "embedding_jobs"
    __table_args__ = (
        Index(
            "ix_embedding_jobs_tenant_doc_ver_idx",
            "tenant_id",
            "document_version_id",
            "status",
        ),
        Index("ix_embedding_jobs_tenant_created_idx", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens_consumed: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<EmbeddingJob(id={self.id}, status='{self.status}', processed={self.processed_chunks}/{self.total_chunks})>"
