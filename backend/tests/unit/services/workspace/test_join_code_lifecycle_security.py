"""Unit tests for WP-1: Join-Code Non-Active Membership Safety Boundary.

Verifies:
- Join-code and open-join redemption NEVER silently reactivates an existing non-active membership.
- Join-code and open-join redemption NEVER overwrites a stored role.
- Active members receive WorkspaceMembershipConflictError.
- Suspended members receive WorkspaceMembershipSuspendedError (subclass of WorkspaceMembershipConflictError).
- Soft-deleted members receive WorkspaceMembershipConflictError.
- Other non-active statuses are rejected with WorkspaceMembershipConflictError.
- Role ceiling is strictly enforced: join-code and open join cannot grant roles above MEMBER (caps ADMIN/VIEWER at MEMBER).
- Genuinely new users successfully join with role=MEMBER.
"""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.api.v1.schemas.workspace_onboarding import JoinWorkspaceData
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.services.workspace.workspace_joining_service import (
    WorkspaceJoiningService,
    WorkspaceMembershipConflictError,
    WorkspaceMembershipSuspendedError,
)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_workspace_repo():
    return AsyncMock()


@pytest.fixture
def mock_settings_repo():
    return AsyncMock()


@pytest.fixture
def mock_member_repo():
    return AsyncMock()


@pytest.fixture
def mock_join_code_service():
    svc = AsyncMock()
    svc.validate_join_code_candidate = AsyncMock()
    svc.record_join_code_usage = AsyncMock()
    return svc


@pytest.fixture
def mock_invitation_service():
    svc = AsyncMock()
    svc.accept_invitation = AsyncMock()
    return svc


@pytest.fixture
def joining_service(
    mock_workspace_repo,
    mock_settings_repo,
    mock_member_repo,
    mock_join_code_service,
    mock_invitation_service,
):
    return WorkspaceJoiningService(
        workspace_repo=mock_workspace_repo,
        settings_repo=mock_settings_repo,
        member_repo=mock_member_repo,
        join_code_service=mock_join_code_service,
        invitation_service=mock_invitation_service,
    )


# ── Join-Code Lifecycle Security Tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_join_code_active_member_conflict(
    joining_service, mock_session, mock_workspace_repo, mock_member_repo, mock_join_code_service
):
    """Active member attempting join-code redemption must be rejected without mutating state."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Acme", slug="acme", public_id="ACME-CORP", status=WorkspaceStatus.ACTIVE.value)
    active_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )

    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_member_repo.get_membership.return_value = active_member

    with pytest.raises(WorkspaceMembershipConflictError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=user_id,
            user_email="active@example.com",
            workspace_identifier="ACME-CORP",
            join_code="VR-123456",
        )

    assert "already an active member" in str(exc_info.value)
    # Ensure no member was added/updated and no join code usage recorded
    mock_session.add.assert_not_called()
    mock_join_code_service.record_join_code_usage.assert_not_called()


@pytest.mark.asyncio
async def test_join_code_suspended_member_rejected_preserves_role_and_status(
    joining_service, mock_session, mock_workspace_repo, mock_member_repo, mock_join_code_service
):
    """Suspended member must NOT be silently reactivated or have role overwritten."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Acme", slug="acme", public_id="ACME-CORP", status=WorkspaceStatus.ACTIVE.value)
    suspended_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        role="VIEWER",  # Stored role must remain intact
        status=MemberStatus.SUSPENDED.value,
        is_deleted=False,
    )

    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_member_repo.get_membership.return_value = suspended_member

    with pytest.raises(WorkspaceMembershipSuspendedError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=user_id,
            user_email="suspended@example.com",
            workspace_identifier="ACME-CORP",
            join_code="VR-123456",
        )

    assert "Account status does not permit join-code redemption" in str(exc_info.value)
    assert issubclass(WorkspaceMembershipSuspendedError, WorkspaceMembershipConflictError)

    # Invariant checks: Stored role and status remain completely untouched
    assert suspended_member.status == MemberStatus.SUSPENDED.value
    assert suspended_member.role == "VIEWER"
    assert suspended_member.is_deleted is False
    mock_session.add.assert_not_called()
    mock_join_code_service.record_join_code_usage.assert_not_called()


@pytest.mark.asyncio
async def test_join_code_soft_deleted_member_rejected(
    joining_service, mock_session, mock_workspace_repo, mock_member_repo, mock_join_code_service
):
    """Soft-deleted member must NOT be reactivated or re-created via join-code."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Acme", slug="acme", public_id="ACME-CORP", status=WorkspaceStatus.ACTIVE.value)
    deleted_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
        is_deleted=True,
    )

    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_member_repo.get_membership.return_value = deleted_member

    with pytest.raises(WorkspaceMembershipConflictError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=user_id,
            user_email="deleted@example.com",
            workspace_identifier="ACME-CORP",
            join_code="VR-123456",
        )

    assert "Account status does not permit join-code redemption" in str(exc_info.value)
    assert deleted_member.is_deleted is True
    mock_session.add.assert_not_called()
    mock_join_code_service.record_join_code_usage.assert_not_called()


@pytest.mark.asyncio
async def test_join_code_other_non_active_status_rejected(
    joining_service, mock_session, mock_workspace_repo, mock_member_repo, mock_join_code_service
):
    """Membership with unrecognized non-active status is rejected cleanly."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Acme", slug="acme", public_id="ACME-CORP", status=WorkspaceStatus.ACTIVE.value)
    other_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        role="MEMBER",
        status="ARCHIVED_STATUS",
        is_deleted=False,
    )

    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_member_repo.get_membership.return_value = other_member

    with pytest.raises(WorkspaceMembershipConflictError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=user_id,
            user_email="other@example.com",
            workspace_identifier="ACME-CORP",
            join_code="VR-123456",
        )

    assert "Existing membership status does not permit joining with this code" in str(exc_info.value)
    mock_session.add.assert_not_called()
    mock_join_code_service.record_join_code_usage.assert_not_called()


