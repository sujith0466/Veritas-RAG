"""Domain Verification schemas."""

from datetime import datetime
import uuid

from pydantic import BaseModel, Field


class DomainCreateRequest(BaseModel):
    """Schema for adding a domain to a workspace."""
    domain_name: str = Field(..., description="The domain to verify", example="acme.com")

class DomainResponse(BaseModel):
    """Schema for representing a workspace domain."""
    id: uuid.UUID
    workspace_id: uuid.UUID
    domain_name: str
    status: str
    is_primary: bool
    last_verified_at: datetime | None
    token_expires_at: datetime
    dns_last_checked_at: datetime | None
    error_reason: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DomainCreateResponse(DomainResponse):
    """Schema for the response when creating a domain, includes the token once."""
    verification_token: str = Field(..., description="The cryptographically secure token to place in TXT record. Shown only once.")

class DomainSetPrimaryRequest(BaseModel):
    """Request for setting a domain as primary."""
    pass
