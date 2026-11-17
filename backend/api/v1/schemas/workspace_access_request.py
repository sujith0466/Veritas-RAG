"""Pydantic schemas for Workspace Access Requests."""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateAccessRequest(BaseModel):
    """Payload for submitting an access request."""

    request_type: str = Field(default="ROLE_ELEVATION", description="ROLE_ELEVATION or JOIN_APPROVAL")
    requested_role: str = Field(default="MEMBER", description="Requested role (MEMBER)")
    reason: str | None = Field(default=None, description="Optional applicant rationale")

    @field_validator("requested_role")
    @classmethod
    def validate_requested_role(cls, v: str) -> str:
        cleaned = (v or "").strip().upper()
        if cleaned != "MEMBER":
            raise ValueError(f"Invalid requested role '{v}'. Only 'MEMBER' access requests are permitted.")
        return cleaned


class RejectAccessRequest(BaseModel):
    """Payload for rejecting an access request."""

    rejection_reason: str | None = Field(default=None, description="Reason for rejection")


class AccessRequestData(BaseModel):
    """Access request representation."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    request_type: str
    current_role: str | None = None
    requested_role: str
    status: str
    reason: str | None = None
    reviewed_by_id: uuid.UUID | None = None
    reviewed_at: datetime.datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime.datetime
    user_email: str | None = None
    user_display_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AccessRequestResponse(BaseModel):
    """Response containing a single access request."""

    success: bool = True
    request: AccessRequestData


class AccessRequestListResponse(BaseModel):
    """Paginated response containing access requests."""

    items: list[AccessRequestData]
    total: int
    skip: int
    limit: int
