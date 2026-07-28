"""LLM audit telemetry records for post-incident investigation."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class LLMAuditRecord(BaseModel):
    """Secure audit record for LLM request/response telemetry."""

    __tablename__ = "llm_audit_records"
    __table_args__ = (
        Index("ix_llm_audit_corr_idx", "correlation_id"),
        Index("ix_llm_audit_provider_model_idx", "provider", "model"),
        Index("ix_llm_audit_created_idx", "created_at"),
    )

    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    response_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    raw_response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
