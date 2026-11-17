"""Automated tests for WorkspaceAccessRequestService lifecycle, transactional approval, and security."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_access_request import (
    AccessRequestStatus,
    AccessRequestType,
    WorkspaceAccessRequest,
)
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.services.workspace.access_request_service import (
    AccessRequestConflictError,
    AccessRequestInvalidStateError,
    AccessRequestService,
    AccessRequestUnauthorizedError,
)


@pytest.mark.asyncio
async def test_create_role_elevation_request_success():
    """Verify active legacy VIEWER member can submit a role elevation request to MEMBER."""
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_access_repo = AsyncMock()
    mock_access_repo.get_active_pending.return_value = None

    mock_member_repo = AsyncMock()
    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=user_id,
        role=WorkspaceRole.VIEWER.value,
        status=MemberStatus.ACTIVE.value,
    )
    mock_member_repo.get_membership.return_value = member

    mock_workspace_repo = AsyncMock()
    mock_workspace = Workspace(
        id=workspace_id,
        name="Engineering",
        slug="engineering",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    service = AccessRequestService(
        access_repo=mock_access_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    req = await service.create_request(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=user_id,
        request_type=AccessRequestType.ROLE_ELEVATION.value,
        requested_role=WorkspaceRole.MEMBER.value,
        reason="Need member access for collaboration",
    )

    assert req.request_type == AccessRequestType.ROLE_ELEVATION.value
    assert req.requested_role == WorkspaceRole.MEMBER.value
    assert req.current_role == WorkspaceRole.VIEWER.value
    assert req.status == AccessRequestStatus.PENDING.value
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_role_elevation_duplicate_pending_conflict():
    """Verify duplicate pending request raises AccessRequestConflictError."""
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    existing_pending = WorkspaceAccessRequest(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=user_id,
        request_type=AccessRequestType.ROLE_ELEVATION.value,
        requested_role=WorkspaceRole.MEMBER.value,
        status=AccessRequestStatus.PENDING.value,
    )

    mock_access_repo = AsyncMock()
    mock_access_repo.get_active_pending.return_value = existing_pending

    mock_member_repo = AsyncMock()
    mock_workspace_repo = AsyncMock()
    mock_workspace = Workspace(
        id=workspace_id,
        name="Engineering",
        slug="engineering",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    service = AccessRequestService(
        access_repo=mock_access_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )

    mock_session = AsyncMock()

    with pytest.raises(AccessRequestConflictError) as exc_info:
        await service.create_request(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=user_id,
            request_type=AccessRequestType.ROLE_ELEVATION.value,
            requested_role=WorkspaceRole.MEMBER.value,
        )

    assert "already have an active pending role elevation request" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_join_approval_request_prospective_user():
    """Verify prospective non-member user can submit JOIN_APPROVAL request."""
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_access_repo = AsyncMock()
    mock_access_repo.get_active_pending.return_value = None

    mock_member_repo = AsyncMock()
    mock_member_repo.get_membership.return_value = None  # Not a member

    mock_workspace_repo = AsyncMock()
    mock_workspace = Workspace(
        id=workspace_id,
        name="Engineering",
        slug="engineering",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    service = AccessRequestService(
        access_repo=mock_access_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    req = await service.create_request(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=user_id,
        request_type=AccessRequestType.JOIN_APPROVAL.value,
        requested_role=WorkspaceRole.MEMBER.value,
        reason="Joining via secured team join code",
    )

    assert req.request_type == AccessRequestType.JOIN_APPROVAL.value
    assert req.current_role is None
    assert req.status == AccessRequestStatus.PENDING.value
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_approve_role_elevation_request_promotes_member():
    """Verify admin approval atomically elevates member role to requested role."""
    workspace_id = uuid.uuid4()
    admin_user_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    request_id = uuid.uuid4()

    admin_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=admin_user_id,
        role=WorkspaceRole.ADMIN.value,
        status=MemberStatus.ACTIVE.value,
    )
    target_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=target_user_id,
        role=WorkspaceRole.VIEWER.value,
        status=MemberStatus.ACTIVE.value,
        version=1,
    )
    access_request = WorkspaceAccessRequest(
        id=request_id,
        workspace_id=workspace_id,
        user_id=target_user_id,
        request_type=AccessRequestType.ROLE_ELEVATION.value,
        current_role=WorkspaceRole.VIEWER.value,
        requested_role=WorkspaceRole.MEMBER.value,
        status=AccessRequestStatus.PENDING.value,
    )

    mock_access_repo = AsyncMock()
    mock_access_repo.get_by_id_for_update.return_value = access_request

    mock_member_repo = AsyncMock()
    mock_member_repo.get_membership.return_value = admin_member
    mock_member_repo.get_membership_for_update.return_value = target_member

    mock_workspace_repo = AsyncMock()
    mock_workspace = Workspace(
        id=workspace_id,
        name="Engineering",
        slug="engineering",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    service = AccessRequestService(
        access_repo=mock_access_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    approved_req = await service.approve_request(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=admin_user_id,
        request_id=request_id,
    )

    assert approved_req.status == AccessRequestStatus.APPROVED.value
    assert approved_req.reviewed_by_id == admin_user_id
    assert target_member.role == WorkspaceRole.MEMBER.value
    assert target_member.version == 2
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_approve_request_stale_role_conflict():
    """Verify approval aborts if member role changed after request creation."""
    workspace_id = uuid.uuid4()
    admin_user_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    request_id = uuid.uuid4()

    admin_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=admin_user_id,
        role=WorkspaceRole.ADMIN.value,
        status=MemberStatus.ACTIVE.value,
    )
    # Target member has already been promoted to ADMIN or altered
    target_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=target_user_id,
        role=WorkspaceRole.ADMIN.value,
        status=MemberStatus.ACTIVE.value,
        version=1,
    )
    access_request = WorkspaceAccessRequest(
        id=request_id,
        workspace_id=workspace_id,
        user_id=target_user_id,
        request_type=AccessRequestType.ROLE_ELEVATION.value,
        current_role=WorkspaceRole.VIEWER.value,  # was VIEWER when requested
        requested_role=WorkspaceRole.MEMBER.value,
        status=AccessRequestStatus.PENDING.value,
    )

    mock_access_repo = AsyncMock()
    mock_access_repo.get_by_id_for_update.return_value = access_request

    mock_member_repo = AsyncMock()
    mock_member_repo.get_membership.return_value = admin_member
    mock_member_repo.get_membership_for_update.return_value = target_member

    mock_workspace_repo = AsyncMock()
    mock_workspace = Workspace(
        id=workspace_id,
        name="Engineering",
        slug="engineering",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    service = AccessRequestService(
        access_repo=mock_access_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )

    mock_session = AsyncMock()

    with pytest.raises(AccessRequestConflictError) as exc_info:
        await service.approve_request(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=admin_user_id,
            request_id=request_id,
        )

    assert "Member role has changed since request submission" in str(exc_info.value)


@pytest.mark.asyncio
async def test_reject_request_records_reason():
    """Verify admin rejection updates status to REJECTED and records reason."""
    workspace_id = uuid.uuid4()
    admin_user_id = uuid.uuid4()
    request_id = uuid.uuid4()

    admin_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=admin_user_id,
        role=WorkspaceRole.ADMIN.value,
        status=MemberStatus.ACTIVE.value,
    )
    access_request = WorkspaceAccessRequest(
        id=request_id,
        workspace_id=workspace_id,
        user_id=uuid.uuid4(),
        request_type=AccessRequestType.ROLE_ELEVATION.value,
        current_role=WorkspaceRole.VIEWER.value,
        requested_role=WorkspaceRole.MEMBER.value,
        status=AccessRequestStatus.PENDING.value,
    )

    mock_access_repo = AsyncMock()
    mock_access_repo.get_by_id_for_update.return_value = access_request

    mock_member_repo = AsyncMock()
    mock_member_repo.get_membership.return_value = admin_member

    mock_workspace_repo = AsyncMock()
    mock_workspace = Workspace(
        id=workspace_id,
        name="Engineering",
        slug="engineering",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    service = AccessRequestService(
        access_repo=mock_access_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    rejected_req = await service.reject_request(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=admin_user_id,
        request_id=request_id,
        rejection_reason="Admin seats are currently capped",
    )

    assert rejected_req.status == AccessRequestStatus.REJECTED.value
    assert rejected_req.rejection_reason == "Admin seats are currently capped"
    assert rejected_req.reviewed_by_id == admin_user_id
    mock_session.commit.assert_called_once()


# ── T-60: Access Request Contract — MEMBER-Only Enforcement Tests ─────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prohibited_role",
    [
        WorkspaceRole.ADMIN.value,
        WorkspaceRole.VIEWER.value,
        WorkspaceRole.OWNER.value,
        "ARBITRARY_ROLE",
        "superadmin",
    ],
)
async def test_create_request_rejects_non_member_roles(prohibited_role: str):
    """T-60: Direct service invocation independently rejects non-MEMBER roles."""
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_workspace_repo = AsyncMock()
    mock_workspace = Workspace(
        id=workspace_id,
        name="Engineering",
        slug="engineering",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    service = AccessRequestService(
        access_repo=AsyncMock(),
        member_repo=AsyncMock(),
        workspace_repo=mock_workspace_repo,
    )

    mock_session = AsyncMock()

    with pytest.raises(AccessRequestInvalidStateError) as exc_info:
        await service.create_request(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=user_id,
            request_type=AccessRequestType.ROLE_ELEVATION.value,
            requested_role=prohibited_role,
        )

    assert "Only MEMBER requests are permitted" in str(exc_info.value)


@pytest.mark.asyncio
async def test_approve_request_rejects_non_member_role_before_mutation():
    """T-60: Approving a request with a non-MEMBER requested_role fails closed."""
    workspace_id = uuid.uuid4()
    admin_user_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    request_id = uuid.uuid4()

    admin_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=admin_user_id,
        role=WorkspaceRole.ADMIN.value,
        status=MemberStatus.ACTIVE.value,
    )
    access_request = WorkspaceAccessRequest(
        id=request_id,
        workspace_id=workspace_id,
        user_id=target_user_id,
        request_type=AccessRequestType.ROLE_ELEVATION.value,
        current_role=WorkspaceRole.VIEWER.value,
        requested_role="ADMIN",  # Prohibited role
        status=AccessRequestStatus.PENDING.value,
    )

    mock_access_repo = AsyncMock()
    mock_access_repo.get_by_id_for_update.return_value = access_request

    mock_member_repo = AsyncMock()
    mock_member_repo.get_membership.return_value = admin_member

    mock_workspace_repo = AsyncMock()
    mock_workspace = Workspace(
        id=workspace_id,
        name="Engineering",
        slug="engineering",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    service = AccessRequestService(
        access_repo=mock_access_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )

    mock_session = AsyncMock()

    with pytest.raises(AccessRequestInvalidStateError) as exc_info:
        await service.approve_request(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=admin_user_id,
            request_id=request_id,
        )

    assert "Cannot approve request with non-MEMBER role" in str(exc_info.value)
    mock_session.commit.assert_not_called()
