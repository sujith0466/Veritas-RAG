"""Unit tests for F3.6 Workspace Settings Service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.workspace_settings import (
    WorkspaceSettingsPayload,
    get_default_workspace_settings,
)
from backend.models.entities.workspace_member import WorkspaceMember
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.models.entities.workspace_settings_history import WorkspaceSettingsHistory
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.repositories.workspace_settings import WorkspaceSettingsRepository
from backend.repositories.workspace_settings_history import WorkspaceSettingsHistoryRepository
from backend.services.workspace.management_service import (
    WorkspaceConflictError,
    WorkspaceUnauthorizedError,
)
from backend.services.workspace.settings_service import (
    WorkspaceSettingsService,
    _compute_settings_hash,
    _deep_merge,
)


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def settings_repo(mock_session):
    repo = AsyncMock(spec=WorkspaceSettingsRepository)
    repo.session = mock_session
    return repo


@pytest.fixture
def history_repo(mock_session):
    repo = AsyncMock(spec=WorkspaceSettingsHistoryRepository)
    repo.session = mock_session
    return repo


@pytest.fixture
def workspace_repo(mock_session):
    repo = AsyncMock(spec=WorkspaceRepository)
    repo.session = mock_session
    return repo


@pytest.fixture
def member_repo(mock_session):
    repo = AsyncMock(spec=WorkspaceMemberRepository)
    repo.session = mock_session
    return repo


@pytest.fixture
def settings_service(settings_repo, history_repo, workspace_repo, member_repo):
    return WorkspaceSettingsService(settings_repo, history_repo, workspace_repo, member_repo)


def test_default_workspace_settings_structure():
    defaults = get_default_workspace_settings()
    expected_categories = [
        "general",
        "security",
        "ai",
        "rag",
        "storage",
        "notifications",
        "integrations",
        "limits",
        "branding",
        "api",
        "custom_extensions",
    ]
    for cat in expected_categories:
        assert cat in defaults, f"Missing category: {cat}"

    assert defaults["ai"]["temperature"] == 0.2
    assert defaults["rag"]["retrieval_mode"] == "HYBRID"
    assert defaults["rag"]["chunk_size"] == 512
    assert defaults["general"]["default_language"] == "en"


def test_deep_merge_and_immutable_protection():
    base = {
        "workspace_id": "original-id",
        "ai": {"temperature": 0.2, "default_model": "gpt-4o"},
        "rag": {"chunk_size": 512},
    }
    patch_data = {
        "workspace_id": "attempted-override-id",
        "ai": {"temperature": 0.7},
        "new_key": "val",
    }
    merged = _deep_merge(base, patch_data)

    # Immutable key was stripped/preserved
    assert merged["workspace_id"] == "original-id"
    # Nested field updated
    assert merged["ai"]["temperature"] == 0.7
    # Sibling nested field preserved
    assert merged["ai"]["default_model"] == "gpt-4o"
    # Other root fields preserved
    assert merged["rag"]["chunk_size"] == 512
    assert merged["new_key"] == "val"


def test_settings_hash_determinism():
    d1 = {"b": 2, "a": 1}
    d2 = {"a": 1, "b": 2}
    assert _compute_settings_hash(d1) == _compute_settings_hash(d2)


@pytest.mark.asyncio
async def test_get_settings_initializes_defaults_when_empty(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="MEMBER"
    )
    settings_repo.get_by_workspace_id.return_value = None

    settings = await settings_service.get_settings(
        session=mock_session,
        workspace_id=ws_id,
        user_id=user_id,
    )

    assert settings.workspace_id == ws_id
    assert settings.version == 1
    assert settings.schema_version == 1
    assert "ai" in settings.settings_json
    mock_session.add.assert_called()


@pytest.mark.asyncio
async def test_patch_settings_success(
    settings_service, settings_repo, history_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    existing_settings = WorkspaceSettings(
        workspace_id=ws_id,
        settings_json=get_default_workspace_settings(),
        schema_version=1,
        version=1,
        settings_hash="old-hash",
        updated_at=now,
    )

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="OWNER"
    )
    settings_repo.get_by_workspace_id_for_update.return_value = existing_settings

    patch_payload = {
        "ai": {"temperature": 0.8},
        "branding": {"primary_color": "#10b981"},
    }

    with patch("backend.core.events.dispatcher.EventDispatcher.publish", new_callable=AsyncMock):
        updated = await settings_service.patch_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            patch_data=patch_payload,
        )

    assert updated.version == 2
    assert updated.settings_json["ai"]["temperature"] == 0.8
    assert updated.settings_json["branding"]["primary_color"] == "#10b981"
    assert updated.settings_hash != "old-hash"
    # History snapshot recorded
    assert mock_session.add.call_count >= 2


@pytest.mark.asyncio
async def test_patch_settings_schema_validation_error(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    existing_settings = WorkspaceSettings(
        workspace_id=ws_id,
        settings_json=get_default_workspace_settings(),
        schema_version=1,
        version=1,
        settings_hash="old-hash",
        updated_at=now,
    )

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="OWNER"
    )
    settings_repo.get_by_workspace_id_for_update.return_value = existing_settings

    # Temperature > 2.0 violates range constraint
    patch_payload = {"ai": {"temperature": 99.0}}

    with pytest.raises(ValidationError):
        await settings_service.patch_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            patch_data=patch_payload,
        )


@pytest.mark.asyncio
async def test_patch_settings_concurrency_conflict(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(minutes=10)

    existing_settings = WorkspaceSettings(
        workspace_id=ws_id,
        settings_json=get_default_workspace_settings(),
        schema_version=1,
        version=1,
        settings_hash="old-hash",
        updated_at=now,
    )

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="OWNER"
    )
    settings_repo.get_by_workspace_id_for_update.return_value = existing_settings

    with pytest.raises(WorkspaceConflictError):
        await settings_service.patch_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=stale_time,
            patch_data={"ai": {"temperature": 0.5}},
        )


@pytest.mark.asyncio
async def test_import_settings_dry_run(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="ADMIN"
    )
    settings_repo.get_by_workspace_id.return_value = None

    import_data = get_default_workspace_settings()
    import_data["ai"]["temperature"] = 0.4

    result = await settings_service.import_settings(
        session=mock_session,
        workspace_id=ws_id,
        user_id=user_id,
        expected_updated_at=now,
        import_payload=import_data,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["valid"] is True
    assert "settings_hash" in result
    # In dry run mode, no DB write performed
    mock_session.commit.assert_not_awaited()
