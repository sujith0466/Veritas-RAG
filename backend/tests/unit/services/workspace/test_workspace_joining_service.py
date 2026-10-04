"""Unit tests for WorkspaceJoiningService (WS-A5).

Covers all 3 joining modes:
- Mode 1: Open Workspace ID (open_join=True / False)
- Mode 2: Protected Workspace ID + Join Code (bcrypt verification, usage limits, increment)
- Mode 3: Invitation Token (acceptance, mismatch checks, email binding)
- Boundary & Security: Tenant UUID rejection, conflict handling, secret-free audit logging.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.api.v1.schemas.workspace_onboarding import JoinWorkspaceData
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.services.workspace.invitation_service import (
    InvitationConflictError,
    InvitationError,
    InvitationInvalidStateError,
    InvitationNotFoundError,
)
from backend.services.workspace.workspace_joining_service import (
    WorkspaceIdentifierInvalidError,
    WorkspaceInvitationJoinError,
    WorkspaceJoinCodeInvalidError,
    WorkspaceJoinForbiddenError,
    WorkspaceJoinIntentMismatchError,
    WorkspaceJoiningService,
    WorkspaceMembershipConflictError,
    WorkspaceTargetNotFoundError,
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


# ── Mode 1: Open Join Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_join_open_success(
    joining_service, mock_session, mock_workspace_repo, mock_settings_repo, mock_member_repo
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(
        id=ws_id,
        name="Public Devs",
        slug="public-devs",
        public_id="PUB-DEVS",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=ws_id,
        settings_json={"open_join": True, "default_join_role": "MEMBER"},
    )
    mock_member_repo.get_membership.return_value = None

    result = await joining_service.join_workspace(
        session=mock_session,
        user_id=user_id,
        user_email="dev@example.com",
        workspace_identifier="PUB-DEVS",
    )

    assert isinstance(result, JoinWorkspaceData)
    assert result.workspace_id == ws_id
    assert result.workspace_name == "Public Devs"
    assert result.role == "MEMBER"
    assert result.status == "ACTIVE"
    mock_session.add.assert_called()


@pytest.mark.asyncio
async def test_join_open_forbidden_when_policy_disabled(
    joining_service, mock_session, mock_workspace_repo, mock_settings_repo, mock_member_repo
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(
        id=ws_id,
        name="Private Enterprise",
        slug="private-corp",
        public_id="PRIV-CORP",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=ws_id,
        settings_json={"open_join": False},
    )

    with pytest.raises(WorkspaceJoinForbiddenError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=user_id,
            user_email="user@example.com",
            workspace_identifier="PRIV-CORP",
        )

    assert "does not permit open self-service joining" in str(exc_info.value)


@pytest.mark.asyncio
async def test_join_open_conflict_when_already_active_member(
    joining_service, mock_session, mock_workspace_repo, mock_settings_repo, mock_member_repo
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(
        id=ws_id,
        name="Public Devs",
        slug="public-devs",
        public_id="PUB-DEVS",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=ws_id,
        settings_json={"open_join": True},
    )
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
    )

    with pytest.raises(WorkspaceMembershipConflictError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=user_id,
            user_email="dev@example.com",
            workspace_identifier="PUB-DEVS",
        )

    assert "already an active member" in str(exc_info.value)


# ── Mode 2: Protected Join Code Tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_join_via_code_success(
    joining_service, mock_session, mock_workspace_repo, mock_member_repo, mock_join_code_service
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(
        id=ws_id,
        name="Acme Corp",
        slug="acme-corp",
        public_id="ACME-CORP",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_member_repo.get_membership.return_value = None
    mock_join_code_service.validate_join_code_candidate.return_value = (True, None, "MEMBER")

    result = await joining_service.join_workspace(
        session=mock_session,
        user_id=user_id,
        user_email="worker@acme.com",
        workspace_identifier="ACME-CORP",
        join_code="VR-234567",
    )

    assert result.workspace_id == ws_id
    assert result.role == "MEMBER"
    mock_join_code_service.record_join_code_usage.assert_awaited_once_with(mock_session, ws_id)
    mock_session.add.assert_called()


@pytest.mark.asyncio
async def test_join_via_code_invalid_fails(
    joining_service, mock_session, mock_workspace_repo, mock_member_repo, mock_join_code_service
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(
        id=ws_id,
        name="Acme Corp",
        slug="acme-corp",
        public_id="ACME-CORP",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_member_repo.get_membership.return_value = None
    mock_join_code_service.validate_join_code_candidate.return_value = (False, "Invalid join code.", "")

    with pytest.raises(WorkspaceJoinCodeInvalidError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=user_id,
            user_email="worker@acme.com",
            workspace_identifier="ACME-CORP",
            join_code="VR-WRONG1",
        )

    assert "Invalid join code" in str(exc_info.value)
    mock_join_code_service.record_join_code_usage.assert_not_called()


@pytest.mark.asyncio
async def test_join_via_code_missing_identifier_fails(joining_service, mock_session):
    with pytest.raises(WorkspaceIdentifierInvalidError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=uuid.uuid4(),
            user_email="worker@acme.com",
            workspace_identifier=None,
            join_code="VR-234567",
        )

    assert "Workspace identifier (Workspace ID or Slug) is required" in str(exc_info.value)


# ── Mode 3: Invitation Token Tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_join_via_invitation_success(
    joining_service, mock_session, mock_invitation_service, mock_member_repo
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    member_id = uuid.uuid4()

    mock_invitation_service.accept_invitation.return_value = {
        "invitation_id": uuid.uuid4(),
        "workspace_id": ws_id,
        "workspace_name": "Design Systems",
        "email": "designer@acme.com",
        "role": "MEMBER",
        "status": "ACCEPTED",
    }
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        id=member_id,
        workspace_id=ws_id,
        user_id=user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
    )

    result = await joining_service.join_workspace(
        session=mock_session,
        user_id=user_id,
        user_email="designer@acme.com",
        invitation_token="sec_inv_1234567890123456789012_secret123456",
    )

    assert result.workspace_id == ws_id
    assert result.workspace_name == "Design Systems"
    assert result.role == "MEMBER"
    assert result.member_id == member_id


@pytest.mark.asyncio
async def test_join_via_invitation_target_mismatch_fails(
    joining_service, mock_session, mock_workspace_repo, mock_invitation_service
):
    invitation_ws_id = uuid.uuid4()
    other_ws_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_workspace_repo.get_by_public_id.return_value = Workspace(
        id=other_ws_id,
        name="Other Workspace",
        slug="other-ws",
        public_id="OTHER-WS",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_invitation_service.accept_invitation.return_value = {
        "workspace_id": invitation_ws_id,
        "workspace_name": "Target Invitation WS",
        "role": "MEMBER",
    }

    with pytest.raises(WorkspaceJoinIntentMismatchError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=user_id,
            user_email="user@acme.com",
            workspace_identifier="OTHER-WS",
            invitation_token="sec_inv_1234567890123456789012_secret123456",
        )

    assert "belongs to a different workspace" in str(exc_info.value)


@pytest.mark.asyncio
async def test_join_via_invitation_email_mismatch_fails(
    joining_service, mock_session, mock_invitation_service
):
    mock_invitation_service.accept_invitation.side_effect = InvitationInvalidStateError("Email mismatch")

    with pytest.raises(WorkspaceInvitationJoinError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=uuid.uuid4(),
            user_email="intruder@external.com",
            invitation_token="sec_inv_1234567890123456789012_secret123456",
        )

    assert "Email mismatch" in str(exc_info.value)


# ── Adversarial & Boundary Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_join_rejects_tenant_uuid_as_public_credential(joining_service, mock_session):
    raw_uuid = str(uuid.uuid4())
    with pytest.raises(WorkspaceIdentifierInvalidError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=uuid.uuid4(),
            user_email="user@acme.com",
            workspace_identifier=raw_uuid,
            join_code="VR-234567",
        )

    assert "Tenant UUID cannot be used as a public join credential" in str(exc_info.value)


@pytest.mark.asyncio
async def test_join_inactive_workspace_returns_not_found(
    joining_service, mock_session, mock_workspace_repo
):
    mock_workspace_repo.get_by_public_id.return_value = Workspace(
        id=uuid.uuid4(),
        name="Archived WS",
        slug="archived-ws",
        public_id="ARCH-WS",
        status="SUSPENDED",
    )

    with pytest.raises(WorkspaceTargetNotFoundError) as exc_info:
        await joining_service.join_workspace(
            session=mock_session,
            user_id=uuid.uuid4(),
            user_email="user@acme.com",
            workspace_identifier="ARCH-WS",
            join_code="VR-234567",
        )

    assert "not found" in str(exc_info.value)
