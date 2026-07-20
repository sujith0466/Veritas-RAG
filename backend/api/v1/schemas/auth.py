"""Authentication and user response schemas for API endpoints.

Defines response structures for `/api/v1/auth/me` and `/api/v1/auth/status`.
"""

from pydantic import BaseModel, Field

from backend.core.auth.context import UserContext
from backend.core.permissions.rbac import Role


class AuthStatusResponse(BaseModel):
    """Response payload for authentication status inspection."""

    is_authenticated: bool = Field(description="Whether a valid JWT was provided")
    user: UserContext | None = Field(default=None, description="Authenticated user context")


__all__ = [
    "AuthStatusResponse",
    "Role",
    "UserContext",
]
