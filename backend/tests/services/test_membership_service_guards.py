"""Automated tests for MembershipService security guards (self-suspend prevention, role hierarchy)."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.services.workspace.membership_service import (
    MembershipConflictError,
    MembershipUnauthorizedError,
    WorkspaceMembershipService,
)


@pytest.mark.asyncio
async def test_self_suspend_prevented():
    """Verify an admin or owner cannot suspend their own membership."""
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    member_id = uuid.uuid4()

    mock_member_repo = AsyncMock()
    actor_member = WorkspaceMember(
        id=member_id,
        workspace_id=workspace_id,
        user_id=user_id,
        role=WorkspaceRole.ADMIN.value,
        status=MemberStatus.ACTIVE.value,
    )
    mock_member_repo.get_membership.return_value = actor_member
    mock_member_repo.get_by_id_for_update.return_value = actor_member

    mock_workspace_repo = AsyncMock()
    mock_workspace = Workspace(
        id=workspace_id,
        name="Security Lab",
        slug="security-lab",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    service = WorkspaceMembershipService(
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )

    mock_session = AsyncMock()

    with pytest.raises(MembershipUnauthorizedError) as exc_info:
        await service.suspend_member(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=user_id,
            member_id=member_id,
        )

    assert "You cannot suspend your own account" in str(exc_info.value)


@pytest.mark.asyncio
async def test_admin_cannot_suspend_owner():
    """Verify an admin cannot suspend a workspace owner."""
    workspace_id = uuid.uuid4()
    admin_user_id = uuid.uuid4()
    admin_member_id = uuid.uuid4()

    owner_user_id = uuid.uuid4()
    owner_member_id = uuid.uuid4()

    admin_member = WorkspaceMember(
        id=admin_member_id,
        workspace_id=workspace_id,
        user_id=admin_user_id,
        role=WorkspaceRole.ADMIN.value,
        status=MemberStatus.ACTIVE.value,
    )
    owner_member = WorkspaceMember(
        id=owner_member_id,
        workspace_id=workspace_id,
        user_id=owner_user_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )

    mock_member_repo = AsyncMock()
    mock_member_repo.get_membership.return_value = admin_member
    mock_member_repo.get_by_id_for_update.return_value = owner_member

    mock_workspace_repo = AsyncMock()
    mock_workspace = Workspace(
        id=workspace_id,
        name="Security Lab",
        slug="security-lab",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    service = WorkspaceMembershipService(
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )

    mock_session = AsyncMock()

    with pytest.raises(MembershipUnauthorizedError) as exc_info:
        await service.suspend_member(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=admin_user_id,
            member_id=owner_member_id,
        )

    assert "ADMIN cannot suspend an OWNER" in str(exc_info.value)


@pytest.mark.asyncio
async def test_admin_can_suspend_regular_member():
    """Verify an admin can successfully suspend an active member."""
    workspace_id = uuid.uuid4()
    admin_user_id = uuid.uuid4()
    admin_member_id = uuid.uuid4()

    member_user_id = uuid.uuid4()
    target_member_id = uuid.uuid4()

    admin_member = WorkspaceMember(
        id=admin_member_id,
        workspace_id=workspace_id,
        user_id=admin_user_id,
        role=WorkspaceRole.ADMIN.value,
        status=MemberStatus.ACTIVE.value,
    )
    target_member = WorkspaceMember(
        id=target_member_id,
        workspace_id=workspace_id,
        user_id=member_user_id,
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.ACTIVE.value,
        version=1,
    )

    mock_member_repo = AsyncMock()
    mock_member_repo.get_membership.return_value = admin_member
    mock_member_repo.get_by_id_for_update.return_value = target_member

    mock_workspace_repo = AsyncMock()
    mock_workspace = Workspace(
        id=workspace_id,
        name="Security Lab",
        slug="security-lab",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    service = WorkspaceMembershipService(
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    suspended = await service.suspend_member(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=admin_user_id,
        member_id=target_member_id,
    )

    assert suspended.status == MemberStatus.SUSPENDED.value
    mock_session.commit.assert_called_once()
