"""Registration schemas and validation."""

import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegistrationRequest(BaseModel):
    """Schema for new user registration with optional onboarding context."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str | None = Field(default=None, max_length=100)

    # WS-A1 Onboarding Context
    workspace_id: str | None = Field(
        default=None,
        max_length=64,
        description="Optional target Workspace ID or Slug to join",
    )
    join_code: str | None = Field(
        default=None,
        description="Optional Join Code (VR-XXXXXX) for protected workspace join",
    )
    invitation_token: str | None = Field(
        default=None,
        max_length=128,
        description="Optional Invitation Token (sec_inv_*)",
    )
    workspace_name: str | None = Field(
        default=None,
        max_length=100,
        description="Optional name when creating a new workspace",
    )
    company_name: str | None = Field(
        default=None,
        max_length=100,
        description="Optional company name for legacy/organizational context",
    )

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

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip()
        # Reject raw UUID to prevent using internal tenant UUID as public join credential
        if re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", clean):
            raise ValueError("Tenant UUID cannot be used as a public join credential. Use Workspace ID or Slug.")
        return clean

    @field_validator("join_code")
    @classmethod
    def normalize_and_validate_join_code(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip().upper()
        if not re.match(r"^VR-[23456789ABCDEFGHJKMNPQRSTVWXYZ]{6}$", clean):
            raise ValueError("Invalid Join Code format. Expected 'VR-XXXXXX' using Crockford alphanumeric characters.")
        return clean

class RegistrationResponse(BaseModel):
    """Schema for successful registration response."""
    message: str = "Registration successful. Please check your email to verify your account."
