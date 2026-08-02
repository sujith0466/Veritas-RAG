"""User Profile API Schemas."""


from pydantic import BaseModel, ConfigDict, Field


class UserProfileData(BaseModel):
    """Sanitized User profile data."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    timezone: str
    language: str
    theme_preference: str
    version: int


class UserProfileResponse(BaseModel):
    """Response payload for user profile fetch/update."""
    success: bool = True
    message: str = "Success"
    data: UserProfileData


class UpdateProfileRequest(BaseModel):
    """Payload for updating user profile."""
    username: str | None = Field(None, pattern=r"^[a-zA-Z0-9_-]{3,30}$", description="Alphanumeric, hyphens, underscores, 3-30 chars")
    display_name: str | None = Field(None, max_length=100)
    timezone: str | None = Field(None, max_length=50)
    language: str | None = Field(None, max_length=20)
    theme_preference: str | None = Field(None, max_length=20)

class AvatarUploadUrlResponse(BaseModel):
    """Response payload for avatar upload URL."""
    success: bool = True
    upload_url: str
    file_key: str
