"""Processing Job Step Entity Model.

Granular per-step execution tracking entity.
"""

from datetime import datetime
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class ProcessingJobStep(BaseModel):
    """Granular per-step execution tracking entity."""

    __tablename__ = "processing_job_steps"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    step_status: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checkpoint_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_job_steps_job_step", "job_id", "step_name"),
        Index("ix_job_steps_job_status", "job_id", "step_status"),
    )

    def __repr__(self) -> str:
        return f"<ProcessingJobStep(id={self.id}, job_id={self.job_id}, step='{self.step_name}', status='{self.step_status}')>"
