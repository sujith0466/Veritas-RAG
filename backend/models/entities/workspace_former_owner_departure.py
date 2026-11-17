"""Workspace Former Owner Departure Entity Model.

Represents the historical departure, transition, or retention record of a former workspace OWNER.
Governed by Section 7 Batch 3 (WP 7.10, PO-D32-03).
"""

from datetime import datetime
import enum
from typing import Any, Optional
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.database.base import Base


class FormerOwnerDepartureType(str, enum.Enum):
    """Enumeration of recognized former owner departure outcomes."""

    VOLUNTARY_LEAVE = "VOLUNTARY_LEAVE"
    NEW_OWNER_REMOVED = "NEW_OWNER_REMOVED"
    NEW_OWNER_RETAINED = "NEW_OWNER_RETAINED"
    TIMEOUT_AUTO_REMOVED = "TIMEOUT_AUTO_REMOVED"


class WorkspaceFormerOwnerDeparture(Base):
    """Immutable record tracking the departure, role reduction, or removal of a former workspace OWNER."""

    __tablename__ = "workspace_former_owner_departures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    former_owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    transfer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspace_ownership_transfers.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    departure_type = Column(String(30), nullable=False)
    former_role = Column(String(50), nullable=False, default="OWNER", server_default="OWNER")
    retained_role = Column(String(50), nullable=True)
    departure_confirmed_at = Column(DateTime(timezone=True), nullable=False)
    confirmed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    departure_notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    # Relationships
    workspace = relationship("Workspace", backref="former_owner_departures")
    former_owner = relationship("User", foreign_keys=[former_owner_id])
    confirmed_by = relationship("User", foreign_keys=[confirmed_by_user_id])
    transfer = relationship(
        "WorkspaceOwnershipTransfer",
        foreign_keys=[transfer_id],
        back_populates="former_owner_departure",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert entity instance to dictionary representation."""
        return {
            "id": str(self.id) if self.id else None,
            "workspace_id": str(self.workspace_id) if self.workspace_id else None,
            "former_owner_id": str(self.former_owner_id) if self.former_owner_id else None,
            "transfer_id": str(self.transfer_id) if self.transfer_id else None,
            "departure_type": self.departure_type,
            "former_role": self.former_role,
            "retained_role": self.retained_role,
            "departure_confirmed_at": (
                self.departure_confirmed_at.isoformat()
                if self.departure_confirmed_at
                else None
            ),
            "confirmed_by_user_id": (
                str(self.confirmed_by_user_id) if self.confirmed_by_user_id else None
            ),
            "departure_notes": self.departure_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
