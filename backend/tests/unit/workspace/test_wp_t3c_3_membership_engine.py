"""Unit tests for WP-T3C-3: Workspace Membership Management Service Engine.

Verifies:
1. Workspace row locking via get_by_id_for_update in all mutations.
2. Target user lifecycle validation rejecting inactive/deactivated users.
3. Last owner protection using count_non_deleted_owners.
4. Decision D-3.5 bulk operation semantics:
   - Ascending deterministic sorting of member IDs
   - Independent atomic transactions per member with rollback isolation
   - Partial success preservation
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.services.workspace.membership_service import (
    MembershipConflictError,
    MembershipError,
    MembershipInvalidStateError,
    MembershipNotFoundError,
    MembershipUnauthorizedError,
    WorkspaceMembershipService,
)


@pytest.fixture
def workspace_id():
    return uuid.uuid4()


@pytest.fixture
def actor_id():
    return uuid.uuid4()


@pytest.fixture
def mock_workspace(workspace_id):
    ws = Workspace(name="Test Workspace")
    ws.id = workspace_id
    ws.status = WorkspaceStatus.ACTIVE.value
    return ws


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_update_member_role_acquires_workspace_row_lock(workspace_id, actor_id, mock_workspace, mock_session):
    workspace_repo = MagicMock()
    workspace_repo.get_by_id_for_update = AsyncMock(return_value=mock_workspace)
    workspace_repo.get_by_id = AsyncMock(return_value=mock_workspace)

    member_repo = MagicMock()
    actor = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )
    actor.id = actor_id

    target_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    target = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=target_user_id,
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.ACTIVE.value,
    )
    target.id = target_id
    target.user = MagicMock(is_active=True, is_deleted=False)

    member_repo.get_membership = AsyncMock(return_value=actor)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target)

    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)
    result = await service.update_member_role(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=actor_id,
        member_id=target_id,
        new_role=WorkspaceRole.ADMIN.value,
    )

    workspace_repo.get_by_id_for_update.assert_awaited_once_with(workspace_id)
    assert result.role == WorkspaceRole.ADMIN.value


@pytest.mark.asyncio
async def test_target_user_inactive_or_deleted_rejected(workspace_id, actor_id, mock_workspace, mock_session):
    workspace_repo = MagicMock()
    workspace_repo.get_by_id_for_update = AsyncMock(return_value=mock_workspace)

    member_repo = MagicMock()
    actor = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )
    actor.id = actor_id

    target_id = uuid.uuid4()
    target = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=uuid.uuid4(),
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.ACTIVE.value,
    )
    target.id = target_id
    target.user = MagicMock(is_active=False, is_deleted=False)

    member_repo.get_membership = AsyncMock(return_value=actor)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target)

    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    with pytest.raises(MembershipConflictError, match="Target user is inactive or deactivated."):
        await service.update_member_role(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=actor_id,
            member_id=target_id,
            new_role=WorkspaceRole.ADMIN.value,
        )


@pytest.mark.asyncio
async def test_last_owner_protection_with_non_deleted_owners_count(workspace_id, mock_workspace, mock_session):
    workspace_repo = MagicMock()
    workspace_repo.get_by_id_for_update = AsyncMock(return_value=mock_workspace)

    member_repo = MagicMock()
    owner_id = uuid.uuid4()
    owner_user_id = uuid.uuid4()
    owner = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=owner_user_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )
    owner.id = owner_id

    actor_id = uuid.uuid4()
    actor = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )
    actor.id = actor_id

    member_repo.get_membership = AsyncMock(return_value=actor)
    member_repo.get_by_id_for_update = AsyncMock(return_value=owner)
    member_repo.count_non_deleted_owners = AsyncMock(return_value=1)

    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    # 1. Suspend last owner rejected
    with pytest.raises(MembershipConflictError, match="Cannot suspend the last remaining OWNER"):
        await service.suspend_member(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=actor_id,
            member_id=owner_id,
        )

    # 2. Remove last owner rejected
    with pytest.raises(MembershipConflictError, match="Cannot remove the last remaining OWNER"):
        await service.remove_member(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=actor_id,
            member_id=owner_id,
        )


@pytest.mark.asyncio
async def test_d35_bulk_operations_sorting_and_partial_success(workspace_id, actor_id, mock_workspace, mock_session):
    """
    Verifies D-3.5:
    - Deduplicates and deterministically sorts member IDs
    - Item 2 fails, but Item 1 and Item 3 succeed (partial success preserved)
    - Session rollback occurs on failure without poisoning subsequent items
    """
    workspace_repo = MagicMock()
    workspace_repo.get_by_id_for_update = AsyncMock(return_value=mock_workspace)

    member_repo = MagicMock()
    actor = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )
    actor.id = actor_id
    member_repo.get_membership = AsyncMock(return_value=actor)

    id_a = uuid.UUID("11111111-1111-1111-1111-111111111111")
    id_b = uuid.UUID("22222222-2222-2222-2222-222222222222")
    id_c = uuid.UUID("33333333-3333-3333-3333-333333333333")

    # Pass in reverse/mixed order with duplicates
    input_ids = [id_c, id_a, id_b, id_a, id_c]

    processed_order = []

    async def mock_suspend(session, ws_id, act_id, mid):
        processed_order.append(mid)
        if mid == id_b:
            raise MembershipConflictError("Simulated failure for member B")
        member = WorkspaceMember(workspace_id=ws_id, user_id=uuid.uuid4(), role=WorkspaceRole.MEMBER.value)
        member.id = mid
        return member

    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)
    service.suspend_member = mock_suspend

    result = await service.bulk_update_members(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=actor_id,
        member_ids=input_ids,
        action="suspend",
    )

    # 1. Deterministic sorting: ascending order [id_a, id_b, id_c]
    assert processed_order == [id_a, id_b, id_c]

    # 2. Result structure and partial success
    assert result["total_requested"] == 3
    assert result["success_count"] == 2
    assert result["failure_count"] == 1

    results = result["results"]
    assert results[0]["member_id"] == str(id_a)
    assert results[0]["status"] == "success"

    assert results[1]["member_id"] == str(id_b)
    assert results[1]["status"] == "error"
    assert "Simulated failure" in results[1]["message"]

    assert results[2]["member_id"] == str(id_c)
    assert results[2]["status"] == "success"

    # 3. Rollback called for failed item B
    mock_session.rollback.assert_awaited()
