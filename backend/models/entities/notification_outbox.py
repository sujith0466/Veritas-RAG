"""Notification Outbox Entity Model.

Implements a durable transactional outbox with lease-based claiming,
double-check locking synchronization, and at-least-once external delivery.
"""

import datetime
from datetime import UTC
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import BaseModel


class NotificationOutbox(BaseModel):
    """Transactional outbox for join-code expiration alerts."""

    __tablename__ = "notification_outbox"

    join_code_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace_join_codes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    join_code_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    checkpoint: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )  # "3D", "24H", "1H", "EXPIRED"
    channel: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )  # "IN_APP", "EMAIL"
    status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING",
        nullable=False,
        index=True,
    )  # "PENDING", "CLAIMED", "SENT", "FAILED", "CANCELLED"

    idempotency_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    lease_expires_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    scheduled_for: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(UTC),
        nullable=False,
    )
    sent_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    join_code = relationship("WorkspaceJoinCode", lazy="selectin")
    workspace = relationship("Workspace", lazy="selectin")
    recipient = relationship("User", lazy="selectin")

    __table_args__ = (
        Index(
            "idx_notif_outbox_claim",
            "status",
            "scheduled_for",
            "lease_expires_at",
            postgresql_where=(status.in_(["PENDING", "CLAIMED"])),
        ),
    )
