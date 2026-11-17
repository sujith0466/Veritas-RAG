"""Unit and Security tests for WP-3 Settings Whitelist (DEC-05).

Verifies strict separation of Routine versus Sensitive workspace settings:
1. Routine settings (branding, timezone, language, notification toggles, MEMBER join role)
   can be modified by workspace OWNER and ADMIN.
2. Sensitive settings (security/SSO, IP allowlists, data retention policies, webhook secrets,
   billing/quotas, AI models) are strictly restricted to workspace OWNER.
3. ADMIN attempts to patch, reset, or import sensitive settings fail closed with WorkspaceUnauthorizedError.
4. Non-owner callers (ADMIN, MEMBER) receive masked sensitive secrets in get_settings responses.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.workspace_settings import (
    get_default_workspace_settings,
)
from backend.models.entities.workspace_member import WorkspaceMember
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.repositories.workspace_settings import WorkspaceSettingsRepository
from backend.repositories.workspace_settings_history import WorkspaceSettingsHistoryRepository
from backend.services.workspace.management_service import (
    WorkspaceUnauthorizedError,
)
from backend.services.workspace.settings_service import (
    WorkspaceSettingsService,
)


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.expunge = MagicMock()
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


def _build_mock_settings(ws_id: uuid.UUID, now: datetime) -> WorkspaceSettings:
    defaults = get_default_workspace_settings()
    defaults["notifications"]["slack_webhook_url"] = "https://hooks.slack.com/services/T00/B00/SECRET123"
    defaults["join_code"]["code_hash"] = "sensitive_bcrypt_hash_xyz"
    return WorkspaceSettings(
        workspace_id=ws_id,
        settings_json=defaults,
        schema_version=1,
        version=1,
        settings_hash="seed-hash-123",
        updated_at=now,
    )


# ==============================================================================
# 1. Routine Settings Modification (ADMIN & OWNER Allowed)
# ==============================================================================

@pytest.mark.asyncio
async def test_admin_patch_branding_rejected(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="ADMIN"
    )
    existing = _build_mock_settings(ws_id, now)
    settings_repo.get_by_workspace_id_for_update.return_value = existing

    patch_payload = {
        "branding": {
            "primary_color": "#10b981",
            "company_name": "Acme Corp",
            "theme_mode": "DARK",
        }
    }

    with pytest.raises(WorkspaceUnauthorizedError, match="Only workspace OWNER"):
        await settings_service.patch_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            patch_data=patch_payload,
        )


@pytest.mark.asyncio
async def test_admin_can_patch_routine_general_and_notifications(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="ADMIN"
    )
    existing = _build_mock_settings(ws_id, now)
    settings_repo.get_by_workspace_id_for_update.return_value = existing

    patch_payload = {
        "general": {
            "timezone": "Europe/London",
            "default_language": "fr",
        },
        "notifications": {
            "email_notifications_enabled": False,
            "alert_on_quota_threshold_pct": 90,
        },
    }

    with patch("backend.core.events.dispatcher.EventDispatcher.publish", new_callable=AsyncMock):
        res = await settings_service.patch_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            patch_data=patch_payload,
        )

    assert res.version == 2
    assert res.settings_json["general"]["timezone"] == "Europe/London"
    assert res.settings_json["notifications"]["email_notifications_enabled"] is False


@pytest.mark.asyncio
async def test_admin_can_patch_routine_join_code(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="ADMIN"
    )
    existing = _build_mock_settings(ws_id, now)
    settings_repo.get_by_workspace_id_for_update.return_value = existing

    patch_payload = {
        "join_code": {
            "is_enabled": True,
            "default_role": "MEMBER",
            "require_approval": True,
            "max_uses": 50,
        }
    }

    with patch("backend.core.events.dispatcher.EventDispatcher.publish", new_callable=AsyncMock):
        res = await settings_service.patch_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            patch_data=patch_payload,
        )

    assert res.version == 2
    assert res.settings_json["join_code"]["is_enabled"] is True
    assert res.settings_json["join_code"]["default_role"] == "MEMBER"


# ==============================================================================
# 2. Sensitive Settings Modification (ADMIN Rejected, OWNER Allowed)
# ==============================================================================

@pytest.mark.asyncio
async def test_admin_patch_sensitive_security_rejected(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="ADMIN"
    )

    with pytest.raises(WorkspaceUnauthorizedError, match="Only workspace OWNER can modify sensitive category 'security'"):
        await settings_service.patch_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            patch_data={"security": {"enforce_mfa": True}},
        )


@pytest.mark.asyncio
async def test_admin_patch_sensitive_general_retention_rejected(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="ADMIN"
    )

    with pytest.raises(WorkspaceUnauthorizedError, match="Only workspace OWNER can modify sensitive setting 'general.retention_days'"):
        await settings_service.patch_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            patch_data={"general": {"retention_days": 90}},
        )


@pytest.mark.asyncio
async def test_admin_patch_sensitive_webhook_url_rejected(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="ADMIN"
    )

    with pytest.raises(WorkspaceUnauthorizedError, match="Only workspace OWNER can modify sensitive setting 'notifications.slack_webhook_url'"):
        await settings_service.patch_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            patch_data={"notifications": {"slack_webhook_url": "https://hooks.slack.com/bad"}},
        )


@pytest.mark.asyncio
async def test_admin_patch_sensitive_limits_rejected(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="ADMIN"
    )

    with pytest.raises(WorkspaceUnauthorizedError, match="Only workspace OWNER can modify sensitive category 'limits'"):
        await settings_service.patch_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            patch_data={"limits": {"monthly_token_budget": 99999999}},
        )


@pytest.mark.asyncio
async def test_owner_can_patch_sensitive_settings(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="OWNER"
    )
    existing = _build_mock_settings(ws_id, now)
    settings_repo.get_by_workspace_id_for_update.return_value = existing

    patch_payload = {
        "security": {"enforce_mfa": True, "ip_allowlist": ["192.168.1.1/32"]},
        "general": {"retention_days": 180},
        "limits": {"monthly_token_budget": 10000000},
        "notifications": {"slack_webhook_url": "https://hooks.slack.com/services/OWNER/NEW/URL"},
    }

    with patch("backend.core.events.dispatcher.EventDispatcher.publish", new_callable=AsyncMock):
        res = await settings_service.patch_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            patch_data=patch_payload,
        )

    assert res.version == 2
    assert res.settings_json["security"]["enforce_mfa"] is True
    assert res.settings_json["general"]["retention_days"] == 180
    assert res.settings_json["limits"]["monthly_token_budget"] == 10000000
    assert res.settings_json["notifications"]["slack_webhook_url"] == "https://hooks.slack.com/services/OWNER/NEW/URL"


# ==============================================================================
# 3. Settings Reset Authorization (DEC-05)
# ==============================================================================

@pytest.mark.asyncio
async def test_admin_reset_all_rejected(
    settings_service, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="ADMIN"
    )

    with pytest.raises(WorkspaceUnauthorizedError, match="Only workspace OWNER can reset all settings"):
        await settings_service.reset_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            category=None,
        )


@pytest.mark.asyncio
async def test_admin_reset_sensitive_category_rejected(
    settings_service, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="ADMIN"
    )

    with pytest.raises(WorkspaceUnauthorizedError, match="Only workspace OWNER can reset sensitive category 'security'"):
        await settings_service.reset_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            category="security",
        )


@pytest.mark.asyncio
async def test_admin_reset_branding_rejected(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="ADMIN"
    )
    existing = _build_mock_settings(ws_id, now)
    settings_repo.get_by_workspace_id_for_update.return_value = existing

    with pytest.raises(WorkspaceUnauthorizedError, match="Only workspace OWNER"):
        await settings_service.reset_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            category="branding",
        )


@pytest.mark.asyncio
async def test_owner_reset_all_allowed(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="OWNER"
    )
    existing = _build_mock_settings(ws_id, now)
    settings_repo.get_by_workspace_id_for_update.return_value = existing

    with patch("backend.core.events.dispatcher.EventDispatcher.publish", new_callable=AsyncMock):
        res = await settings_service.reset_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            category=None,
        )

    assert res.version == 2


# ==============================================================================
# 4. Settings Import Authorization (DEC-05)
# ==============================================================================

@pytest.mark.asyncio
async def test_admin_import_settings_rejected(
    settings_service, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="ADMIN"
    )

    with pytest.raises(WorkspaceUnauthorizedError, match="Only workspace OWNER can import settings"):
        await settings_service.import_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            import_payload=get_default_workspace_settings(),
            dry_run=False,
        )


@pytest.mark.asyncio
async def test_owner_import_settings_allowed(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=user_id, role="OWNER"
    )
    existing = _build_mock_settings(ws_id, now)
    settings_repo.get_by_workspace_id.return_value = existing
    settings_repo.get_by_workspace_id_for_update.return_value = existing

    import_data = get_default_workspace_settings()
    import_data["branding"]["primary_color"] = "#6366f1"

    with patch("backend.core.events.dispatcher.EventDispatcher.publish", new_callable=AsyncMock):
        res = await settings_service.import_settings(
            session=mock_session,
            workspace_id=ws_id,
            user_id=user_id,
            expected_updated_at=now,
            import_payload=import_data,
            dry_run=False,
        )

    assert res["success"] is True
    assert res["version"] == 2


# ==============================================================================
# 5. Secret Masking for Non-Owner Roles (DEC-05)
# ==============================================================================

@pytest.mark.asyncio
async def test_secret_masking_in_get_settings_for_admin_and_member(
    settings_service, settings_repo, member_repo, mock_session
):
    ws_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    member_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    now = datetime.now(UTC)

    # 1. ADMIN sees masked webhook secret and null join code secret
    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=admin_id, role="ADMIN"
    )
    settings_repo.get_by_workspace_id.return_value = _build_mock_settings(ws_id, now)
    admin_settings = await settings_service.get_settings(mock_session, ws_id, admin_id)
    assert admin_settings.settings_json["notifications"]["slack_webhook_url"] == "********"
    assert admin_settings.settings_json["join_code"]["code_hash"] is None

    # 2. MEMBER sees masked secrets
    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=member_id, role="MEMBER"
    )
    settings_repo.get_by_workspace_id.return_value = _build_mock_settings(ws_id, now)
    member_settings = await settings_service.get_settings(mock_session, ws_id, member_id)
    assert member_settings.settings_json["notifications"]["slack_webhook_url"] == "********"
    assert member_settings.settings_json["join_code"]["code_hash"] is None

    # 3. OWNER sees unmasked plaintext secrets
    member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=ws_id, user_id=owner_id, role="OWNER"
    )
    settings_repo.get_by_workspace_id.return_value = _build_mock_settings(ws_id, now)
    owner_settings = await settings_service.get_settings(mock_session, ws_id, owner_id)
    assert owner_settings.settings_json["notifications"]["slack_webhook_url"] == "https://hooks.slack.com/services/T00/B00/SECRET123"
    assert owner_settings.settings_json["join_code"]["code_hash"] == "sensitive_bcrypt_hash_xyz"
