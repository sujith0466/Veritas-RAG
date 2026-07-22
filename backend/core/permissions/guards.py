"""Permission guard checks and abstractions.

Provides reusable evaluation helpers for role and permission authorization.
"""

from .rbac import Role
from .registry import Permission, get_permission_registry


def evaluate_role_access(user_role: Role, allowed_roles: tuple[Role, ...]) -> bool:
    """Evaluate whether user_role is authorized among allowed_roles."""
    if user_role == Role.ADMIN:
        return True
    return user_role in allowed_roles


def evaluate_permission_access(
    user_role: Role, required_permission: Permission
) -> bool:
    """Evaluate whether user_role possesses required_permission using the registry."""
    registry = get_permission_registry()
    return registry.has_permission(user_role, required_permission)
