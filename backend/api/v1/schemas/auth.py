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

class PasswordResetVerifyResponse(BaseModel):
    """Password reset OTP verification response payload."""
    reset_token: str
    expires_in_seconds: int = 900

class PasswordResetCompleteRequest(BaseModel):
    """Password reset completion payload."""
    email: str
    reset_token: str
    new_password: str = Field(min_length=8)

class ResetPasswordOTPRequest(BaseModel):
    """Reset password via OTP request payload."""
    email: str
    otp: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8)

class ChangePasswordRequest(BaseModel):
    """Authenticated password change request payload."""
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)

class ChangePasswordVerifyCodeRequest(BaseModel):
    """Payload to verify 6-digit security code for authenticated password change."""
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")

class ChangePasswordVerifyCodeResponse(BaseModel):
    """Response returned upon successful security code verification."""
    change_token: str
    expires_in_seconds: int = 900

class ChangePasswordCompleteRequest(BaseModel):
    """Payload to complete authenticated password change using change_token."""
    change_token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)

class DemoRoleSwitchRequest(BaseModel):
    """Request payload to switch demo role."""
    target_role: str = Field(description="Target canonical role to simulate (platform_admin, owner, admin, member, viewer)")
    workspace_id: str | None = Field(default=None, description="Optional target workspace ID context")

class DemoRoleSwitchResponse(BaseModel):
    """Response payload for demo role switch."""
    access_token: str
    token_type: str = "Bearer"
    role: str
    workspace_id: str | None = None
    demo_simulated: bool = True

class DemoRoleResetResponse(BaseModel):
    """Response payload for resetting demo role to base authentic role."""
    access_token: str
    token_type: str = "Bearer"
    role: str
    workspace_id: str | None = None
    demo_simulated: bool = False
    message: str = "Reset to authentic database role successfully"

__all__ = [
    "AuthStatusResponse",
    "Role",
    "UserContext",
    "LoginRequest",
    "LoginResponse",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    "VerifyOTPRequest",
    "PasswordResetVerifyResponse",
    "PasswordResetCompleteRequest",
    "ResetPasswordOTPRequest",
    "ChangePasswordRequest",
    "ChangePasswordVerifyCodeRequest",
    "ChangePasswordVerifyCodeResponse",
    "ChangePasswordCompleteRequest",
    "DemoRoleSwitchRequest",
    "DemoRoleSwitchResponse",
    "DemoRoleResetResponse",
]
