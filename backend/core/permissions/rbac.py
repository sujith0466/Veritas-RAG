"""Role-Based Access Control (RBAC) definitions.

Defines the core role hierarchy and enums used across the enterprise platform.
"""

from enum import StrEnum


class Role(StrEnum):
    """Platform roles ordered by decreasing authority."""

    ADMIN = "admin"
    ENGINEER = "engineer"
    ANALYST = "analyst"
    VIEWER = "viewer"

    @classmethod
    def from_str(cls, value: str | None) -> "Role":
        """Safely parse string into Role enum with fallback to VIEWER."""
        if not value:
            return cls.VIEWER
        try:
            return cls(value.lower())
        except ValueError:
            return cls.VIEWER
