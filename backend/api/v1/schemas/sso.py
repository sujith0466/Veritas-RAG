"""SSO Config schemas."""

from datetime import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class IdentityProviderCreateRequest(BaseModel):
    """Schema for creating an IdP."""
    name: str = Field(..., max_length=100, json_schema_extra={"example": "Corporate Okta"})
    type: str = Field(..., json_schema_extra={"example": "SAML"})
    entity_id_issuer: str = Field(..., json_schema_extra={"example": "http://www.okta.com/exk12345"})
    sso_url: str = Field(..., json_schema_extra={"example": "https://org.okta.com/app/app/sso/saml"})
    logout_url: str | None = Field(None, json_schema_extra={"example": "https://org.okta.com/app/app/sso/logout"})
    metadata_url: str | None = Field(None, json_schema_extra={"example": "https://org.okta.com/app/app/sso/saml/metadata"})
    certificates: dict | list | None = Field(None, description="Certificates or JWKS keys")
    attribute_mapping: dict[str, str] = Field(..., json_schema_extra={"example": {"email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"}})
    domain_restrictions: list[str] | None = Field(None, json_schema_extra={"example": ["acme.com"]})
    jit_enabled: bool = Field(False)
    force_sso: bool = Field(False)

class IdentityProviderUpdateRequest(BaseModel):
    """Schema for updating an IdP."""
    name: str | None = None
    is_active: bool | None = None
    entity_id_issuer: str | None = None
    sso_url: str | None = None
    logout_url: str | None = None
    metadata_url: str | None = None
    certificates: dict | list | None = None
    attribute_mapping: dict[str, str] | None = None
    domain_restrictions: list[str] | None = None
    jit_enabled: bool | None = None
    force_sso: bool | None = None

class IdentityProviderResponse(BaseModel):
    """Schema for IdP response."""
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    type: str
    is_active: bool
    entity_id_issuer: str
    sso_url: str
    logout_url: str | None
    metadata_url: str | None
    certificates: dict | list | None
    attribute_mapping: dict[str, str]
    domain_restrictions: list[str] | None
    jit_enabled: bool
    force_sso: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
