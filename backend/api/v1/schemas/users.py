from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ProfileDataSchema(BaseModel):
    bio: Optional[str] = Field(default=None, max_length=1000)
    organization: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    department: Optional[str] = Field(default=None, max_length=255)
    designation: Optional[str] = Field(default=None, max_length=255)
    website: Optional[str] = Field(default=None, max_length=255)
    timezone: Optional[str] = Field(default=None, max_length=100)
    location: Optional[str] = Field(default=None, max_length=255)
    workspace_name: Optional[str] = Field(default=None, max_length=255)

    model_config = {"extra": "forbid"}


class AISettingsSchema(BaseModel):
    default_model: Optional[str] = Field(default=None, max_length=100)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    system_prompt: Optional[str] = Field(default=None, max_length=10000)

    model_config = {"extra": "forbid"}


class UserPreferencesSchema(BaseModel):
    ai: Optional[AISettingsSchema] = None

    model_config = {"extra": "forbid"}


class WorkspaceSettingsSchema(BaseModel):
    retention_policy: Optional[str] = Field(default=None, max_length=50)
    data_region: Optional[str] = Field(default=None, max_length=50)

    model_config = {"extra": "forbid"}


class UserProfileUpdate(BaseModel):
    username: Optional[str] = Field(default=None, max_length=150)
    profile_data: Optional[ProfileDataSchema] = None

    model_config = {"extra": "forbid"}


class UserPreferencesUpdate(BaseModel):
    preferences: UserPreferencesSchema

    model_config = {"extra": "forbid"}


class UserWorkspaceUpdate(BaseModel):
    workspace_settings: WorkspaceSettingsSchema

    model_config = {"extra": "forbid"}


class UserResponse(BaseModel):
    id: str
    email: str
    username: Optional[str]
    avatar_url: Optional[str]
    role: str
    is_active: bool
    profile_data: Optional[Dict[str, Any]]
    preferences: Optional[Dict[str, Any]]
    workspace_settings: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True
