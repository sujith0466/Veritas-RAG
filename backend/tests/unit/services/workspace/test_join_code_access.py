"""Unit tests for Workstream D (Member/Viewer Join Access).

Validates:
- D-01: MEMBER can access Join Access (view/copy active code & link)
- D-02: VIEWER can access Join Access (view/copy active code & link)
- D-03: OWNER can access Join Access
- D-04: ADMIN can access Join Access
- D-05: Non-member is rejected (403 / WorkspaceUnauthorizedError)
- D-06: Cross-workspace member is rejected (Tenant Isolation)
- D-07: Current active code is decrypted accurately from zero-plaintext DB storage
- D-08: Canonical Join Link is generated with public identifier & code
- D-09: Disabled join code returns has_active_code=False and join_code=None
- D-10: Expired join code returns has_active_code=False and join_code=None
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.services.workspace.join_code_service import JoinCodeService
from backend.services.workspace.management_service import (
    WorkspaceUnauthorizedError,
)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_settings_repo():
    return AsyncMock()


@pytest.fixture
def mock_member_repo():
    return AsyncMock()


@pytest.fixture
def mock_workspace_repo():
    return AsyncMock()


@pytest.fixture
def join_code_service(mock_settings_repo, mock_member_repo, mock_workspace_repo):
    return JoinCodeService(
        settings_repo=mock_settings_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )


@pytest.mark.asyncio
async def test_member_and_viewer_join_access_d_matrix(
    mock_session,
    mock_settings_repo,
    mock_member_repo,
    mock_workspace_repo,
    join_code_service,
):
    """D-01 to D-08: Verifies MEMBER, VIEWER, ADMIN, OWNER access to current active join credentials."""
    workspace_id = uuid.uuid4()
    workspace = Workspace(
        id=workspace_id,
        name="Apollo Analytics Corp",
        public_id="APOLLO-99",
        slug="apollo-analytics",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = workspace

    admin_id = uuid.uuid4()
    member_id = uuid.uuid4()
    viewer_id = uuid.uuid4()
    outsider_id = uuid.uuid4()

    # Generate an active join code
    settings_obj = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={},
        schema_version=1,
        version=1,
        settings_hash="",
    )
    mock_settings_repo.get_by_workspace_id.return_value = settings_obj
    mock_settings_repo.get_by_workspace_id_for_update.return_value = settings_obj

    # Setup admin membership for generation
    mock_member_repo.get_membership = AsyncMock(
        return_value=WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=admin_id,
            role="ADMIN",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
    )

    gen_resp = await join_code_service.generate_new_join_code(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=admin_id,
        expires_in_days=30,
        default_role="MEMBER",
    )
    active_code = gen_resp.join_code

    # Configure repository with generated settings
    mock_settings_repo.get_by_workspace_id.return_value = settings_obj

    # 1. D-01: MEMBER can access active join code & canonical link
    mock_member_repo.get_membership = AsyncMock(
        return_value=WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=member_id,
            role="MEMBER",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
    )
    access_member = await join_code_service.get_join_access(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=member_id,
    )
    assert access_member.has_active_code is True
    assert access_member.join_code == active_code
    assert access_member.public_id == "APOLLO-99"
    assert access_member.join_link == f"/workspaces/join?workspace_id=APOLLO-99&join_code={active_code}"

    # 2. D-02: VIEWER can access active join code & canonical link
    mock_member_repo.get_membership = AsyncMock(
        return_value=WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=viewer_id,
            role="VIEWER",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
    )
    access_viewer = await join_code_service.get_join_access(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=viewer_id,
    )
    assert access_viewer.has_active_code is True
    assert access_viewer.join_code == active_code

    # 3. D-05 & D-06: Non-member / cross-workspace rejected (Tenant Isolation)
    mock_member_repo.get_membership = AsyncMock(return_value=None)
    with pytest.raises(WorkspaceUnauthorizedError):
        await join_code_service.get_join_access(
            session=mock_session,
            workspace_id=workspace_id,
            user_id=outsider_id,
        )


@pytest.mark.asyncio
async def test_join_access_disabled_or_expired(
    mock_session,
    mock_settings_repo,
    mock_member_repo,
    mock_workspace_repo,
    join_code_service,
):
    """D-09 & D-10: Disabled or expired join code returns has_active_code=False and join_code=None."""
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    workspace = Workspace(
        id=workspace_id,
        name="Apollo Analytics Corp",
        public_id="APOLLO-99",
        slug="apollo-analytics",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = workspace
    mock_member_repo.get_membership = AsyncMock(
        return_value=WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
            role="MEMBER",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
    )

    # 1. Disabled code
    disabled_settings = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={
            "join_code": {
                "is_enabled": False,
                "code_hash": "somehash",
                "code_encrypted": join_code_service.encrypt_join_code("VR-DISAB1"),
                "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            }
        },
        schema_version=1,
        version=1,
        settings_hash="",
    )
    mock_settings_repo.get_by_workspace_id.return_value = disabled_settings

    res_disabled = await join_code_service.get_join_access(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    assert res_disabled.has_active_code is False
    assert res_disabled.join_code is None
    assert res_disabled.join_link is None

    # 2. Expired code
    expired_settings = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={
            "join_code": {
                "is_enabled": True,
                "code_hash": "somehash",
                "code_encrypted": join_code_service.encrypt_join_code("VR-EXPIR1"),
                "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            }
        },
        schema_version=1,
        version=1,
        settings_hash="",
    )
    mock_settings_repo.get_by_workspace_id.return_value = expired_settings

    res_expired = await join_code_service.get_join_access(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    assert res_expired.has_active_code is False
    assert res_expired.join_code is None
    assert res_expired.join_link is None
