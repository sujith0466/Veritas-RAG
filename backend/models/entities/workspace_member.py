import datetime
import enum
from typing import Any
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.models.base import BaseModel


class MemberStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class WorkspaceRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"

    @classmethod
    def from_str(cls, value: str | None) -> "WorkspaceRole":
        """Safely parse string into WorkspaceRole enum with fallback to MEMBER."""
        if not value:
            return cls.MEMBER
        val_upper = value.strip().upper()
        try:
            return cls(val_upper)
        except ValueError:
            return cls.MEMBER

    @classmethod
    def is_valid(cls, value: str | None) -> bool:
        """Check if string is an exact valid workspace membership role."""
        if not value:
            return False
        return value.strip().upper() in {r.value for r in cls}

    def to_rbac_role(self) -> Any:
        """Convert uppercase WorkspaceRole to lowercase RBAC Role."""
        from backend.core.permissions.rbac import Role
        return Role(self.value.lower())

    @classmethod
    def from_rbac_role(cls, role: Any) -> "WorkspaceRole":
        """Convert RBAC Role to uppercase WorkspaceRole."""
        val = role.value if hasattr(role, "value") else str(role)
        return cls(val.strip().upper())


class WorkspaceMember(BaseModel):
    """Associates users with workspaces and defines their role and lifecycle status."""

    __tablename__ = "workspace_members"

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
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # "OWNER", "ADMIN", "MEMBER", "VIEWER"
    status: Mapped[str] = mapped_column(
        String(50), default=MemberStatus.ACTIVE.value, nullable=False
    )
    last_active_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    member_metadata: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    joined_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    workspace = relationship("Workspace", backref="members", lazy="selectin")
    user = relationship("User", foreign_keys=[user_id], lazy="selectin")
    invited_by = relationship("User", foreign_keys=[invited_by_user_id], lazy="selectin")
