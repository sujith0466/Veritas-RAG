"""Authentication and user response schemas for API endpoints.

Defines response structures for `/api/v1/auth/me` and `/api/v1/auth/status`.
"""

from pydantic import BaseModel, Field

from backend.core.auth.context import UserContext
from backend.core.permissions.rbac import Role


class AuthStatusResponse(BaseModel):
    """Response payload for authentication status inspection."""

    is_authenticated: bool = Field(description="Whether a valid JWT was provided")
    user: UserContext | None = Field(
        default=None, description="Authenticated user context"
    )

class LoginRequest(BaseModel):
    """Login payload."""
    email: str
    password: str

class LoginResponse(BaseModel):
    """Access token response payload (Refresh token sent via cookie)."""
    access_token: str
    token_type: str = "Bearer"

class ForgotPasswordRequest(BaseModel):
    """Forgot password request payload."""
    email: str

class ResetPasswordRequest(BaseModel):
    """Reset password request payload."""
    token: str
    new_password: str = Field(min_length=8)

class VerifyOTPRequest(BaseModel):
    """Verify OTP request payload."""
    email: str
    otp: str = Field(min_length=6, max_length=6)

class ResetPasswordOTPRequest(BaseModel):
    """Reset password via OTP request payload."""
    email: str
    otp: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8)

class ChangePasswordRequest(BaseModel):
    """Authenticated password change request payload."""
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)

__all__ = [
    "AuthStatusResponse",
    "Role",
    "UserContext",
    "LoginRequest",
    "LoginResponse",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    "VerifyOTPRequest",
    "ResetPasswordOTPRequest",
    "ChangePasswordRequest",
]
