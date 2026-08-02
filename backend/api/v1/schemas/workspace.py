import uuid

from pydantic import BaseModel, Field


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name of the workspace")
    description: str | None = Field(None, max_length=1024, description="Optional description of the workspace")


from datetime import datetime


class UpdateWorkspaceRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100, description="Name of the workspace")
    description: str | None = Field(None, max_length=1024, description="Optional description of the workspace")
    expected_updated_at: datetime = Field(..., description="Timestamp for optimistic concurrency")


from pydantic import validator


class ArchiveWorkspaceRequest(BaseModel):
    expected_updated_at: datetime = Field(..., description="Timestamp for optimistic concurrency")
    confirmation_name: str = Field(..., description="Workspace name confirmation")
    reason: str | None = Field(None, max_length=500, description="Optional reason for archiving")

    @validator("reason")
    def validate_reason(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Reason cannot be empty whitespace")
        return v


class RestoreWorkspaceRequest(BaseModel):
    expected_updated_at: datetime = Field(..., description="Timestamp for optimistic concurrency")


import enum


class SuspensionReasonCode(str, enum.Enum):
    BILLING = "BILLING"
    SECURITY = "SECURITY"
    ABUSE = "ABUSE"
    LEGAL = "LEGAL"
    COMPLIANCE = "COMPLIANCE"
    MANUAL = "MANUAL"
    OTHER = "OTHER"


class SuspendWorkspaceRequest(BaseModel):
    expected_updated_at: datetime = Field(..., description="Timestamp for optimistic concurrency")
    confirmation_name: str = Field(..., description="Workspace name confirmation")
    reason_code: SuspensionReasonCode = Field(..., description="Standardized suspension reason code")
    reason_text: str | None = Field(None, max_length=500, description="Detailed explanation or justification")

    @validator("reason_text")
    def validate_reason_text(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("reason_text cannot be empty whitespace")
        return v


class UnsuspendWorkspaceRequest(BaseModel):
    expected_updated_at: datetime = Field(..., description="Timestamp for optimistic concurrency")
    reason_text: str | None = Field(None, max_length=500, description="Optional reason for unsuspension")

    @validator("reason_text")
    def validate_reason_text(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("reason_text cannot be empty whitespace")
        return v


class DeletionReasonCode(str, enum.Enum):
    USER_REQUESTED = "USER_REQUESTED"
    PROJECT_COMPLETED = "PROJECT_COMPLETED"
    MIGRATION = "MIGRATION"
    BILLING_DEFAULT = "BILLING_DEFAULT"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    OTHER = "OTHER"


class SoftDeleteWorkspaceRequest(BaseModel):
    expected_updated_at: datetime = Field(..., description="Timestamp for optimistic concurrency")
    confirmation_name: str = Field(..., description="Workspace name confirmation")
    reason_code: DeletionReasonCode = Field(..., description="Standardized deletion reason code")
    reason_text: str | None = Field(None, max_length=500, description="Detailed explanation")

    @validator("reason_text")
    def validate_reason_text(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("reason_text cannot be empty whitespace")
        return v


class RestoreDeletedWorkspaceRequest(BaseModel):
    expected_updated_at: datetime = Field(..., description="Timestamp for optimistic concurrency")


class HardDeleteWorkspaceRequest(BaseModel):
    confirmation_slug: str = Field(..., description="Workspace slug confirmation for permanent purge")
    force_immediate: bool = Field(False, description="Flag to force immediate purge without waiting for retention")
    reason: str = Field(..., min_length=3, max_length=500, description="Reason for hard deletion")


class WorkspaceDataResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    status: str
    provisioning_status: str
    updated_at: datetime
    suspended_at: datetime | None = None
    deleted_at: datetime | None = None
    purge_at: datetime | None = None
    deleted_by_user_id: uuid.UUID | None = None
    deletion_reason_code: str | None = None
    deletion_reason_text: str | None = None


class WorkspaceResponse(BaseModel):
    success: bool
    data: WorkspaceDataResponse


