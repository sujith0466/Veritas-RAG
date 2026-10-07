"""Automated tests for invitation service fixes: inviter resolution, acceptance link, and query-time expiration."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_invitation import InvitationStatus, WorkspaceInvitation
from backend.models.entities.workspace_member import WorkspaceMember
from backend.repositories.workspace_invitation import WorkspaceInvitationRepository
from backend.services.email.provider import SMTPEmailProvider
from backend.services.workspace.invitation_service import WorkspaceInvitationService


@pytest.mark.asyncio
async def test_inviter_identity_resolved_from_actor():
    """Verify create_invitation resolves inviter name from actor user and passes it to email provider."""
    actor_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    mock_invitation_repo = AsyncMock()
    mock_invitation_repo.get_pending_by_workspace_and_email.return_value = None

    mock_member_repo = AsyncMock()
    actor_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=actor_id,
        role="ADMIN",
        status="ACTIVE",
    )
    mock_member_repo.get_membership.return_value = actor_member
    mock_member_repo.is_member.return_value = False

    mock_workspace_repo = AsyncMock()
    mock_workspace = Workspace(
        id=workspace_id,
        name="Security Guild",
        slug="security-guild",
        status=WorkspaceStatus.ACTIVE,
    )
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    mock_settings_repo = AsyncMock()
    mock_settings_repo.get_by_workspace_id.return_value = None

    mock_user_repo = AsyncMock()
    mock_actor_user = User(
        id=actor_id,
        email="lead@raguard.io",
        display_name="Security Lead",
        username="seclead",
    )
    mock_user_repo.get_by_id.return_value = mock_actor_user

    mock_email_provider = AsyncMock()
    mock_email_provider.send_invitation_email = AsyncMock(return_value=True)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_user_res = MagicMock()
    mock_user_res.scalars.return_value.first.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_user_res)

    service = WorkspaceInvitationService(
        invitation_repo=mock_invitation_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
        settings_repo=mock_settings_repo,
        email_provider=mock_email_provider,
        user_repo=mock_user_repo,
    )

    invitation = await service.send_invitation(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=actor_id,
        email="newhire@raguard.io",
        role="MEMBER",
    )

    assert invitation is not None
    mock_email_provider.send_invitation_email.assert_called_once()
    call_kwargs = mock_email_provider.send_invitation_email.call_args.kwargs
    assert call_kwargs["inviter_name"] == "Security Lead"
    assert call_kwargs["to_email"] == "newhire@raguard.io"
    assert call_kwargs["workspace_name"] == "Security Guild"


@pytest.mark.asyncio
async def test_email_provider_generates_correct_acceptance_link():
    """Verify SMTPEmailProvider constructs absolute acceptance link format {FRONTEND_URL}/invitations/accept?token={raw_token}."""
    with patch("backend.services.email.provider.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.frontend_url = "https://app.raguard.io"
        mock_settings.smtp.is_configured = True
        mock_get_settings.return_value = mock_settings

        provider = SMTPEmailProvider()
        provider._send_email = AsyncMock(return_value=True)

        token = "test_raw_token_xyz"
        await provider.send_invitation_email(
            to_email="colleague@example.com",
            raw_token=token,
            workspace_name="Veritas Core",
            role="MEMBER",
            inviter_name="Alice",
        )

        provider._send_email.assert_called_once()
        body = provider._send_email.call_args[0][2]
        assert "https://app.raguard.io/invitations/accept?token=test_raw_token_xyz" in body


@pytest.mark.asyncio
async def test_invitation_query_time_expiration_filter():
    """Verify WorkspaceInvitationRepository filters out expired invitations at query time in both count and item queries."""
    now_utc = datetime.datetime.now(datetime.UTC)
    valid_inv = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        email="valid@example.com",
        role="MEMBER",
        status="PENDING",
        token_hash="hash2",
        expires_at=now_utc + datetime.timedelta(days=2),
    )

    count_result = MagicMock()
    count_result.scalar.return_value = 1

    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = [valid_inv]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[count_result, items_result])

    repo = WorkspaceInvitationRepository(mock_session)
    items, total = await repo.list_by_workspace(valid_inv.workspace_id, status=InvitationStatus.PENDING.value)

    assert mock_session.execute.call_count == 2
    # Verify count query includes expires_at >
    count_stmt_str = str(mock_session.execute.call_args_list[0][0][0])
    assert "expires_at >" in count_stmt_str
    # Verify items query includes expires_at >
    items_stmt_str = str(mock_session.execute.call_args_list[1][0][0])
    assert "expires_at >" in items_stmt_str

    assert total == 1
    assert len(items) == 1
    assert items[0].email == "valid@example.com"
