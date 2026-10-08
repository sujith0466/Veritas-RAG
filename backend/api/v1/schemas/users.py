from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


import re
from urllib.parse import urlparse

class ProfileDataSchema(BaseModel):
    bio: str | None = Field(default=None, max_length=1000)
    organization: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    department: str | None = Field(default=None, max_length=255)
    designation: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    workspace_name: str | None = Field(default=None, max_length=255)

    model_config = {"extra": "ignore"}

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        parsed = urlparse(v)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
            raise ValueError("Website must be a valid HTTP or HTTPS URL")
        return v


class AISettingsSchema(BaseModel):
    default_model: str | None = Field(default=None, max_length=100)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    system_prompt: str | None = Field(default=None, max_length=10000)

    model_config = {"extra": "ignore"}


class UserPreferencesSchema(BaseModel):
    ai: AISettingsSchema | None = None

    model_config = {"extra": "ignore"}


class WorkspaceSettingsSchema(BaseModel):
    retention_policy: str | None = Field(default=None, max_length=50)
    data_region: str | None = Field(default=None, max_length=50)
    onboarding_completed: bool | None = Field(default=None)

    model_config = {"extra": "ignore"}


class UserProfileUpdate(BaseModel):
    username: str | None = Field(default=None, max_length=30)
    display_name: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, max_length=50)
    language: str | None = Field(default=None, max_length=20)
    theme_preference: str | None = Field(default=None, max_length=20)
    version: int | None = Field(default=None, description="Expected version for optimistic locking")

    profile_data: ProfileDataSchema | None = None

    model_config = {"extra": "ignore"}

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not re.match(r"^[a-zA-Z0-9_-]{3,30}$", v):
            raise ValueError("Username must be between 3 and 30 characters and contain only letters, numbers, underscores, or hyphens")
        return v


class UserPreferencesUpdate(BaseModel):
    preferences: UserPreferencesSchema

    model_config = {"extra": "ignore"}


class UserWorkspaceUpdate(BaseModel):
    workspace_settings: WorkspaceSettingsSchema

    model_config = {"extra": "ignore"}


import uuid

class UserResponse(BaseModel):
    id: uuid.UUID | str
    email: str
    username: str | None
    display_name: str | None = None
    avatar_url: str | None
    role: str
    is_active: bool

    # F4.7 fields
    timezone: str = "UTC"
    language: str = "en-US"
    theme_preference: str = "system"
    version: int = 1

    profile_data: dict[str, Any] | None
    preferences: dict[str, Any] | None
    workspace_settings: dict[str, Any] | None

    model_config = ConfigDict(from_attributes=True)
