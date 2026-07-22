"""Retrieval Query Log ORM Model (`RetrievalQueryLog`).

Records execution statistics, stage latencies, and candidate density counts across
every multi-stage hybrid search query for tenant audit trails and KPI monitoring (`ADR-005`).
"""

from typing import Any

from sqlalchemy import JSON, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class RetrievalQueryLog(BaseModel):
    """ORM entity logging multi-stage search execution statistics and latency breakdowns."""

    __tablename__ = "retrieval_queries"
    __table_args__ = (
        Index("ix_retrieval_queries_tenant_created_idx", "tenant_id", "created_at"),
        Index("ix_retrieval_queries_tenant_corr_idx", "tenant_id", "correlation_id"),
    )

    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    dense_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sparse_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    merged_unique_count: Mapped[int] = mapped_column(Integer, nullable=False)
    final_top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    total_duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    stage_breakdown_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<RetrievalQueryLog(id={self.id}, tenant='{self.tenant_id}', "
            f"query='{self.query_text[:30]}...', duration_ms={self.total_duration_ms})>"
        )
