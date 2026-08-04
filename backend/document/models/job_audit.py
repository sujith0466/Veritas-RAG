"""Processing Job Audit Log Entity Model.

Append-only audit trail for all job lifecycle events.
"""

from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class ProcessingJobAuditLog(BaseModel):
    """Append-only audit trail for all job lifecycle events."""

    __tablename__ = "processing_job_audit_logs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_job_audit_job_timestamp", "job_id", "timestamp"),
        Index("ix_job_audit_job_event", "job_id", "event"),
    )

    def __repr__(self) -> str:
        return f"<ProcessingJobAuditLog(id={self.id}, job_id={self.job_id}, event='{self.event}')>"