@pytest.mark.asyncio
async def test_join_code_role_ceiling_enforced_against_elevated_roles(
    joining_service, mock_session, mock_workspace_repo, mock_member_repo, mock_join_code_service, mock_settings_repo
):
    """Join-code self-service default role must be capped at MEMBER even if configured higher."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Acme", slug="acme", public_id="ACME-CORP", status=WorkspaceStatus.ACTIVE.value)

    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_member_repo.get_membership.return_value = None
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=ws_id,
        settings_json={"join_code_require_approval": False},
    )
    # Code candidate validation reports an attempt to grant ADMIN role
    mock_join_code_service.validate_join_code_candidate.return_value = (True, None, "ADMIN")

    result = await joining_service.join_workspace(
        session=mock_session,
        user_id=user_id,
        user_email="newbie@example.com",
        workspace_identifier="ACME-CORP",
        join_code="VR-123456",
    )

    assert isinstance(result, JoinWorkspaceData)
    # Role ceiling enforced: ADMIN capped to MEMBER
    assert result.role == "MEMBER"
    assert result.status == "ACTIVE"
    mock_session.add.assert_called()


@pytest.mark.asyncio
async def test_join_code_new_user_success(
    joining_service, mock_session, mock_workspace_repo, mock_member_repo, mock_join_code_service, mock_settings_repo
):
    """Genuinely new user joins successfully with brand-new MEMBER record."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Acme", slug="acme", public_id="ACME-CORP", status=WorkspaceStatus.ACTIVE.value)

    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_member_repo.get_membership.return_value = None
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=ws_id,
        settings_json={"join_code_require_approval": False},
    )
    mock_join_code_service.validate_join_code_candidate.return_value = (True, None, "MEMBER")

    result = await joining_service.join_workspace(
        session=mock_session,
        user_id=user_id,
        user_email="newbie@example.com",
        workspace_identifier="ACME-CORP",
        join_code="VR-123456",
    )

    assert isinstance(result, JoinWorkspaceData)
    assert result.workspace_id == ws_id
    assert result.role == "MEMBER"
    assert result.status == "ACTIVE"
    mock_join_code_service.record_join_code_usage.assert_awaited_once_with(mock_session, ws_id)
    # Verify new WorkspaceMember added to session
    added_objects = [call.args[0] for call in mock_session.add.call_args_list if call.args]
    member_records = [obj for obj in added_objects if isinstance(obj, WorkspaceMember)]
    assert len(member_records) == 1
    assert member_records[0].user_id == user_id
    assert member_records[0].workspace_id == ws_id
    assert member_records[0].role == "MEMBER"
    assert member_records[0].status == MemberStatus.ACTIVE.value


# ── Open-Join Lifecycle Security Tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_open_join_suspended_member_rejected(
    joining_service, mock_session, mock_workspace_repo, mock_member_repo, mock_settings_repo
):
    """Suspended member must NOT be reactivated or role overwritten via open join."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Public WS", slug="public-ws", public_id="PUB-WS", status=WorkspaceStatus.ACTIVE.value)
    suspended_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        role="VIEWER",
        status=MemberStatus.SUSPENDED.value,
        is_deleted=False,
    )

    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=ws_id,
        settings_json={"open_join": True, "default_join_role": "MEMBER"},
    )
    mock_member_repo.get_membership.return_value = suspended_member

    with pytest.raises(WorkspaceMembershipSuspendedError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=user_id,
            user_email="suspended@example.com",
            workspace_identifier="PUB-WS",
        )

    assert "Account status does not permit open joining" in str(exc_info.value)
    assert suspended_member.status == MemberStatus.SUSPENDED.value
    assert suspended_member.role == "VIEWER"
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_open_join_soft_deleted_member_rejected(
    joining_service, mock_session, mock_workspace_repo, mock_member_repo, mock_settings_repo
):
    """Soft-deleted member must NOT be reactivated or re-created via open join."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Public WS", slug="public-ws", public_id="PUB-WS", status=WorkspaceStatus.ACTIVE.value)
    deleted_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
        is_deleted=True,
    )

    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=ws_id,
        settings_json={"open_join": True, "default_join_role": "MEMBER"},
    )
    mock_member_repo.get_membership.return_value = deleted_member

    with pytest.raises(WorkspaceMembershipConflictError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=user_id,
            user_email="deleted@example.com",
            workspace_identifier="PUB-WS",
        )

    assert "Account status does not permit open joining" in str(exc_info.value)
    assert deleted_member.is_deleted is True
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_open_join_role_ceiling_enforced_against_elevated_roles(
    joining_service, mock_session, mock_workspace_repo, mock_member_repo, mock_settings_repo
):
    """Open-join default role configured as OWNER/ADMIN/VIEWER is capped at MEMBER."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(id=ws_id, name="Public WS", slug="public-ws", public_id="PUB-WS", status=WorkspaceStatus.ACTIVE.value)

    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_member_repo.get_membership.return_value = None
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=ws_id,
        settings_json={"open_join": True, "default_join_role": "ADMIN"},
    )

    result = await joining_service.join_workspace(
        session=mock_session,
        user_id=user_id,
        user_email="newbie@example.com",
        workspace_identifier="PUB-WS",
    )

    assert isinstance(result, JoinWorkspaceData)
    assert result.role == "MEMBER"
    assert result.status == "ACTIVE"
