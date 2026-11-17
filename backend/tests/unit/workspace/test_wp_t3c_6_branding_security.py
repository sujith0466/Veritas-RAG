"""Unit tests for WP-T3C-6: Workspace Settings and Section 3.2 Branding Security Alignment.

Verifies:
1. Branding removed from ROUTINE_SETTINGS_CATEGORIES and added to SENSITIVE_CATEGORIES.
2. stage_branding_preview restricted strictly to WorkspaceRole.OWNER (rejects ADMIN/MEMBER with 403 / WorkspaceUnauthorizedError).
3. publish_branding restricted strictly to WorkspaceRole.OWNER (rejects ADMIN/MEMBER with 403 / WorkspaceUnauthorizedError).
4. rollback_branding restricted strictly to WorkspaceRole.OWNER (rejects ADMIN/MEMBER with 403 / WorkspaceUnauthorizedError).
"""

from datetime import datetime, timezone
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.entities.workspace_member import WorkspaceMember, WorkspaceRole
from backend.services.workspace.management_service import WorkspaceUnauthorizedError
from backend.services.workspace.settings_service import (
    ROUTINE_SETTINGS_CATEGORIES,
    SENSITIVE_CATEGORIES,
    WorkspaceSettingsService,
)


@pytest.fixture
def mock_workspace_repo():
    return AsyncMock()


@pytest.fixture
def mock_member_repo():
    return AsyncMock()


@pytest.fixture
def mock_settings_repo():
    return AsyncMock()


@pytest.fixture
def mock_history_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_workspace_repo, mock_member_repo, mock_settings_repo, mock_history_repo):
    return WorkspaceSettingsService(
        workspace_repo=mock_workspace_repo,
        member_repo=mock_member_repo,
        settings_repo=mock_settings_repo,
        history_repo=mock_history_repo,
    )


def test_branding_category_classification():
    """Verifies category classification under Section 3.2."""
    assert "branding" not in ROUTINE_SETTINGS_CATEGORIES
    assert "branding" in SENSITIVE_CATEGORIES


@pytest.mark.asyncio
async def test_stage_branding_preview_admin_and_member_rejected(service, mock_member_repo):
    ws_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    member_id = uuid.uuid4()

    # 1. ADMIN attempt rejected
    admin_member = WorkspaceMember(workspace_id=ws_id, user_id=admin_id, role=WorkspaceRole.ADMIN.value)
    mock_member_repo.get_membership.return_value = admin_member

    with pytest.raises(WorkspaceUnauthorizedError, match="Only workspace OWNER can stage branding preview"):
        await service.stage_branding_preview(
            workspace_id=ws_id,
            user_id=admin_id,
            branding_dict={"primary_color": "#00ff00"},
            is_platform_admin=False,
        )

    # 2. MEMBER attempt rejected
    member_user = WorkspaceMember(workspace_id=ws_id, user_id=member_id, role=WorkspaceRole.MEMBER.value)
    mock_member_repo.get_membership.return_value = member_user

    with pytest.raises(WorkspaceUnauthorizedError, match="Only workspace OWNER can stage branding preview"):
        await service.stage_branding_preview(
            workspace_id=ws_id,
            user_id=member_id,
            branding_dict={"primary_color": "#00ff00"},
            is_platform_admin=False,
        )


@pytest.mark.asyncio
async def test_stage_branding_preview_owner_allowed(service, mock_member_repo):
    ws_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    owner_member = WorkspaceMember(workspace_id=ws_id, user_id=owner_id, role=WorkspaceRole.OWNER.value)
    mock_member_repo.get_membership.return_value = owner_member

    with patch("backend.cache.client.get_redis_client", return_value=None):
        result = await service.stage_branding_preview(
            workspace_id=ws_id,
            user_id=owner_id,
            branding_dict={"primary_color": "#00ff00"},
            is_platform_admin=False,
        )

    assert result["is_preview"] is True
    assert result["branding"]["primary_color"] == "#00ff00"


@pytest.mark.asyncio
async def test_publish_branding_admin_rejected(service, mock_member_repo):
    ws_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    session = AsyncMock()

    admin_member = WorkspaceMember(workspace_id=ws_id, user_id=admin_id, role=WorkspaceRole.ADMIN.value)
    mock_member_repo.get_membership.return_value = admin_member

    with pytest.raises(WorkspaceUnauthorizedError, match="Only workspace OWNER can publish branding"):
        await service.publish_branding(
            session=session,
            workspace_id=ws_id,
            user_id=admin_id,
            expected_updated_at=datetime.now(timezone.utc),
            branding_dict={"primary_color": "#ff0000"},
            is_platform_admin=False,
        )


@pytest.mark.asyncio
async def test_rollback_branding_admin_rejected(service, mock_member_repo):
    ws_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    session = AsyncMock()

    admin_member = WorkspaceMember(workspace_id=ws_id, user_id=admin_id, role=WorkspaceRole.ADMIN.value)
    mock_member_repo.get_membership.return_value = admin_member

    with pytest.raises(WorkspaceUnauthorizedError, match="Only workspace OWNER can rollback branding"):
        await service.rollback_branding(
            session=session,
            workspace_id=ws_id,
            user_id=admin_id,
            expected_updated_at=datetime.now(timezone.utc),
            target_version=1,
            is_platform_admin=False,
        )
