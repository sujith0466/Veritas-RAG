"""Unit tests for WS-B2: Member Management."""

import datetime
from datetime import UTC
import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.api.v1.schemas.workspace_member import (
    WorkspaceMemberData,
    WorkspaceMemberListResponse,
    WorkspaceMemberResponse,
    WorkspaceMemberUserData,
)
from backend.models.entities.user import User
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.services.workspace.membership_service import (
    MembershipNotFoundError,
    MembershipUnauthorizedError,
    WorkspaceMembershipService,
)


@pytest.mark.asyncio
async def test_list_members_requires_active_workspace_membership():
    """Verify non-member or suspended member cannot list workspace members."""
    ws_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    # 1. Non-member actor
    member_repo.get_membership = AsyncMock(return_value=None)
    with pytest.raises(MembershipUnauthorizedError, match="Actor is not a member of this workspace"):
        await service.list_members(workspace_id=ws_id, actor_id=actor_id)

    # 2. Suspended member actor
    suspended_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=actor_id,
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.SUSPENDED.value,
    )
    member_repo.get_membership = AsyncMock(return_value=suspended_member)
    with pytest.raises(MembershipUnauthorizedError, match="Suspended members cannot perform workspace operations"):
        await service.list_members(workspace_id=ws_id, actor_id=actor_id)


@pytest.mark.asyncio
async def test_list_members_success_with_filtering_and_pagination():
    """Verify listing members returns items, total count, and next_cursor."""
    ws_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    active_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=actor_id,
        role=WorkspaceRole.ADMIN.value,
        status=MemberStatus.ACTIVE.value,
    )
    member_repo.get_membership = AsyncMock(return_value=active_member)

    sample_user = User(
        id=actor_id,
        email="test@veritas.rag",
        username="testuser",
        display_name="Test User",
        avatar_url="https://veritas.rag/avatar.png",
        is_active=True,
    )
    active_member.user = sample_user
    active_member.created_at = datetime.datetime.now(UTC)
    active_member.updated_at = datetime.datetime.now(UTC)
    active_member.version = 1

    member_repo.list_members = AsyncMock(return_value=([active_member], 1, None))

    items, total, next_cursor = await service.list_members(
        workspace_id=ws_id,
        actor_id=actor_id,
        search="test",
        role="ADMIN",
        status="ACTIVE",
        skip=0,
        limit=20,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].id == active_member.id
    assert next_cursor is None

    # Test DTO validation
    dto = WorkspaceMemberData.model_validate(items[0])
    assert dto.user is not None
    assert dto.user.email == "test@veritas.rag"
    assert dto.user.display_name == "Test User"
    assert dto.user.avatar_url == "https://veritas.rag/avatar.png"
    assert dto.role == "ADMIN"
    assert dto.status == "ACTIVE"


@pytest.mark.asyncio
async def test_get_member_tenant_scoping():
    """Verify get_member ensures member belongs strictly to requested workspace."""
    ws_id = uuid.uuid4()
    other_ws_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_member_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    service = WorkspaceMembershipService(member_repo=member_repo, workspace_repo=workspace_repo)

    active_actor = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=actor_id,
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.ACTIVE.value,
    )
    member_repo.get_membership = AsyncMock(return_value=active_actor)

    # Target member belongs to another workspace -> repo returns None for (target_member_id, ws_id)
    member_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(MembershipNotFoundError, match="Member not found in this workspace"):
        await service.get_member(workspace_id=ws_id, member_id=target_member_id, actor_id=actor_id)
