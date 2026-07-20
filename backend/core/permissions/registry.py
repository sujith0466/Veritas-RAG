"""Permission Registry.

Centralizes all permission definitions and role-to-permission mappings.
Decouples granular action checks from hardcoded role strings across endpoints.
"""

from enum import StrEnum
from functools import lru_cache

from .rbac import Role


class Permission(StrEnum):
    """Granular permissions across platform capabilities."""

    READ_KNOWLEDGE = "read:knowledge"
    WRITE_KNOWLEDGE = "write:knowledge"
    RUN_QUERY = "run:query"
    ADMIN_SETTINGS = "admin:settings"
    VIEW_DETAILED_HEALTH = "view:detailed_health"
    MANAGE_USERS = "manage:users"
    MANAGE_KEYS = "manage:keys"


class PermissionRegistry:
    """Registry centralizing role-to-permission mappings and lookup logic."""

    def __init__(self) -> None:
        self._role_permissions: dict[Role, set[Permission]] = {}
        self._setup_defaults()

    def _setup_defaults(self) -> None:
        """Register baseline role-to-permission mappings."""
        all_permissions = set(Permission)

        self._role_permissions[Role.ADMIN] = all_permissions
        self._role_permissions[Role.ENGINEER] = {
            Permission.READ_KNOWLEDGE,
            Permission.WRITE_KNOWLEDGE,
            Permission.RUN_QUERY,
            Permission.MANAGE_KEYS,
        }
        self._role_permissions[Role.ANALYST] = {
            Permission.READ_KNOWLEDGE,
            Permission.RUN_QUERY,
        }
        self._role_permissions[Role.VIEWER] = {
            Permission.READ_KNOWLEDGE,
        }

    def register_role_permissions(
        self, role: Role, permissions: set[Permission]
    ) -> None:
        """Register or overwrite permissions assigned to a role."""
        self._role_permissions[role] = permissions

    def get_permissions_for_role(self, role: Role) -> set[Permission]:
        """Return all permissions granted to a given role."""
        return self._role_permissions.get(role, set())

    def has_permission(self, role: Role, permission: Permission) -> bool:
        """Check if a given role possesses the specified permission."""
        if role == Role.ADMIN:
            return True
        return permission in self.get_permissions_for_role(role)


@lru_cache(maxsize=1)
def get_permission_registry() -> PermissionRegistry:
    """Return the singleton instance of the PermissionRegistry."""
    return PermissionRegistry()
