"""User Profile Service.

Handles user profile updates, optimistic locking, and event emission (F4.7).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError
import structlog

from backend.api.v1.schemas.users import UserProfileUpdate
from backend.core.events.dispatcher import EventDispatcher
from backend.core.exceptions.base import ApplicationException
from backend.models.entities.user import User
from backend.repositories.implementations.user_repository import UserRepository
from backend.services.user.events import UserProfileUpdatedEvent

logger = structlog.get_logger(__name__)


class ProfileUpdateConflictError(ApplicationException):
    error_code = "USER_001"
    default_message = "Profile update conflict due to concurrent modification."


class UsernameTakenError(ApplicationException):
    error_code = "USER_002"
    default_message = "Username is already taken."


class UserProfileService:
    """Service for managing user profiles."""

    def __init__(
        self,
        session: AsyncSession,
        event_dispatcher: EventDispatcher,
    ) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.event_dispatcher = event_dispatcher

    async def get_profile(self, user_id: uuid.UUID) -> User:
        """Fetch the user's profile."""
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active or user.is_deleted:
            raise ApplicationException("User not found", error_code="USER_404")
        return user

    async def update_profile(
        self,
        user_id: uuid.UUID,
        update_data: UserProfileUpdate,
        expected_version: int,
    ) -> User:
        """Update user profile with optimistic locking."""
        user = await self.get_profile(user_id)

        if user.version != expected_version:
            raise ProfileUpdateConflictError()

        # Check username uniqueness if changing
        if update_data.username and update_data.username != user.username:
            if await self.user_repo.exists_by_username(update_data.username):
                raise UsernameTakenError()

        changed_fields = []

        # Base fields
        base_fields = ["username", "display_name", "timezone", "language", "theme_preference"]
        update_dict = update_data.model_dump(exclude_unset=True)

        for key in base_fields:
            if key in update_dict:
                val = update_dict[key]
                if getattr(user, key) != val:
                    setattr(user, key, val)
                    changed_fields.append(key)

        # Nested profile_data
        if update_data.profile_data is not None:
            current_data = user.profile_data or {}
            new_data = update_data.profile_data.model_dump(exclude_unset=True)
            if new_data:
                for k, v in new_data.items():
                    if current_data.get(k) != v:
                        current_data[k] = v
                        if "profile_data" not in changed_fields:
                            changed_fields.append("profile_data")
                if "profile_data" in changed_fields:
                    user.profile_data = current_data

        if not changed_fields:
            return user

        user.version += 1

        try:
            await self.session.commit()
            await self.session.refresh(user)
        except StaleDataError as e:
            await self.session.rollback()
            raise ProfileUpdateConflictError() from e

        await self.event_dispatcher.publish(
            UserProfileUpdatedEvent(
                user_id=str(user.id),
                changed_fields=changed_fields
            )
        )

        logger.info(
            "User profile updated",
            user_id=str(user.id),
            changed_fields=changed_fields
        )

        return user
