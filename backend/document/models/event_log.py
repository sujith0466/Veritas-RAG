"""Document Event Log Entity Model.

Immutable ledger of domain events emitted across the document processing lifecycle.
"""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class DocumentEventLog(BaseModel):
    """Domain event log entry for document tracking and audit."""

    __tablename__ = "document_events"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    triggered_by: Mapped[str] = mapped_column(
        String(100), default="system", nullable=False
    )

    def __repr__(self) -> str:
        return f"<DocumentEventLog(id={self.id}, doc_id={self.document_id}, event='{self.event_type}')>"
