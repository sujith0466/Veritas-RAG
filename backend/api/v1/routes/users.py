from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.users import (
    UserPreferencesUpdate,
    UserProfileUpdate,
    UserResponse,
    UserWorkspaceUpdate,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.dependencies.storage import get_current_storage_provider
from backend.core.dependencies.user import get_user_profile_service
from backend.document.storage.base import StorageProvider
from backend.models.entities.user import User
from backend.services.user.profile_service import (
    ProfileUpdateConflictError,
    UsernameTakenError,
    UserProfileService,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: UserContext = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_user_profile_service),
):
    """Get the current authenticated user's full profile and settings."""
    user = await profile_service.get_profile(current_user.user_id)
    return user


@router.patch("/me/profile", response_model=UserResponse)
async def update_my_profile(
    update_data: UserProfileUpdate,
    if_match: int | None = Header(None, alias="If-Match", description="Expected current version of the profile for optimistic locking"),
    current_user: UserContext = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_user_profile_service),
):
    """Update user profile information."""
    try:
        if if_match is None:
            # Backward compatibility: skip optimistic locking check if header not provided
            current = await profile_service.get_profile(current_user.user_id)
            if_match = current.version

        updated_user = await profile_service.update_profile(
            user_id=current_user.user_id,
            update_data=update_data,
            expected_version=if_match,
        )
        return updated_user
    except ProfileUpdateConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except UsernameTakenError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))



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
    if user.avatar_url and "/avatars/" in user.avatar_url:
        try:
            # Extract object key (e.g. avatars/123/img.jpg) from URL
            parts = user.avatar_url.split("/avatars/")
            if len(parts) == 2:
                old_key = "avatars/" + parts[1]
                await storage.delete_object(old_key)
        except Exception:
            pass

    # Upload new file
    import uuid
    ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    object_key = f"avatars/{current_user.id}/{uuid.uuid4().hex}.{ext}"
    await storage.save_stream(file.file, object_key)

    url = await storage.get_uri(object_key)
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
