"""Unit tests for WS-B3: Role Promotion / Demotion."""

import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.services.workspace.events import WorkspaceMemberRoleUpdatedEvent
from backend.services.workspace.membership_service import (
    MembershipConflictError,
    MembershipNotFoundError,
    MembershipUnauthorizedError,
    WorkspaceMembershipService,
)


@pytest.mark.asyncio
async def test_member_role_cannot_modify_any_roles():
    """Verify that a MEMBER actor cannot modify any roles."""
    ws_id = uuid.uuid4()
    member_actor_id = uuid.uuid4()
    target_member_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    member_actor = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=member_actor_id,
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.ACTIVE.value,
    )
    member_repo.get_membership = AsyncMock(return_value=member_actor)

    session = AsyncMock()

    with pytest.raises(MembershipUnauthorizedError, match="Only OWNER or ADMIN can modify member roles"):
        await service.update_member_role(
            session=session,
            workspace_id=ws_id,
            actor_id=member_actor_id,
            member_id=target_member_id,
            new_role="VIEWER",
        )


@pytest.mark.asyncio
async def test_owner_can_promote_member_to_admin_with_pessimistic_lock_and_audit():
    """Verify OWNER can promote MEMBER to ADMIN, acquiring row lock, creating audit log and event."""
    ws_id = uuid.uuid4()
    owner_actor_id = uuid.uuid4()
    target_member_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    event_dispatcher = MagicMock()
    event_dispatcher.publish = AsyncMock()

    service = WorkspaceMembershipService(
        member_repo=member_repo,
        workspace_repo=workspace_repo,
        event_dispatcher=event_dispatcher,
    )

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    owner_actor = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=owner_actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )
    target_member = WorkspaceMember(
        id=target_member_id,
        workspace_id=ws_id,
        user_id=target_user_id,
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.ACTIVE.value,
        version=1,
    )

    member_repo.get_membership = AsyncMock(return_value=owner_actor)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target_member)

    session = AsyncMock()

    updated = await service.update_member_role(
        session=session,
        workspace_id=ws_id,
        actor_id=owner_actor_id,
        member_id=target_member_id,
        new_role="ADMIN",
    )

    # 1. Pessimistic lock was called
    member_repo.get_by_id_for_update.assert_awaited_once_with(target_member_id, ws_id)

    # 2. Target member role updated and version incremented
    assert updated.role == WorkspaceRole.ADMIN.value
    assert updated.version == 2

    # 3. Session changes added and committed
    assert session.add.call_count >= 2  # member and audit log
    session.commit.assert_awaited_once()

    # 4. Domain event published
    event_dispatcher.publish.assert_awaited_once()
    event = event_dispatcher.publish.call_args[0][0]
    assert isinstance(event, WorkspaceMemberRoleUpdatedEvent)
    assert event.workspace_id == str(ws_id)
    assert event.old_role == "MEMBER"
    assert event.new_role == "ADMIN"


@pytest.mark.asyncio
async def test_update_member_role_dry_run_does_not_commit():
    """Verify dry_run=True returns prospective role change without database mutations."""
    ws_id = uuid.uuid4()
    owner_actor_id = uuid.uuid4()
    target_member_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    owner_actor = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=owner_actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )
    target_member = WorkspaceMember(
        id=target_member_id,
        workspace_id=ws_id,
        user_id=target_user_id,
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.ACTIVE.value,
        version=1,
    )

    member_repo.get_membership = AsyncMock(return_value=owner_actor)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target_member)

    session = AsyncMock()

    prospective = await service.update_member_role(
        session=session,
        workspace_id=ws_id,
        actor_id=owner_actor_id,
        member_id=target_member_id,
        new_role="VIEWER",
        dry_run=True,
    )

    assert prospective.role == "VIEWER"
    # Target member in repo is untouched
    assert target_member.role == "MEMBER"
    # DB session was NOT committed
    session.commit.assert_not_awaited()
    session.add.assert_not_called()
