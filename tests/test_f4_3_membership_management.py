"""Tests for F4.3: Workspace Membership Management."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.services.workspace.membership_service import (
    MembershipConflictError,
    MembershipUnauthorizedError,
    WorkspaceMembershipService,
)


@pytest.fixture
def mock_membership_service():
    member_repo = MagicMock()
    workspace_repo = MagicMock()
    event_dispatcher = MagicMock()
    event_dispatcher.publish = AsyncMock()

    service = WorkspaceMembershipService(
        member_repo=member_repo,
        workspace_repo=workspace_repo,
        event_dispatcher=event_dispatcher,
    )
    return {
        "service": service,
        "member_repo": member_repo,
        "workspace_repo": workspace_repo,
        "event_dispatcher": event_dispatcher,
    }


@pytest.mark.asyncio
async def test_update_member_role_success(mock_membership_service):
    service = mock_membership_service["service"]
    member_repo = mock_membership_service["member_repo"]
    workspace_repo = mock_membership_service["workspace_repo"]

    session = AsyncMock()
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    actor_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=workspace_id, user_id=actor_id, role="OWNER", status="ACTIVE")
    member_repo.get_membership = AsyncMock(return_value=actor_member)

    target_member = WorkspaceMember(id=target_id, workspace_id=workspace_id, user_id=uuid.uuid4(), role="MEMBER", status="ACTIVE", version=1)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target_member)

    updated = await service.update_member_role(
        session=session,
        workspace_id=workspace_id,
        actor_id=actor_id,
        member_id=target_id,
        new_role="ADMIN",
    )

    assert updated.role == "ADMIN"
    assert updated.version == 2
    session.add.assert_called()
    session.flush.assert_called()
    session.commit.assert_called()


@pytest.mark.asyncio
async def test_last_owner_protection_on_role_demote(mock_membership_service):
    service = mock_membership_service["service"]
    member_repo = mock_membership_service["member_repo"]
    workspace_repo = mock_membership_service["workspace_repo"]

    session = AsyncMock()
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    actor_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=workspace_id, user_id=actor_id, role="OWNER", status="ACTIVE")
    member_repo.get_membership = AsyncMock(return_value=actor_member)

    target_member = WorkspaceMember(id=target_id, workspace_id=workspace_id, user_id=actor_id, role="OWNER", status="ACTIVE", version=1)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target_member)
    member_repo.count_active_owners = AsyncMock(return_value=1)

    with pytest.raises(MembershipConflictError, match="Cannot demote the last remaining OWNER"):
        await service.update_member_role(
            session=session,
            workspace_id=workspace_id,
            actor_id=actor_id,
            member_id=target_id,
            new_role="ADMIN",
        )


@pytest.mark.asyncio
async def test_admin_cannot_promote_to_owner(mock_membership_service):
    service = mock_membership_service["service"]
    member_repo = mock_membership_service["member_repo"]
    workspace_repo = mock_membership_service["workspace_repo"]

    session = AsyncMock()
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    actor_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=workspace_id, user_id=actor_id, role="ADMIN", status="ACTIVE")
    member_repo.get_membership = AsyncMock(return_value=actor_member)

    with pytest.raises(MembershipUnauthorizedError, match="ADMIN cannot promote a member to OWNER"):
        await service.update_member_role(
            session=session,
            workspace_id=workspace_id,
            actor_id=actor_id,
            member_id=target_id,
            new_role="OWNER",
        )


@pytest.mark.asyncio
async def test_suspend_and_restore_member(mock_membership_service):
    service = mock_membership_service["service"]
    member_repo = mock_membership_service["member_repo"]
    workspace_repo = mock_membership_service["workspace_repo"]

    session = AsyncMock()
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    actor_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=workspace_id, user_id=actor_id, role="OWNER", status="ACTIVE")
    member_repo.get_membership = AsyncMock(return_value=actor_member)

    target_member = WorkspaceMember(id=target_id, workspace_id=workspace_id, user_id=uuid.uuid4(), role="MEMBER", status="ACTIVE", version=1)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target_member)

    # Suspend
    suspended = await service.suspend_member(session, workspace_id, actor_id, target_id)
    assert suspended.status == MemberStatus.SUSPENDED.value

    # Restore
    restored = await service.restore_member(session, workspace_id, actor_id, target_id)
    assert restored.status == MemberStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_remove_member_success(mock_membership_service):
    service = mock_membership_service["service"]
    member_repo = mock_membership_service["member_repo"]
    workspace_repo = mock_membership_service["workspace_repo"]

    session = AsyncMock()
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    actor_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=workspace_id, user_id=actor_id, role="OWNER", status="ACTIVE")
    member_repo.get_membership = AsyncMock(return_value=actor_member)

    target_member = WorkspaceMember(id=target_id, workspace_id=workspace_id, user_id=uuid.uuid4(), role="MEMBER", status="ACTIVE", is_deleted=False, version=1)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target_member)

    removed = await service.remove_member(session, workspace_id, actor_id, target_id)
    assert removed.is_deleted is True
