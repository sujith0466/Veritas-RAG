"""Workspace Join Code API Schemas."""

import datetime
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class CreateJoinCodeRequest(BaseModel):
    """Payload for creating or rotating a workspace join code."""

    expires_in_days: int | None = Field(
        default=None,
        ge=1,
        le=30,
        description="Expiration TTL in days (defaults to 7 days, clamped to 1-30 days)",
    )


class WorkspaceJoinCodeData(BaseModel):
    """Sanitized public DTO for workspace join code entity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    created_by_user_id: uuid.UUID | None = None
    operational_custodian_user_id: uuid.UUID | None = None
    expires_at: datetime.datetime
    is_active: bool
    code_display: str | None = None
    use_count: int = 0
    created_at: datetime.datetime
    updated_at: datetime.datetime


class WorkspaceJoinCodeResponse(BaseModel):
    """Response payload for join code lifecycle operations."""

    success: bool = True
    message: str = "Workspace join code processed successfully."
    data: WorkspaceJoinCodeData
    join_code: str | None = Field(
        default=None,
        description="Plaintext join code (revealed on creation/rotation or to creator).",
    )


class ClaimCustodianRequest(BaseModel):
    """Payload for claiming operational custodianship over an unmapped legacy join code."""

    notes: str | None = Field(
        default=None,
        max_length=500,
        description="Optional justification or audit notes for claiming custodianship.",
    )


class WorkspaceJoinCodeRedemptionData(BaseModel):
    """Sanitized DTO for join code redemption log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    join_code_id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    redeemed_at: datetime.datetime
    ip_address: str | None = None
    user_agent: str | None = None


class WorkspaceJoinCodeActivityResponse(BaseModel):
    """Response payload for join code redemption activity log."""

    success: bool = True
    total: int
    items: list[WorkspaceJoinCodeRedemptionData]


class MemberAccessStatusEnum(str, Enum):
    """Authoritative credential access status for member dashboard."""

    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    CREATOR_INELIGIBLE = "CREATOR_INELIGIBLE"
    NO_ATTRIBUTION = "NO_ATTRIBUTION"
    NO_CODE_CONFIGURED = "NO_CODE_CONFIGURED"
    ADMIN_MANAGEMENT_REQUIRED = "ADMIN_MANAGEMENT_REQUIRED"
    ATTRIBUTION_CONFLICT = "ATTRIBUTION_CONFLICT"
    VIEWER_RESTRICTED = "VIEWER_RESTRICTED"
    ROLE_NOT_AUTHORIZED = "ROLE_NOT_AUTHORIZED"


class MemberJoinAccessResponse(BaseModel):
    """Response schema for member-facing join code access endpoint."""

    success: bool = Field(..., description="Indicates whether the request completed successfully.")
    status: MemberAccessStatusEnum = Field(..., description="Authoritative credential access status.")
    workspace_id: uuid.UUID = Field(..., description="Target workspace unique identifier.")
    workspace_name: str = Field(..., description="Workspace display name.")
    public_id: Optional[str] = Field(None, description="Workspace public identifier or slug.")
    creator_name: Optional[str] = Field(None, description="Display name of originating administrator (None on conflict or unattributed).")
    join_code: Optional[str] = Field(None, description="Plaintext Crockford join code (disclosed ONLY to MEMBER when status is ACTIVE).")
    join_link: Optional[str] = Field(None, description="Full canonical join link (disclosed ONLY to MEMBER when status is ACTIVE).")
    code_display: Optional[str] = Field(None, description="Masked code preview (e.g. V-RAG-•••••• disclosed to OWNER/ADMIN).")
    expires_at: Optional[datetime.datetime] = Field(None, description="Expiration timestamp if code exists; None otherwise.")
    message: str = Field(..., description="User-facing status explanation or guidance message.")

