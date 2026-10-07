"""Workspace Access Request Entity Model.

Represents a formal request by a user to either elevate their role in a workspace
or receive administrator approval to join a workspace protected by approval policy.
"""

import datetime
import enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import BaseModel


class AccessRequestType(str, enum.Enum):
    """Types of workspace access requests."""

    ROLE_ELEVATION = "ROLE_ELEVATION"
    JOIN_APPROVAL = "JOIN_APPROVAL"


class AccessRequestStatus(str, enum.Enum):
    """Lifecycle statuses for a workspace access request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class WorkspaceAccessRequest(BaseModel):
    """Entity representing a role elevation or join approval access request."""

    __tablename__ = "workspace_access_requests"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AccessRequestType.ROLE_ELEVATION.value
    )
    current_role: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    requested_role: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default=AccessRequestStatus.PENDING.value, nullable=False, index=True
    )
    reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    # Relationships
    workspace = relationship("Workspace", backref="access_requests")
    user = relationship("User", foreign_keys=[user_id], backref="access_requests")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])

    __table_args__ = (
        Index(
            "uq_active_pending_access_request",
            "workspace_id",
            "user_id",
            "request_type",
            unique=True,
            postgresql_where=(status == "PENDING"),
        ),
        Index(
            "ix_workspace_access_requests_workspace_status",
            "workspace_id",
            "status",
        ),
    )
