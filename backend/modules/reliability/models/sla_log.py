"""Retrieval SLA Log ORM Model (`RetrievalSLALog`).

Records execution latency compliance against SLA budgets ($400\text{ms}$)
and tracks degraded fallback/broadening activations for tenant audit trails (`ADR-005`).
"""

from typing import Any

from sqlalchemy import Boolean, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class RetrievalSLALog(BaseModel):
    """ORM entity logging search latency compliance and fallback activations."""

    __tablename__ = "retrieval_sla_logs"
    __table_args__ = (
        Index("ix_sla_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_sla_logs_tenant_breach", "tenant_id", "is_sla_breached"),
        Index("ix_sla_logs_tenant_degraded", "tenant_id", "is_degraded_fallback"),
    )

    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_module: Mapped[str] = mapped_column(
        String(100), nullable=False, default="qdrant_hybrid"
    )
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    is_sla_breached: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_degraded_fallback: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    fallback_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<RetrievalSLALog(id={self.id}, tenant='{self.tenant_id}', "
            f"duration={self.duration_ms}ms, breached={self.is_sla_breached}, degraded={self.is_degraded_fallback})>"
        )
