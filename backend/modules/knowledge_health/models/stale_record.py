"""ORM entity representing chunks requiring re-vectorization after model rotations (`stale_embedding_records`)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from backend.database.base import Base


class StaleEmbeddingRecord(Base):
    """ORM table for tracking chunks needing re-embedding after model rotation or config drift."""

    __tablename__ = "stale_embedding_records"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(100), nullable=False, index=True)
    chunk_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_provider = Column(String(50), nullable=False)
    old_model_name = Column(String(100), nullable=False)
    target_provider = Column(String(50), nullable=False)
    target_model_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    def __repr__(self) -> str:
        return f"<StaleEmbeddingRecord(id={self.id}, tenant_id='{self.tenant_id}', chunk_id={self.chunk_id}, status='{self.status}')>"
