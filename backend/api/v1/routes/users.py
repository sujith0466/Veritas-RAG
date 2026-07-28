from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.dependencies.database import get_db
from backend.core.dependencies.auth import get_current_user
from backend.core.auth.context import UserContext
from backend.models.entities.user import User
from backend.api.v1.schemas.users import (
    UserResponse,
    UserProfileUpdate,
    UserPreferencesUpdate,
    UserWorkspaceUpdate,
)
from backend.core.dependencies.storage import get_current_storage_provider
from backend.modules.storage.services.provider import StorageProvider

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current authenticated user's full profile and settings."""
    stmt = select(User).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Ensure ID is string for response schema
    user_dict = {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "is_active": user.is_active,
        "profile_data": user.profile_data or {},
        "preferences": user.preferences or {},
        "workspace_settings": user.workspace_settings or {},
    }
    return user_dict


@router.patch("/me/profile", response_model=UserResponse)
async def update_my_profile(
    update_data: UserProfileUpdate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user profile information."""
    stmt = select(User).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if update_data.username is not None:
        user.username = update_data.username
    if update_data.profile_data is not None:
        # Merge dicts
        current_data = user.profile_data or {}
        current_data.update(update_data.profile_data.model_dump(exclude_unset=True))
        user.profile_data = current_data

    await db.commit()
    await db.refresh(user)

    user_dict = {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "is_active": user.is_active,
        "profile_data": user.profile_data or {},
        "preferences": user.preferences or {},
        "workspace_settings": user.workspace_settings or {},
    }
    return user_dict


@router.patch("/me/preferences", response_model=UserResponse)
async def update_my_preferences(
    update_data: UserPreferencesUpdate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user preferences (UI, AI, Notifications)."""
    stmt = select(User).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    current_prefs = user.preferences or {}
    current_prefs.update(update_data.preferences.model_dump(exclude_unset=True))
    user.preferences = current_prefs

    await db.commit()
    await db.refresh(user)

    user_dict = {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "is_active": user.is_active,
        "profile_data": user.profile_data or {},
        "preferences": user.preferences or {},
        "workspace_settings": user.workspace_settings or {},
    }
    return user_dict


@router.patch("/me/workspace", response_model=UserResponse)
async def update_my_workspace(
    update_data: UserWorkspaceUpdate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update workspace settings."""
    stmt = select(User).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    current_ws = user.workspace_settings or {}
    current_ws.update(update_data.workspace_settings.model_dump(exclude_unset=True))
    user.workspace_settings = current_ws

    await db.commit()
    await db.refresh(user)

    user_dict = {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "is_active": user.is_active,
        "profile_data": user.profile_data or {},
        "preferences": user.preferences or {},
        "workspace_settings": user.workspace_settings or {},
    }
    return user_dict


@router.post("/me/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageProvider = Depends(get_current_storage_provider),
):
    """Upload user avatar and update profile."""
    stmt = select(User).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if file.content_type not in ["image/jpeg", "image/png", "image/gif", "image/webp"]:
        raise HTTPException(status_code=400, detail="Invalid image format")

    max_size = 5 * 1024 * 1024
    content = await file.read(max_size + 1)
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail="File too large (max 5MB)")
    await file.seek(0)

    # If user already has an avatar, delete it
    if user.avatar_url and user.avatar_url.startswith("/api/v1/storage"):
        await storage.delete_file(user.avatar_url)

    # Upload new file
    url = await storage.upload_file(file.file, file.filename, file.content_type)
    user.avatar_url = url

    await db.commit()
    await db.refresh(user)

    user_dict = {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "is_active": user.is_active,
        "profile_data": user.profile_data or {},
        "preferences": user.preferences or {},
        "workspace_settings": user.workspace_settings or {},
    }
    return user_dict
