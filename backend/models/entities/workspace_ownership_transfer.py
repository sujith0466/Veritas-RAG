"""Workspace Ownership Transfer Entity Model.

Represents a formal ownership nomination, handover, and former owner lifecycle within a workspace.
Governed by Section 7 Batch 1 & Batch 2 (V3.0).
"""

from datetime import datetime
import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.database.base import Base


class TransferStatus(str, enum.Enum):
    """Lifecycle statuses for workspace ownership transfers."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class FormerOwnerChoice(str, enum.Enum):
    """Former owner disposition choices."""

    PENDING = "PENDING"
    STAY = "STAY"
    LEAVE = "LEAVE"


class DecisionStatus(str, enum.Enum):
    """Lifecycle status of the role decision for the former owner."""

    PENDING = "PENDING"
    DECIDED_ADMIN = "DECIDED_ADMIN"
    DECIDED_MEMBER = "DECIDED_MEMBER"
    DECIDED_REMOVED = "DECIDED_REMOVED"
    FALLBACK_ADMIN = "FALLBACK_ADMIN"
    TIMED_OUT = "TIMED_OUT"


class ReminderType(str, enum.Enum):
    """Reminder notifications scheduled for the new owner."""

    DAY_14 = "DAY_14"
    DAY_25 = "DAY_25"
    DAY_29 = "DAY_29"


class ReminderStatus(str, enum.Enum):
    """Status of scheduled role decision reminder."""

    PENDING = "PENDING"
    SENT = "SENT"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class WorkspaceOwnershipTransfer(Base):
    """Entity representing a workspace ownership transfer nomination and lifecycle."""

    __tablename__ = "workspace_ownership_transfers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    nominated_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    nominee_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status = Column(String(30), nullable=False, default=TransferStatus.PENDING.value)
    rejection_reason = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    expired_at = Column(DateTime(timezone=True), nullable=True)

    # Batch 2 Lifecycle fields
    former_owner_choice = Column(
        String(20), nullable=False, default=FormerOwnerChoice.PENDING.value, server_default="PENDING"
    )
    former_owner_choice_at = Column(DateTime(timezone=True), nullable=True)
    decision_status = Column(
        String(30), nullable=False, default=DecisionStatus.PENDING.value, server_default="PENDING"
    )
    decision_deadline_at = Column(DateTime(timezone=True), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    response_notes = Column(Text, nullable=True)
    decision_notes = Column(Text, nullable=True)

    # Batch 3 Snapshot & History Protection fields (WP 7.12, WP 7.13)
    current_owner_email_snapshot = Column(String(255), nullable=False)
    nominated_user_email_snapshot = Column(String(255), nullable=False)

    workspace = relationship("Workspace", backref="ownership_transfers")
    nominated_by = relationship("User", foreign_keys=[nominated_by_user_id])
    nominee = relationship("User", foreign_keys=[nominee_user_id])
    decided_by = relationship("User", foreign_keys=[decided_by_user_id])
    former_owner_departure = relationship(
        "WorkspaceFormerOwnerDeparture",
        back_populates="transfer",
        uselist=False,
    )
    reminders = relationship(
        "WorkspaceOwnershipRoleReminder",
        back_populates="transfer",
        cascade="all, delete-orphan",
        order_by="WorkspaceOwnershipRoleReminder.scheduled_for",
    )


class WorkspaceOwnershipRoleReminder(Base):
    """Entity tracking scheduled reminders to new owner regarding role decision."""

    __tablename__ = "workspace_ownership_role_reminders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transfer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspace_ownership_transfers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    recipient_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reminder_type = Column(String(20), nullable=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        String(20), nullable=False, default=ReminderStatus.PENDING.value, server_default="PENDING"
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now())

    transfer = relationship("WorkspaceOwnershipTransfer", back_populates="reminders")
    workspace = relationship("Workspace")
    recipient = relationship("User", foreign_keys=[recipient_user_id])
