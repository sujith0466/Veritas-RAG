"""Tests for F4.2: Invitation Acceptance Flow."""

import datetime
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.core.auth.context import UserContext
from backend.core.permissions.rbac import Role
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_invitation import InvitationStatus, WorkspaceInvitation
from backend.models.entities.workspace_member import WorkspaceMember
from backend.services.workspace.invitation_service import (
    InvitationConflictError,
    InvitationInvalidStateError,
    InvitationUnauthorizedError,
    WorkspaceInvitationService,
    generate_invitation_token,
)


@pytest.fixture
def mock_repos():
    invitation_repo = MagicMock()
    member_repo = MagicMock()
    workspace_repo = MagicMock()
    settings_repo = MagicMock()
    email_provider = MagicMock()
    event_dispatcher = MagicMock()
    event_dispatcher.publish = AsyncMock()

    service = WorkspaceInvitationService(
        invitation_repo=invitation_repo,
        member_repo=member_repo,
        workspace_repo=workspace_repo,
        settings_repo=settings_repo,
        email_provider=email_provider,
        event_dispatcher=event_dispatcher,
    )
    return {
        "service": service,
        "invitation_repo": invitation_repo,
        "member_repo": member_repo,
        "workspace_repo": workspace_repo,
        "event_dispatcher": event_dispatcher,
    }


@pytest.mark.asyncio
async def test_accept_invitation_success(mock_repos):
    service = mock_repos["service"]
    invitation_repo = mock_repos["invitation_repo"]
    member_repo = mock_repos["member_repo"]
    workspace_repo = mock_repos["workspace_repo"]

    session = AsyncMock()
    raw_token, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    inviter_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, name="Test Corp", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    expires_at = datetime.datetime.now(UTC) + datetime.timedelta(days=3)
    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email="testuser@example.com",
        role="MEMBER",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        invited_by_user_id=inviter_id,
        expires_at=expires_at,
        version=1,
    )
    invitation_repo.get_by_token_hash_for_update = AsyncMock(return_value=invitation)
    member_repo.get_membership = AsyncMock(return_value=None)

    user_context = UserContext(
        id=user_id,
        supabase_id=str(uuid.uuid4()),
        email="testuser@example.com",
        role=Role.MEMBER,
    )

    result = await service.accept_invitation(session, raw_token, user_context)

    assert result["success"] is True
    assert result["workspace_id"] == workspace_id
    assert result["role"] == "MEMBER"
    assert invitation.status == InvitationStatus.ACCEPTED.value
    session.add.assert_called()
    session.flush.assert_called()
    session.commit.assert_called()


@pytest.mark.asyncio
async def test_accept_invitation_email_mismatch(mock_repos):
    service = mock_repos["service"]
    invitation_repo = mock_repos["invitation_repo"]
    workspace_repo = mock_repos["workspace_repo"]

    session = AsyncMock()
    raw_token, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, name="Test Corp", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email="target@example.com",
        role="MEMBER",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.datetime.now(UTC) + datetime.timedelta(days=3),
        version=1,
    )
    invitation_repo.get_by_token_hash_for_update = AsyncMock(return_value=invitation)

    user_context = UserContext(
        id=user_id,
        supabase_id=str(uuid.uuid4()),
        email="attacker@example.com",
        role=Role.MEMBER,
    )

    with pytest.raises(InvitationUnauthorizedError, match="Logged in user email does not match"):
        await service.accept_invitation(session, raw_token, user_context)


@pytest.mark.asyncio
async def test_accept_invitation_expired(mock_repos):
    service = mock_repos["service"]
    invitation_repo = mock_repos["invitation_repo"]
    workspace_repo = mock_repos["workspace_repo"]

    session = AsyncMock()
    raw_token, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, name="Test Corp", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    expired_at = datetime.datetime.now(UTC) - datetime.timedelta(days=1)
    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email="testuser@example.com",
        role="MEMBER",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=expired_at,
        version=1,
    )
    invitation_repo.get_by_token_hash_for_update = AsyncMock(return_value=invitation)

    user_context = UserContext(
        id=user_id,
        supabase_id=str(uuid.uuid4()),
        email="testuser@example.com",
        role=Role.MEMBER,
    )

    with pytest.raises(InvitationInvalidStateError, match="This invitation has expired"):
        await service.accept_invitation(session, raw_token, user_context)


@pytest.mark.asyncio
async def test_accept_invitation_already_member(mock_repos):
    service = mock_repos["service"]
    invitation_repo = mock_repos["invitation_repo"]
    member_repo = mock_repos["member_repo"]
    workspace_repo = mock_repos["workspace_repo"]

    session = AsyncMock()
    raw_token, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    workspace = Workspace(id=workspace_id, name="Test Corp", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email="testuser@example.com",
        role="MEMBER",
        token_hash=token_hash,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.datetime.now(UTC) + datetime.timedelta(days=3),
        version=1,
    )
    invitation_repo.get_by_token_hash_for_update = AsyncMock(return_value=invitation)

    # Already a member
    existing_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=workspace_id, user_id=user_id, role="MEMBER")
    member_repo.get_membership = AsyncMock(return_value=existing_member)

    user_context = UserContext(
        id=user_id,
        supabase_id=str(uuid.uuid4()),
        email="testuser@example.com",
        role=Role.MEMBER,
    )

    with pytest.raises(InvitationConflictError, match="You are already a member"):
        await service.accept_invitation(session, raw_token, user_context)
