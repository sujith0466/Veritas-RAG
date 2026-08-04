"""Failed Job Diagnostics Entity Model (`FailedJobDiagnostics`).

Forensic failure context and operator remediation state for Dead Letter Queue (DLQ) jobs.
"""

from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class FailedJobDiagnostics(BaseModel):
    """Captures deep diagnostic context for quarantined DLQ jobs."""

    __tablename__ = "failed_job_diagnostics"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    failing_step: Mapped[str] = mapped_column(String(100), nullable=False)
    exception_class: Mapped[str] = mapped_column(String(255), nullable=False)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    payload_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    remediation_status: Mapped[str] = mapped_column(
        String(50), default="PENDING_TRIAGE", index=True, nullable=False
    )
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_failed_jobs_tenant_remediation", "tenant_id", "remediation_status"),
        Index("ix_failed_jobs_job_step", "job_id", "failing_step"),
    )

    def __repr__(self) -> str:
        return f"<FailedJobDiagnostics(id={self.id}, job_id={self.job_id}, step='{self.failing_step}', status='{self.remediation_status}')>"
