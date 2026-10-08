import uuid
import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock

from backend.api.v1.schemas.users import ProfileDataSchema, UserProfileUpdate
from backend.services.user.profile_service import (
    ProfileUpdateConflictError,
    UsernameTakenError,
    UserProfileService,
)
from backend.models.entities.user import User


class TestUserProfileValidation:
    """Tests for ProfileDataSchema and UserProfileUpdate validation."""

    def test_website_valid_schemes(self):
        # Valid http / https
        schema1 = ProfileDataSchema(website="https://veritas-rag.example.com")
        assert schema1.website == "https://veritas-rag.example.com"

        schema2 = ProfileDataSchema(website="http://localhost:8000")
        assert schema2.website == "http://localhost:8000"

        # None or empty
        schema3 = ProfileDataSchema(website=None)
        assert schema3.website is None

        schema4 = ProfileDataSchema(website="")
        assert schema4.website is None

    def test_website_invalid_schemes_rejected(self):
        with pytest.raises(ValidationError) as exc:
            ProfileDataSchema(website="javascript:alert(1)")
        assert "Website must be a valid HTTP or HTTPS URL" in str(exc.value)

        with pytest.raises(ValidationError) as exc:
            ProfileDataSchema(website="data:text/html,<script>alert(1)</script>")
        assert "Website must be a valid HTTP or HTTPS URL" in str(exc.value)

        with pytest.raises(ValidationError) as exc:
            ProfileDataSchema(website="ftp://files.example.com")
        assert "Website must be a valid HTTP or HTTPS URL" in str(exc.value)

    def test_username_validation(self):
        # Valid usernames (3-30 alphanumeric, underscore, hyphen)
        up1 = UserProfileUpdate(username="john_doe")
        assert up1.username == "john_doe"

        up2 = UserProfileUpdate(username="alice-123")
        assert up2.username == "alice-123"

        up3 = UserProfileUpdate(username=None)
        assert up3.username is None

        # Too short (< 3)
        with pytest.raises(ValidationError) as exc:
            UserProfileUpdate(username="ab")
        assert "Username must be between 3 and 30 characters" in str(exc.value)

        # Invalid characters
        with pytest.raises(ValidationError) as exc:
            UserProfileUpdate(username="john doe")
        assert "Username must be between 3 and 30 characters" in str(exc.value)

        with pytest.raises(ValidationError) as exc:
            UserProfileUpdate(username="user@name!")
        assert "Username must be between 3 and 30 characters" in str(exc.value)


@pytest.mark.asyncio
class TestUserProfileServiceLogic:
    """Tests for UserProfileService optimistic locking and updates."""

    async def test_optimistic_locking_conflict(self):
        user_id = uuid.uuid4()
        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.is_active = True
        mock_user.is_deleted = False
        mock_user.version = 2

        mock_session = AsyncMock()
        mock_dispatcher = MagicMock()

        service = UserProfileService(session=mock_session, event_dispatcher=mock_dispatcher)
        service.get_profile = AsyncMock(return_value=mock_user)

        # Expect version 1 when current version is 2 -> Conflict
        with pytest.raises(ProfileUpdateConflictError):
            await service.update_profile(
                user_id=user_id,
                update_data=UserProfileUpdate(display_name="New Name"),
                expected_version=1,
            )

    async def test_successful_profile_update_increments_version(self):
        user_id = uuid.uuid4()
        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.is_active = True
        mock_user.is_deleted = False
        mock_user.username = "current_user"
        mock_user.display_name = "Old Name"
        mock_user.timezone = "UTC"
        mock_user.language = "en"
        mock_user.theme_preference = "system"
        mock_user.profile_data = {}
        mock_user.version = 1

        mock_session = AsyncMock()
        mock_dispatcher = MagicMock()
        mock_dispatcher.publish = AsyncMock()

        service = UserProfileService(session=mock_session, event_dispatcher=mock_dispatcher)
        service.get_profile = AsyncMock(return_value=mock_user)

        updated_user = await service.update_profile(
            user_id=user_id,
            update_data=UserProfileUpdate(display_name="New Name"),
            expected_version=1,
        )

        assert updated_user.display_name == "New Name"
        assert updated_user.version == 2
        mock_session.commit.assert_awaited_once()
