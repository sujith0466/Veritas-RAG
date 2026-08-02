"""FastAPI authentication and authorization dependencies.

Provides request-scoped dependency injectors for user identification,
authentication verification, and role/permission enforcement.
"""

from collections.abc import Callable, Coroutine
from typing import Any
import uuid

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.auth.context import UserContext
from backend.core.dependencies.database import get_db
from backend.core.exceptions.auth import AuthenticationException
from backend.core.permissions.rbac import Role
from backend.models.entities.user import User

async def get_optional_user(
    request: Request,
) -> UserContext | None:
    """Retrieve the UserContext injected by the JWTAuthenticationMiddleware.
    
    Returns:
        UserContext if a valid token is provided, else None for anonymous requests.
    """
    return getattr(request.state, "user_context", None)


async def get_current_user(
    user_context: UserContext | None = Depends(get_optional_user),
) -> UserContext:
    """Enforce that the request is made by an authenticated user.

    Returns:
        The UserContext from the middleware.

    Raises:
        AuthenticationException: If no valid credentials were provided.
    """
    if not user_context:
        raise AuthenticationException("Authentication required")
    return user_context

def require_active_user() -> Callable[..., Coroutine[Any, Any, User]]:
    """Dependency requirement ensuring the request is authenticated and user is active."""
    async def _active_guard(
        user_context: UserContext = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> User:
        user_id = user_context.id
        stmt = select(User).where(User.id == user_id, User.is_deleted.is_(False))
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise AuthenticationException("Account is inactive")
        return user
    return _active_guard

def require_verified_user() -> Callable[..., Coroutine[Any, Any, User]]:
    """Dependency requirement ensuring the user is verified."""
    async def _verified_guard(
        user: User = Depends(require_active_user()),
    ) -> User:
        if not user.is_verified:
            raise AuthenticationException("Account is not verified")
        return user
    return _verified_guard

def require_workspace() -> Callable[..., Coroutine[Any, Any, UserContext]]:
    """Dependency requirement ensuring the token has a workspace_id."""
    async def _workspace_guard(
        user_context: UserContext = Depends(get_current_user),
    ) -> UserContext:
        if not user_context.workspace_name:
            raise AuthenticationException("Workspace context required")
        return user_context
    return _workspace_guard

def require_role(*roles: Role) -> Callable[..., Coroutine[Any, Any, UserContext]]:
    """Return a dependency requiring the authenticated user to possess one of the roles.

    Args:
        *roles: One or more allowed Role enums.

    Returns:
        FastAPI dependency function enforcing the role check.
    """
    async def _role_guard(
        user_context: UserContext = Depends(get_current_user),
    ) -> UserContext:
        if user_context.role not in roles:
            raise AuthenticationException("Insufficient permissions")
        return user_context
    return _role_guard
