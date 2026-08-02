"""Verification schemas."""

from pydantic import BaseModel, EmailStr

class ResendVerificationRequest(BaseModel):
    """Schema for requesting a new verification email."""
    email: EmailStr
