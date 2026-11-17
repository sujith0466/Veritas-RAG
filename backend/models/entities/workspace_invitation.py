"""Workspace Invitation Entity Model.

Represents a time-bounded, cryptographically hashed invitation to join a workspace.
"""

import datetime
from datetime import UTC
import enum
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import BaseModel


class InvitationStatus(str, enum.Enum):
    """Lifecycle statuses for a workspace invitation."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    CANCELED = "CANCELED"


class WorkspaceInvitation(BaseModel):
    """The workspace invitation entity."""

    __tablename__ = "workspace_invitations"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # "ADMIN", "MEMBER", "VIEWER"
    token_selector: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=InvitationStatus.PENDING.value, nullable=False
    )
    is_legacy_bound: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    resend_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_resent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    workspace = relationship("Workspace", backref="invitations", lazy="selectin")
    invited_by = relationship("User", foreign_keys=[invited_by_user_id], lazy="selectin")
    revoked_by = relationship("User", foreign_keys=[revoked_by_user_id], lazy="selectin")


class WorkspaceInvitationRedemption(BaseModel):
    """Immutable redemption ledger for reusable multi-user invitation links.
    
    Tracks distinct users who redeemed an invitation link.
    Protected with ON DELETE RESTRICT to guarantee audit retention.
    """

    __tablename__ = "workspace_invitation_redemptions"

    invitation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace_invitations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    redeemed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    invitation = relationship("WorkspaceInvitation", backref="redemptions", lazy="selectin")
    workspace = relationship("Workspace", lazy="selectin")
    user = relationship("User", lazy="selectin")

    __table_args__ = (
        Index("uq_wir_redemption", "invitation_id", "user_id", unique=True),
        Index("idx_wir_invitation", "invitation_id"),
        Index("idx_wir_user", "user_id"),
    )

