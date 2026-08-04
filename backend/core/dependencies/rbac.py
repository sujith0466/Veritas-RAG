"""RBAC permission and role evaluation dependencies.

Provides FastAPI dependency injectors for granular permission enforcement (F4.4).
"""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, status

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.permissions.guards import evaluate_role_access
from backend.core.permissions.rbac import Role
from backend.core.permissions.registry import Permission, get_permission_registry


def require_permission(
    *permissions: Permission | str,
) -> Callable[..., Coroutine[Any, Any, UserContext]]:
    """Return a dependency requiring the user to possess at least one of the specified permissions.
    
    Evaluates role permissions using the central PermissionRegistry with O(1) in-memory lookups.
    """
    async def _permission_guard(
        user_context: UserContext = Depends(get_current_user),
    ) -> UserContext:
        registry = get_permission_registry()
        user_role = Role.from_str(user_context.role) if isinstance(user_context.role, str) else user_context.role

        # Check permissions
        has_access = any(
            registry.has_permission(user_role, p, is_suspended=False)
            for p in permissions
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required one of: {[str(p) for p in permissions]}",
            )
        return user_context

    return _permission_guard


def require_role(
    *roles: Any,
) -> Callable[..., Coroutine[Any, Any, UserContext]]:
    """Return a dependency requiring the user to possess one of the specified roles."""
    flat_roles = []
    for r in roles:
        if isinstance(r, (list, tuple, set)):
            flat_roles.extend(r)
        else:
            flat_roles.append(r)

    async def _role_guard(
        user_context: UserContext = Depends(get_current_user),
    ) -> UserContext:
        user_role = Role.from_str(user_context.role) if isinstance(user_context.role, str) else user_context.role
        has_role = evaluate_role_access(user_role, tuple(flat_roles))
        if not has_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role permissions for this operation.",
            )
        return user_context

    return _role_guard
