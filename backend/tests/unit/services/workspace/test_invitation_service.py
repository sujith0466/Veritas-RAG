"""Unit tests for F4.1 Workspace Invitation (Send, Token, Expiry)."""

import datetime
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_invitation import (
    InvitationStatus,
    WorkspaceInvitation,
)
from backend.models.entities.workspace_member import WorkspaceMember
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.services.workspace.invitation_service import (
    InvitationConflictError,
    InvitationInvalidStateError,
    InvitationRateLimiter,
    InvitationRateLimitError,
    InvitationUnauthorizedError,
    WorkspaceInvitationService,
    generate_invitation_token,
    hash_token,
)


@pytest.fixture
def mock_invitation_repo():
    return AsyncMock()


@pytest.fixture
def mock_member_repo():
    return AsyncMock()


@pytest.fixture
def mock_workspace_repo():
    return AsyncMock()


@pytest.fixture
def mock_settings_repo():
    return AsyncMock()


@pytest.fixture
def mock_email_provider():
    provider = AsyncMock()
    provider.send_invitation_email = AsyncMock(return_value=True)
    return provider


@pytest.fixture
def mock_event_dispatcher():
    dispatcher = AsyncMock()
    dispatcher.publish = AsyncMock()
    return dispatcher


@pytest.fixture
def isolated_rate_limiter():
    return InvitationRateLimiter()


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    # Mock scalars().first() for user queries
    exec_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = None
    exec_result.scalars.return_value = scalars_mock
    session.execute.return_value = exec_result
    return session


@pytest.fixture
def invitation_service(
    mock_invitation_repo,
    mock_member_repo,
    mock_workspace_repo,
    mock_settings_repo,
    mock_email_provider,
    mock_event_dispatcher,
    isolated_rate_limiter,
):
    return WorkspaceInvitationService(
        invitation_repo=mock_invitation_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
        settings_repo=mock_settings_repo,
        email_provider=mock_email_provider,
        event_dispatcher=mock_event_dispatcher,
        rate_limiter=isolated_rate_limiter,
    )


# ── 1. Cryptographic Token Tests ───────────────────────────────────────────────

def test_generate_invitation_token_entropy_and_hash():
    raw_token, token_hash = generate_invitation_token()

    assert raw_token.startswith("sec_inv_")
    assert len(raw_token) > 40
    assert len(token_hash) == 64  # SHA-256 hex digest length
    assert hash_token(raw_token) == token_hash

    # Ensure high entropy (two consecutive tokens are different)
    raw2, hash2 = generate_invitation_token()
    assert raw_token != raw2
    assert token_hash != hash2


# ── 2. Send Invitation Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_invitation_success(
    invitation_service,
    mock_session,
    mock_workspace_repo,
    mock_member_repo,
    mock_settings_repo,
    mock_invitation_repo,
    mock_email_provider,
    mock_event_dispatcher,
):
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_email = "colleague@example.com"

    mock_workspace = Workspace(id=workspace_id, name="Acme Inc", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=actor_id, role="OWNER")
    mock_member_repo.get_membership.return_value = mock_member

    # No existing pending invitation
    mock_invitation_repo.get_pending_by_workspace_and_email.return_value = None

    # Custom TTL in settings
    mock_settings = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={"invitations": {"ttl_days": 14}},
    )
    mock_settings_repo.get_by_workspace_id.return_value = mock_settings

    invitation = await invitation_service.send_invitation(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=actor_id,
        email=target_email,
        role="MEMBER",
        custom_message="Welcome aboard!",
    )

    assert invitation.workspace_id == workspace_id
    assert invitation.email == "colleague@example.com"
    assert invitation.role == "MEMBER"
    assert invitation.status == InvitationStatus.PENDING.value
    assert invitation.version == 1
    assert invitation.resend_count == 0

    # Verify session additions (Entity + AuditLog) and commit
    assert mock_session.add.call_count >= 2
    mock_session.commit.assert_awaited_once()

    # Verify event published and email sent
    mock_event_dispatcher.publish.assert_awaited_once()
    mock_email_provider.send_invitation_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_invitation_non_active_workspace_fails(
    invitation_service, mock_session, mock_workspace_repo
):
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    mock_workspace = Workspace(id=workspace_id, name="Acme Inc", status=WorkspaceStatus.SUSPENDED.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    with pytest.raises(InvitationInvalidStateError, match="SUSPENDED"):
        await invitation_service.send_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=actor_id,
            email="test@example.com",
            role="MEMBER",
        )


@pytest.mark.asyncio
async def test_send_invitation_unauthorized_role_hierarchy(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo
):
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    mock_workspace = Workspace(id=workspace_id, name="Acme Inc", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    # Actor is ADMIN
    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=actor_id, role="ADMIN")
    mock_member_repo.get_membership.return_value = mock_member

    # ADMIN cannot invite OWNER
    with pytest.raises(InvitationUnauthorizedError, match="ADMIN cannot invite a user to the OWNER role"):
        await invitation_service.send_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=actor_id,
            email="test@example.com",
            role="OWNER",
        )


