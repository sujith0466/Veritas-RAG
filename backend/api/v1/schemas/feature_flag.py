"""Feature Flag API schemas for validation and serialization."""

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, Field

from backend.models.entities.feature_flag import (
    FlagCategory,
    FlagLifecycleState,
    FlagType,
)


# ── Request Schemas ──────────────────────────────────────────────────────────

class FeatureFlagCreateRequest(BaseModel):
    key: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9_.-]+$", description="Unique flag key")
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    category: FlagCategory = Field(default=FlagCategory.BETA)
    lifecycle_state: FlagLifecycleState = Field(default=FlagLifecycleState.DRAFT)
    flag_type: FlagType = Field(default=FlagType.BOOLEAN)
    default_enabled: bool = Field(default=False)
    prerequisite_flag_keys: list[str] = Field(default_factory=list)
    default_variant: dict[str, Any] = Field(default_factory=dict)
    target_environments: str = Field(default="production,staging,development")
    change_reason: str = Field(default="Created new feature flag", max_length=255)


class FeatureFlagUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    category: FlagCategory | None = None
    lifecycle_state: FlagLifecycleState | None = None
    default_enabled: bool | None = None
    prerequisite_flag_keys: list[str] | None = None
    default_variant: dict[str, Any] | None = None
    target_environments: str | None = None
    change_reason: str = Field(default="Updated feature flag", max_length=255)


class FeatureFlagKillswitchRequest(BaseModel):
    is_active: bool = Field(..., description="True to engage killswitch (disable flag immediately), False to disengage")
    reason: str = Field(..., min_length=3, max_length=255, description="Reason for emergency killswitch activation")


class FeatureFlagWorkspaceRuleRequest(BaseModel):
    is_enabled: bool = Field(default=True)
    rollout_percentage: int = Field(default=100, ge=0, le=100)
    activation_start_at: datetime | None = None
    activation_end_at: datetime | None = None
    targeting_conditions: list[dict[str, Any]] = Field(default_factory=list)
    custom_variant: dict[str, Any] = Field(default_factory=dict)
    change_reason: str = Field(default="Configured workspace rule", max_length=255)


# ── Response Schemas ─────────────────────────────────────────────────────────

class FeatureFlagDataResponse(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: str | None = None
    category: str
    lifecycle_state: str
    flag_type: str
    default_enabled: bool
    is_killswitch_active: bool
    prerequisite_flag_keys: list[str]
    default_variant: dict[str, Any]
    target_environments: list[str]
    version: int
    created_at: datetime
    updated_at: datetime


class FeatureFlagResponse(BaseModel):
    success: bool
    data: FeatureFlagDataResponse


class FeatureFlagListResponse(BaseModel):
    success: bool
    data: list[FeatureFlagDataResponse]


class FeatureFlagWorkspaceRuleDataResponse(BaseModel):
    id: uuid.UUID
    flag_id: uuid.UUID
    workspace_id: uuid.UUID
    is_enabled: bool
    rollout_percentage: int
    activation_start_at: datetime | None = None
    activation_end_at: datetime | None = None
    targeting_conditions: list[dict[str, Any]]
    custom_variant: dict[str, Any]
    version: int
    created_at: datetime
    updated_at: datetime


class FeatureFlagWorkspaceRuleResponse(BaseModel):
    success: bool
    data: FeatureFlagWorkspaceRuleDataResponse


class FeatureFlagEvaluationDataResponse(BaseModel):
    flag_key: str
    is_enabled: bool
    variant: dict[str, Any]
    reason: str
    tier_served: str
    evaluated_at: datetime


class FeatureFlagEvaluationResponse(BaseModel):
    success: bool
    data: FeatureFlagEvaluationDataResponse


class FeatureFlagBulkEvaluationResponse(BaseModel):
    success: bool
    workspace_id: uuid.UUID
    flags: dict[str, FeatureFlagEvaluationDataResponse]


class FeatureFlagHistoryDataResponse(BaseModel):
    id: uuid.UUID
    flag_id: uuid.UUID
    workspace_id: uuid.UUID | None = None
    changed_by_user_id: uuid.UUID | None = None
    version: int
    change_action: str
    change_reason: str | None = None
    old_rule: dict[str, Any] | None = None
    new_rule: dict[str, Any]
    created_at: datetime


class FeatureFlagHistoryResponse(BaseModel):
    success: bool
    data: list[FeatureFlagHistoryDataResponse]
