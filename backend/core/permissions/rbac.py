"""Role-Based Access Control (RBAC) definitions.

Defines the core workspace and platform role hierarchies and enums.
"""

from enum import StrEnum


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

    @property
    def is_workspace_admin_or_owner(self) -> bool:
        """Return True if role is Owner, Admin, or Platform Admin."""
        return self in (Role.OWNER, Role.ADMIN, Role.PLATFORM_ADMIN)
