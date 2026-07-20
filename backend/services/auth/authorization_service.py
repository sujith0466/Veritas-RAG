"""Authorization Service.

Explicitly separated from authentication, this service encapsulates all
RBAC evaluation and permission checks using the central PermissionRegistry.
"""

import structlog

from backend.core.auth.context import UserContext
from backend.core.exceptions.auth import InsufficientRoleException
from backend.core.permissions.rbac import Role
from backend.core.permissions.registry import (
    Permission,
    PermissionRegistry,
    get_permission_registry,
)

logger = structlog.get_logger(__name__)


class AuthorizationService:
    """Evaluates role access and granular permissions against the central registry."""

    def __init__(self, registry: PermissionRegistry | None = None) -> None:
        self.registry = registry or get_permission_registry()

    def check_role(self, user: UserContext, *allowed_roles: Role) -> bool:
        """Return True if the user's role is in allowed_roles or is ADMIN."""
        if user.role == Role.ADMIN:
            return True
        return user.role in allowed_roles

    def check_permission(self, user: UserContext, permission: Permission) -> bool:
        """Return True if the user's role grants the required permission."""
        return self.registry.has_permission(user.role, permission)

    def verify_role(self, user: UserContext, *allowed_roles: Role) -> None:
        """Verify the user possesses an allowed role, raising InsufficientRoleException if denied."""
        if not self.check_role(user, *allowed_roles):
            logger.warning(
                "Role authorization check failed",
                user_id=str(user.id),
                user_role=user.role.value,
                allowed_roles=[r.value for r in allowed_roles],
            )
            raise InsufficientRoleException(
                f"Operation requires role in {[r.value for r in allowed_roles]}; current role is {user.role.value}"
            )

    def verify_permission(self, user: UserContext, permission: Permission) -> None:
        """Verify the user has the required permission, raising InsufficientRoleException if denied."""
        if not self.check_permission(user, permission):
            logger.warning(
                "Permission authorization check failed",
                user_id=str(user.id),
                user_role=user.role.value,
                required_permission=permission.value,
            )
            raise InsufficientRoleException(
                f"Missing required permission '{permission.value}' for role '{user.role.value}'"
            )
