"""Permission guard checks and abstractions.

Provides reusable evaluation helpers for role and permission authorization.
"""

from .rbac import Role
from .registry import Permission, get_permission_registry


def evaluate_role_access(
    user_role: Role | str,
    allowed_roles: tuple[Role | str, ...],
    is_suspended: bool = False,
) -> bool:
    """Evaluate whether user_role is authorized among allowed_roles."""
    if is_suspended:
        return False

    if isinstance(user_role, str):
        user_role = Role.from_str(user_role)

    if user_role in (Role.ADMIN, Role.PLATFORM_ADMIN, Role.OWNER):
        return True

    parsed_allowed = [
        Role.from_str(r) if isinstance(r, str) else r for r in allowed_roles
    ]
    return user_role in parsed_allowed


def evaluate_permission_access(
    user_role: Role | str,
    required_permission: Permission | str,
    is_suspended: bool = False,
) -> bool:
    """Evaluate whether user_role possesses required_permission using the registry."""
    registry = get_permission_registry()
    return registry.has_permission(
        user_role, required_permission, is_suspended=is_suspended
    )
