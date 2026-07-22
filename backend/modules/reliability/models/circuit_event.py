"""Circuit Breaker Event Log ORM Model (`CircuitBreakerEventLog`).

Records circuit breaker state transitions (e.g., CLOSED -> OPEN)
and recovery events across tenant namespaces (`ADR-005`).
"""

from typing import Any

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class CircuitBreakerEventLog(BaseModel):
    """ORM entity logging circuit breaker state transitions and trip reasons."""

    __tablename__ = "circuit_breaker_events"
    __table_args__ = (
        Index(
            "ix_circuit_events_tenant_target",
            "tenant_id",
            "target_module",
            "created_at",
        ),
    )

    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    target_module: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    previous_state: Mapped[str] = mapped_column(String(50), nullable=False)
    new_state: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return (
            f"<CircuitBreakerEventLog(id={self.id}, tenant='{self.tenant_id}', "
            f"transition='{self.previous_state} -> {self.new_state}')>"
        )
