"""User and authentication context models.

Defines the request-scoped user context and token payload structures
propagated through FastAPI dependencies and request contexts.
"""

from typing import Any
import uuid

from pydantic import BaseModel, Field

from backend.core.permissions.rbac import Role


class TokenPayload(BaseModel):
    """Payload decoded from a verified Supabase JWT token."""

    sub: str = Field(description="Subject: Supabase Auth user ID")
    email: str | None = Field(default=None, description="User email address if present")
    role: str = Field(
        default="viewer", description="User role from JWT claims or metadata"
    )
    tenant_id: str | None = Field(default=None, description="Multi-tenant ID from JWT")
    workspace_name: str | None = Field(default=None, description="Workspace name from JWT")
    full_name: str | None = Field(default=None, description="User full name from JWT")
    organization_name: str | None = Field(default=None, description="Organization name from JWT")
    exp: int = Field(description="Expiration timestamp (Unix epoch)")
    jti: str | None = Field(default=None, description="JWT ID for token revocation")
    aud: str | list[str] | None = Field(default=None, description="Audience claim")
    iss: str | None = Field(default=None, description="Issuer claim")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional raw claims or user metadata",
    )


class UserContext(BaseModel):
    """Authenticated user context propagated across the request lifecycle."""

    id: uuid.UUID = Field(description="Internal PostgreSQL user primary key")
    email: str = Field(description="User email address")
    role: Role = Field(default=Role.VIEWER, description="Assigned platform role")
    is_active: bool = Field(default=True, description="Account active status")
    is_verified: bool = Field(default=True, description="Account email verification status")
    tenant_id: str | None = Field(default=None, description="Optional multi-tenant ID")
    workspace_name: str | None = Field(default=None, description="Optional workspace name")


    @property
    def user_id(self) -> uuid.UUID:
        """Alias for id."""
        return self.id

    @property
    def is_admin(self) -> bool:
        """Return True if the user has the ADMIN role."""
        return self.role == Role.ADMIN

