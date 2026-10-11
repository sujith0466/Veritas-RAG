"""Tests for Privacy Data Export and Account Lifecycle Services."""

import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

from backend.services.user_export import DataExportService, _scrub_dict, FORBIDDEN_EXPORT_KEYS
from backend.services.user_lifecycle import (
    UserLifecycleService,
    ReauthenticationFailedException,
    SoleWorkspaceOwnerConflictException,
    LifecycleException,
)
from backend.models.entities.user import User
from backend.core.security.password import get_password_hash


def test_scrub_dict_removes_sensitive_keys():
    raw = {
        "email": "test@example.com",
        "hashed_password": "supersecretpasswordhash",
        "nested": {
            "token": "sensitive_jwt_token",
            "salt": "random_salt",
            "safe_key": "safe_value",
        },
        "safe_list": [
            {"secret_key": "secret", "name": "item1"},
            "plain_string"
        ]
    }
    cleaned = _scrub_dict(raw)

    assert "hashed_password" not in cleaned
    assert "token" not in cleaned["nested"]
    assert "salt" not in cleaned["nested"]
    assert cleaned["nested"]["safe_key"] == "safe_value"
    assert "secret_key" not in cleaned["safe_list"][0]
    assert cleaned["safe_list"][0]["name"] == "item1"


@pytest.mark.asyncio
async def test_user_lifecycle_requires_delete_confirmation():
    session = AsyncMock()
    service = UserLifecycleService(session)

    with pytest.raises(LifecycleException, match="must type DELETE"):
        await service.deactivate_user_account(
            user_id=uuid.uuid4(),
            password="any",
            confirmation_text="NO",
        )


@pytest.mark.asyncio
async def test_user_lifecycle_reauthentication_failure():
    session = AsyncMock()
    service = UserLifecycleService(session)

    hashed = get_password_hash("CorrectPassword123!")
    user = User(
        id=uuid.uuid4(),
        email="test_user@example.com",
        role="viewer",
        is_active=True,
        hashed_password=hashed,
    )

    with pytest.raises(ReauthenticationFailedException):
        await service.verify_credentials(user, "WrongPassword!")

    # Success with correct password
    await service.verify_credentials(user, "CorrectPassword123!")
