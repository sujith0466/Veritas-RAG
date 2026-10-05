"""Role-Based Access Control (RBAC) definitions.

Defines the core workspace and platform role hierarchies and enums.
"""

from enum import StrEnum
from typing import Any


class Role(StrEnum):
    """Platform / Workspace roles ordered by decreasing authority."""

    # Workspace & Platform Roles
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    ENGINEER = "engineer"
    ANALYST = "analyst"
    VIEWER = "viewer"

    # Platform Roles
    PLATFORM_ADMIN = "platform_admin"
    PLATFORM_SUPPORT = "platform_support"
    PLATFORM_AUDITOR = "platform_auditor"

    @classmethod
    def from_str(cls, value: str | None) -> "Role":
        """Safely parse string into Role enum with fallback to VIEWER."""
        if not value:
            return cls.VIEWER
        try:
            return cls(value.lower())
        except ValueError:
            return cls.VIEWER

    @classmethod
    def is_workspace_role(cls, role: "Role | str | None") -> bool:
        """Check if role is one of the valid workspace membership roles (OWNER, ADMIN, MEMBER, VIEWER)."""
        if not role:
            return False
        val = role.value if isinstance(role, cls) else str(role).strip().lower()
        return val in (cls.OWNER.value, cls.ADMIN.value, cls.MEMBER.value, cls.VIEWER.value)

    def to_workspace_role(self) -> Any:
        """Convert RBAC role to uppercase WorkspaceRole enum. Raises ValueError if not a workspace role."""
        if not self.is_workspace_role(self):
            raise ValueError(f"Role '{self.value}' is not a valid workspace membership role.")
        from backend.models.entities.workspace_member import WorkspaceRole
        return WorkspaceRole(self.value.upper())

    @property
    def is_workspace_admin_or_owner(self) -> bool:
        """Return True if role is Owner, Admin, or Platform Admin."""
        return self in (Role.OWNER, Role.ADMIN, Role.PLATFORM_ADMIN)


# Canonical workspace membership roles
WORKSPACE_ROLES: tuple[Role, ...] = (
    Role.OWNER,
    Role.ADMIN,
    Role.MEMBER,
    Role.VIEWER,
)
