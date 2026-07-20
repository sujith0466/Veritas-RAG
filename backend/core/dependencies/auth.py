"""FastAPI authentication and authorization dependencies.

Provides request-scoped dependency injectors for user identification,
authentication verification, and role/permission enforcement.
"""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth.context import UserContext
from backend.core.auth.middleware import extract_bearer_token
from backend.core.dependencies.database import get_db
from backend.core.exceptions.auth import AuthenticationException
from backend.core.permissions.rbac import Role
from backend.core.permissions.registry import Permission
from backend.services.auth.auth_service import AuthService
from backend.services.auth.authorization_service import AuthorizationService


async def get_optional_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> UserContext | None:
    """Extract and authenticate the request bearer token if present.

    Returns:
        UserContext if a valid token is provided, else None for anonymous requests.

    Raises:
        InvalidTokenException: If a token is provided but has invalid signature/format.
        ExpiredTokenException: If a token is provided but has expired.
    """
    token = extract_bearer_token(request)
    if not token:
        return None

    auth_service = AuthService(session)
    return await auth_service.authenticate_token(token)


async def get_current_user(
    user: UserContext | None = Depends(get_optional_user),
) -> UserContext:
    """Enforce that the request is made by an authenticated user.

    Returns:
        The authenticated UserContext.

    Raises:
        AuthenticationException: If no valid credentials were provided.
    """
    if not user:
        raise AuthenticationException("Authentication required")
    return user


def require_authenticated() -> Callable[..., Coroutine[Any, Any, UserContext]]:
    """Dependency requirement ensuring the request is authenticated."""
    return get_current_user


def require_role(*roles: Role) -> Callable[..., Coroutine[Any, Any, UserContext]]:
    """Return a dependency requiring the authenticated user to possess one of the roles.

    Args:
        *roles: One or more allowed Role enums.

    Returns:
        FastAPI dependency function enforcing the role check.
    """

    async def _role_guard(
        user: UserContext = Depends(get_current_user),
    ) -> UserContext:
        authz_service = AuthorizationService()
        authz_service.verify_role(user, *roles)
        return user

    return _role_guard


def require_permission(
    permission: Permission,
) -> Callable[..., Coroutine[Any, Any, UserContext]]:
    """Return a dependency requiring the user's role to grant the specified permission.

    Args:
        permission: The required Permission enum.

    Returns:
        FastAPI dependency function enforcing the permission check.
    """

    async def _permission_guard(
        user: UserContext = Depends(get_current_user),
    ) -> UserContext:
        authz_service = AuthorizationService()
        authz_service.verify_permission(user, permission)
        return user

    return _permission_guard
