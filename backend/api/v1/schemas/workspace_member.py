"""Workspace Member API Schemas."""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.entities.workspace_member import WorkspaceRole


class UpdateMemberRoleRequest(BaseModel):
    """Payload for modifying a member's role."""

    role: str = Field(..., description="Target workspace role (e.g. 'OWNER', 'ADMIN', 'MEMBER', 'VIEWER')")
    dry_run: bool = Field(default=False, description="If true, validates role change without persisting")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        role_upper = v.strip().upper()
        allowed = {r.value for r in WorkspaceRole}
        if role_upper not in allowed:
            raise ValueError(f"Invalid workspace role '{v}'. Allowed roles: {allowed}")
        return role_upper


class BulkMemberActionRequest(BaseModel):
    """Payload for executing a batch action across multiple members."""

    action: str = Field(..., description="Bulk action: 'suspend', 'restore', 'remove', 'update_role'")
    member_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100, description="List of member UUIDs")
    role: str | None = Field(default=None, description="Target role when action is 'update_role'")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        act_lower = v.strip().lower()
        allowed = {"suspend", "restore", "remove", "update_role"}
        if act_lower not in allowed:
            raise ValueError(f"Invalid action '{v}'. Allowed actions: {allowed}")
        return act_lower


class WorkspaceMemberUserData(BaseModel):
    """Sanitized User details embedded in member response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str | None = None
    is_active: bool = True


class WorkspaceMemberData(BaseModel):
    """Sanitized DTO for workspace member entity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    status: str
    invited_by_user_id: uuid.UUID | None = None
    joined_at: datetime.datetime | None = None
    last_active_at: datetime.datetime | None = None
    version: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    user: WorkspaceMemberUserData | None = None


class WorkspaceMemberResponse(BaseModel):
    """Response payload for a single workspace member operation."""

    success: bool = True
    message: str = "Workspace member operation completed successfully."
    data: WorkspaceMemberData


class WorkspaceMemberListResponse(BaseModel):
    """Response payload for paginated workspace member list."""

    success: bool = True
    total: int
    page: int
    page_size: int
    next_cursor: str | None = None
    items: list[WorkspaceMemberData]


class BulkMemberActionResult(BaseModel):
    """Individual member result in bulk operation."""

    member_id: str
    status: str
    message: str | None = None


class BulkMemberActionResponse(BaseModel):
    """Response payload for bulk member operation."""

    success: bool = True
    message: str = "Bulk member operation processed."
    total: int
    results: list[BulkMemberActionResult]