@pytest.mark.asyncio
async def test_send_invitation_duplicate_pending_fails(
    invitation_service,
    mock_session,
    mock_workspace_repo,
    mock_member_repo,
    mock_invitation_repo,
):
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_email = "duplicate@example.com"

    mock_workspace = Workspace(id=workspace_id, name="Acme Inc", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=actor_id, role="OWNER")
    mock_member_repo.get_membership.return_value = mock_member

    existing_inv = WorkspaceInvitation(
        workspace_id=workspace_id,
        email=target_email,
        role="MEMBER",
        token_hash="dummyhash",
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.datetime.now(UTC) + datetime.timedelta(days=7),
    )
    mock_invitation_repo.get_pending_by_workspace_and_email.return_value = existing_inv

    with pytest.raises(InvitationConflictError, match="A pending invitation already exists"):
        await invitation_service.send_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=actor_id,
            email=target_email,
            role="MEMBER",
        )


# ── 3. Rate Limiting Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invitation_rate_limits_enforced(
    invitation_service,
    mock_session,
    mock_workspace_repo,
    mock_member_repo,
    mock_invitation_repo,
    mock_settings_repo,
):
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_email = "spammed@example.com"

    mock_workspace = Workspace(id=workspace_id, name="Acme Inc", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=actor_id, role="OWNER")
    mock_member_repo.get_membership.return_value = mock_member
    mock_invitation_repo.get_pending_by_workspace_and_email.return_value = None
    mock_settings_repo.get_by_workspace_id.return_value = None

    # Trigger 5 invitations to the same email
    for _ in range(5):
        await invitation_service.send_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=actor_id,
            email=target_email,
            role="MEMBER",
        )

    # 6th invitation should trigger 429 rate limit error
    with pytest.raises(InvitationRateLimitError, match="Daily invitation limit for this recipient email exceeded"):
        await invitation_service.send_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=actor_id,
            email=target_email,
            role="MEMBER",
        )


# ── 4. Resend & Revocation Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resend_invitation_success_and_cooldown(
    invitation_service,
    mock_session,
    mock_workspace_repo,
    mock_member_repo,
    mock_invitation_repo,
    mock_settings_repo,
):
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    invitation_id = uuid.uuid4()

    mock_workspace = Workspace(id=workspace_id, name="Acme Inc", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=actor_id, role="ADMIN")
    mock_member_repo.get_membership.return_value = mock_member

    # Created 2 minutes ago (past 60s cooldown)
    created_time = datetime.datetime.now(UTC) - datetime.timedelta(minutes=2)
    invitation = WorkspaceInvitation(
        id=invitation_id,
        workspace_id=workspace_id,
        email="test@example.com",
        role="MEMBER",
        token_hash="oldhash",
        status=InvitationStatus.PENDING.value,
        resend_count=0,
        version=1,
        created_at=created_time,
        last_resent_at=None,
        expires_at=datetime.datetime.now(UTC) + datetime.timedelta(days=7),
    )
    mock_invitation_repo.get_by_id.return_value = invitation
    mock_settings_repo.get_by_workspace_id.return_value = None

    resent_inv = await invitation_service.resend_invitation(
        session=mock_session,
        workspace_id=workspace_id,
        invitation_id=invitation_id,
        actor_id=actor_id,
    )

    assert resent_inv.resend_count == 1
    assert resent_inv.version == 2
    assert resent_inv.token_hash != "oldhash"
    assert resent_inv.last_resent_at is not None

    # Immediate next resend should fail due to 60s cooldown
    with pytest.raises(InvitationRateLimitError, match="Please wait"):
        await invitation_service.resend_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            invitation_id=invitation_id,
            actor_id=actor_id,
        )


@pytest.mark.asyncio
async def test_revoke_invitation_success(
    invitation_service,
    mock_session,
    mock_workspace_repo,
    mock_member_repo,
    mock_invitation_repo,
    mock_event_dispatcher,
):
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    invitation_id = uuid.uuid4()

    mock_workspace = Workspace(id=workspace_id, name="Acme Inc", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    mock_member = WorkspaceMember(workspace_id=workspace_id, user_id=actor_id, role="OWNER")
    mock_member_repo.get_membership.return_value = mock_member

    invitation = WorkspaceInvitation(
        id=invitation_id,
        workspace_id=workspace_id,
        email="test@example.com",
        role="MEMBER",
        token_hash="somehash",
        status=InvitationStatus.PENDING.value,
        version=1,
    )
    mock_invitation_repo.get_by_id.return_value = invitation

    revoked = await invitation_service.revoke_invitation(
        session=mock_session,
        workspace_id=workspace_id,
        invitation_id=invitation_id,
        actor_id=actor_id,
    )

    assert revoked.status == InvitationStatus.REVOKED.value
    assert revoked.revoked_by_user_id == actor_id
    assert revoked.revoked_at is not None
    assert revoked.version == 2

    mock_event_dispatcher.publish.assert_awaited_once()


# ── 5. Expiration Worker Cleanup Tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_expiration_cleanup(
    invitation_service,
    mock_session,
    mock_invitation_repo,
    mock_event_dispatcher,
):
    inv1 = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        email="expired1@example.com",
        role="MEMBER",
        token_hash="hash1",
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.datetime.now(UTC) - datetime.timedelta(days=1),
    )
    inv2 = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        email="expired2@example.com",
        role="VIEWER",
        token_hash="hash2",
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.datetime.now(UTC) - datetime.timedelta(hours=2),
    )

    mock_invitation_repo.find_expired_pending.return_value = [inv1, inv2]
    mock_invitation_repo.batch_expire.return_value = 2

    expired_count = await invitation_service.run_expiration_cleanup(session=mock_session)

    assert expired_count == 2
    assert mock_event_dispatcher.publish.call_count == 2
    mock_session.commit.assert_awaited_once()
