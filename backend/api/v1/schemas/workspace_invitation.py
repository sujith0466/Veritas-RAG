"""Workspace Invitation API Schemas."""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SendInvitationRequest(BaseModel):
    """Payload for creating and sending a workspace invitation."""

    email: EmailStr = Field(..., description="Target recipient email address to invite")
    role: str = Field(
        default="MEMBER",
        description="Target workspace role ('ADMIN', 'MEMBER', 'VIEWER')",
    )
    custom_message: str | None = Field(
        default=None,
        max_length=500,
        description="Optional custom invitation message included in email",
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"ADMIN", "MEMBER", "VIEWER"}
        role_upper = v.strip().upper()
        if role_upper not in allowed:
            raise ValueError(f"Invalid role '{v}'. Allowed roles: {allowed}")
        return role_upper


class ResendInvitationRequest(BaseModel):
    """Payload for resending a workspace invitation."""

    custom_message: str | None = Field(
        default=None,
        max_length=500,
        description="Optional custom invitation message included in email",
    )


class WorkspaceInvitationData(BaseModel):
    """Sanitized public DTO for workspace invitation (never exposes raw token or hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    email: str
    role: str
    status: str
    invited_by_user_id: uuid.UUID | None = None
    expires_at: datetime.datetime
    accepted_at: datetime.datetime | None = None
    revoked_at: datetime.datetime | None = None
    resend_count: int
    last_resent_at: datetime.datetime | None = None
    version: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class WorkspaceInvitationResponse(BaseModel):
    """Response payload for a single workspace invitation operation."""

    success: bool = True
    message: str = "Workspace invitation processed successfully."
    data: WorkspaceInvitationData


class WorkspaceInvitationListResponse(BaseModel):
    """Response payload for paginated workspace invitations."""

    success: bool = True
    total: int
    page: int
    page_size: int
    items: list[WorkspaceInvitationData]


class VerifyInvitationData(BaseModel):
    """Metadata returned when invitee checks magic link validity."""

    invitation_id: uuid.UUID
    workspace_id: uuid.UUID
    workspace_name: str
    email: str
    role: str
    inviter_email: str | None = None
    expires_at: datetime.datetime
    status: str


class VerifyInvitationResponse(BaseModel):
    """Response payload for invitation verification."""

    success: bool = True
    message: str = "Invitation token verified successfully."
    data: VerifyInvitationData


class AcceptInvitationRequest(BaseModel):
    """Payload for accepting a workspace invitation."""

    token: str = Field(..., description="Raw cryptographic invitation token from magic link")


class AcceptInvitationData(BaseModel):
    """Data returned after accepting an invitation."""

    workspace_id: uuid.UUID
    workspace_name: str
    role: str
    member_id: uuid.UUID


class AcceptInvitationResponse(BaseModel):
    """Response payload for invitation acceptance."""

    success: bool = True
    message: str = "Workspace invitation accepted successfully."
    data: AcceptInvitationData
