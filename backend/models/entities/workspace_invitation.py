"""Workspace Invitation Entity Model.

Represents a time-bounded, cryptographically hashed invitation to join a workspace.
"""

import datetime
import enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String
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
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # "ADMIN", "MEMBER", "VIEWER"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=InvitationStatus.PENDING.value, nullable=False
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
