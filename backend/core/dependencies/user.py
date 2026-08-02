"""User dependencies for FastAPI."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.database import get_db
from backend.core.events import EventDispatcher, get_dispatcher
from backend.services.user.profile_service import UserProfileService


def get_user_profile_service(
    session: AsyncSession = Depends(get_db),
    dispatcher: EventDispatcher = Depends(get_dispatcher),
) -> UserProfileService:
    """Return an instance of UserProfileService."""
    return UserProfileService(session, dispatcher)
