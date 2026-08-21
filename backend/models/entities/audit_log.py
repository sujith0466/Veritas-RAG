"""Audit Log Entity Model.

Records security and operational actions across the platform for traceability and compliance.
"""

from typing import Any
import uuid

from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import ImmutableBaseModel


class AuditLog(ImmutableBaseModel):
    """Immutable WORM audit trail entry for tracking system actions and security events.

    Inherits from ImmutableBaseModel (id, created_at).
    Does NOT contain is_deleted or updated_at to ensure append-only compliance.
    """

    __tablename__ = "audit_logs"


    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action='{self.action}', status='{self.status}')>"
        )
