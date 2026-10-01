"""Permission guard checks and abstractions.

Provides reusable evaluation helpers for role and permission authorization.
"""

from .rbac import Role
from .registry import Permission, get_permission_registry


ROLE_HIERARCHY: dict[Role, int] = {
    Role.PLATFORM_ADMIN: 100,
    Role.OWNER: 90,
    Role.ADMIN: 80,
    Role.ENGINEER: 70,
    Role.ANALYST: 60,
    Role.MEMBER: 50,
    Role.VIEWER: 10,
    Role.PLATFORM_SUPPORT: 5,
    Role.PLATFORM_AUDITOR: 5,
}


def evaluate_role_access(
    user_role: Role | str,
    allowed_roles: tuple[Role | str, ...],
    is_suspended: bool = False,
) -> bool:
    """Evaluate whether user_role is authorized among allowed_roles according to role hierarchy."""
    if is_suspended:
        return False

    if isinstance(user_role, str):
        user_role = Role.from_str(user_role)

    parsed_allowed = [
        Role.from_str(r) if isinstance(r, str) else r for r in allowed_roles
    ]

    # Platform Admin exclusive isolation: if only PLATFORM_ADMIN is allowed, only PLATFORM_ADMIN can enter
    if Role.PLATFORM_ADMIN in parsed_allowed and len(parsed_allowed) == 1:
        return user_role == Role.PLATFORM_ADMIN

    # PLATFORM_ADMIN has super-authority across all standard routes
    if user_role == Role.PLATFORM_ADMIN:
        return True

    # Owner exclusive isolation: if only OWNER is allowed, ADMIN cannot enter
    if Role.OWNER in parsed_allowed and len(parsed_allowed) == 1:
        return user_role == Role.OWNER

    # Admin and Owner possess authority over standard workspace routes
    if user_role in (Role.ADMIN, Role.OWNER):
        return True

    # Viewer routes are accessible to all active workspace roles
    if Role.VIEWER in parsed_allowed and user_role in (
        Role.MEMBER,
        Role.ENGINEER,
        Role.ANALYST,
        Role.VIEWER,
    ):
        return True

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
