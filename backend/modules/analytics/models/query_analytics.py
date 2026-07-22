"""Query Analytics Record ORM Model (`QueryAnalyticsRecord`).

Stores execution history, confidence trends, retry statistics, and reliability scores
for every AI query processed by the Execution Gateway (`Phase 4 Milestone 1`).
"""

from typing import Any

from sqlalchemy import Boolean, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class QueryAnalyticsRecord(BaseModel):
    """ORM entity recording execution outcomes, confidence, hallucination, and latency."""

    __tablename__ = "query_analytics_records"
    __table_args__ = (
        Index("ix_query_analytics_tenant_created_idx", "tenant_id", "created_at"),
        Index("ix_query_analytics_tenant_outcome_idx", "tenant_id", "outcome"),
        Index("ix_query_analytics_corr_idx", "correlation_id", unique=True),
    )

    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # SUCCESS, CLARIFICATION_REQUIRED, etc.
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hallucination_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reliability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    is_safe_to_serve: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("is_safe_to_serve", True)
        kwargs.setdefault("retry_attempts", 0)
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<QueryAnalyticsRecord(id={self.id}, tenant='{self.tenant_id}', "
            f"outcome='{self.outcome}', reliability={self.reliability_score})>"
        )
