"""Registration schemas and validation."""

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegistrationRequest(BaseModel):
    """Schema for new user registration (WP-8).

    Accepts credentials and profile data only. Registration is strictly decoupled
    from workspace creation and joining. Dead onboarding fields (workspace_id,
    join_code, invitation_token, workspace_name, company_name) are stripped
    from the schema and ignored without breaking legacy callers.
    """
    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str | None = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password_policy(cls, v: str) -> str:
        """Validate password meets security policy.

        Requirements:
        - Minimum 8 characters (handled by Field)
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 number
        - At least 1 special character
        """
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_\+=\[\]\\/;'~`]", v):
            raise ValueError("Password must contain at least one special character.")
        return v


class RegistrationResponse(BaseModel):
    """Schema for successful registration response."""
    message: str = "Registration successful. Please check your email to verify your account."
