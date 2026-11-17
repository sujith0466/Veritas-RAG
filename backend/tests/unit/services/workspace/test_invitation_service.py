"""Unit tests for F4.1 Workspace Invitation (Send, Token, Expiry)."""

import datetime
from datetime import UTC
import re
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from backend.api.v1.schemas.workspace_onboarding import INVITATION_TOKEN_PATTERN
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
    parse_invitation_token,
    verify_invitation_secret,
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
    session.rollback = AsyncMock()
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
    raw_token, token_selector, token_hash = generate_invitation_token()

    assert raw_token.startswith("sec_inv_")
    assert len(raw_token) >= 70
    assert len(token_selector) == 22
    assert token_hash.startswith("$2b$")

    # Verify regex conformance with official WS-A1 schema
    assert re.match(INVITATION_TOKEN_PATTERN, raw_token) is not None

    # Parse and verify secret
    parsed_selector, parsed_secret = parse_invitation_token(raw_token)
    assert parsed_selector == token_selector
    assert verify_invitation_secret(parsed_secret, token_hash) is True

    # High entropy check: successive tokens differ in raw, selector, and verifier
    raw2, sel2, hash2 = generate_invitation_token()
    assert raw_token != raw2
    assert token_selector != sel2
    assert token_hash != hash2


def test_invitation_token_legacy_sha256_verification():
    import hashlib
    legacy_raw = "sec_inv_legacy_opaque_token_without_selector"
    legacy_hash = hashlib.sha256(legacy_raw.encode("utf-8")).hexdigest()

    parsed_sel, parsed_sec = parse_invitation_token(legacy_raw)
    assert parsed_sel is None
    assert parsed_sec == legacy_raw
    assert verify_invitation_secret(parsed_sec, legacy_hash) is True
    assert verify_invitation_secret("wrong_token", legacy_hash) is False


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
    assert invitation.token_selector is not None
    assert len(invitation.token_selector) == 22
    assert invitation.token_hash.startswith("$2b$")
    assert getattr(invitation, "invitation_token", None) is not None
    assert invitation.invitation_token.startswith("sec_inv_")

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
    assert resent_inv.token_selector is not None
    assert len(resent_inv.token_selector) == 22
    assert resent_inv.token_hash.startswith("$2b$")
    assert getattr(resent_inv, "invitation_token", None) is not None
    assert resent_inv.invitation_token.startswith("sec_inv_")
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
        invited_by_user_id=actor_id,
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


# ── 6. Section 2 Acceptance Security Tests (T-2.A, T-2.B) ──────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stored_invitation_role",
    ["MEMBER", "ADMIN", "OWNER", "SUPERADMIN", "CUSTOM_ROLE", "GUEST", "UNKNOWN"],
)
async def test_accept_invitation_unconditional_member_role(
    stored_invitation_role,
    invitation_service,
    mock_session,
    mock_workspace_repo,
    mock_invitation_repo,
    mock_member_repo,
    mock_event_dispatcher,
):
    """T-2.B / D-2.5: Verifies that every invitation acceptance unconditionally

    creates a MEMBER membership, ignoring any stored elevated, legacy, or unexpected
    roles.
    """
    raw_token, token_selector, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    target_email = "invitee@example.com"

    mock_workspace = Workspace(id=workspace_id, name="Security Test WS", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email=target_email,
        role=stored_invitation_role,
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.PENDING.value,
        version=1,
        expires_at=datetime.datetime.now(UTC) + datetime.timedelta(days=7),
    )
    mock_invitation_repo.get_by_token_selector_for_update.return_value = invitation
    mock_member_repo.get_membership.return_value = None

    user_context = MagicMock()
    user_context.id = user_id
    user_context.email = target_email

    result = await invitation_service.accept_invitation(
        session=mock_session,
        raw_token=raw_token,
        user_context=user_context,
    )

    # Return value must be unconditionally MEMBER
    assert result["role"] == "MEMBER"
    assert result["workspace_id"] == workspace_id
    assert result["success"] is True

    # Check that the added WorkspaceMember entity was given role="MEMBER"
    added_members = [
        call_arg[0][0]
        for call_arg in mock_session.add.call_args_list
        if isinstance(call_arg[0][0], WorkspaceMember)
    ]
    assert len(added_members) == 1
    created_member = added_members[0]
    assert created_member.role == "MEMBER"
    assert created_member.user_id == user_id
    assert created_member.workspace_id == workspace_id

    # Check that published domain event records authoritative MEMBER role
    published_events = [
        call_arg[0][0]
        for call_arg in mock_event_dispatcher.publish.call_args_list
    ]
    assert len(published_events) == 1
    assert published_events[0].role == "MEMBER"


@pytest.mark.asyncio
async def test_accept_invitation_concurrency_integrity_error_rollback(
    invitation_service,
    mock_session,
    mock_workspace_repo,
    mock_invitation_repo,
    mock_member_repo,
):
    """T-2.A: Verifies that database uniqueness conflicts (IntegrityError) during

    concurrent invitation acceptance trigger session rollback and return a clean
    InvitationConflictError.
    """
    raw_token, token_selector, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    target_email = "invitee@example.com"

    mock_workspace = Workspace(id=workspace_id, name="Security Test WS", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email=target_email,
        role="MEMBER",
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.PENDING.value,
        version=1,
        expires_at=datetime.datetime.now(UTC) + datetime.timedelta(days=7),
    )
    mock_invitation_repo.get_by_token_selector_for_update.return_value = invitation
    mock_member_repo.get_membership.return_value = None

    user_context = MagicMock()
    user_context.id = user_id
    user_context.email = target_email

    # Simulate concurrent race collision at flush/commit time
    mock_session.flush.side_effect = IntegrityError(
        statement="INSERT INTO workspace_members ...",
        params={},
        orig=Exception("duplicate key value violates unique constraint 'uq_workspace_members_active_user'"),
    )

    with pytest.raises(InvitationConflictError, match="already an active member"):
        await invitation_service.accept_invitation(
            session=mock_session,
            raw_token=raw_token,
            user_context=user_context,
        )

    # Verify that session.rollback was awaited
    mock_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_accept_invitation_unrelated_integrity_error_reraised(
    invitation_service, mock_session, mock_workspace_repo, mock_invitation_repo, mock_member_repo
):
    """T-2.A: Verifies that unrelated database integrity violations (e.g. FK violations,

    not-null constraints, check constraints) are rolled back and re-raised without
    being misclassified as duplicate active-membership conflicts.
    """
    raw_token, token_selector, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    target_email = "invitee@example.com"

    mock_workspace = Workspace(id=workspace_id, name="Security Test WS", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email=target_email,
        role="MEMBER",
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.PENDING.value,
        version=1,
        expires_at=datetime.datetime.now(UTC) + datetime.timedelta(days=7),
    )
    mock_invitation_repo.get_by_token_selector_for_update.return_value = invitation
    mock_member_repo.get_membership.return_value = None

    user_context = MagicMock()
    user_context.id = user_id
    user_context.email = target_email

    # Simulate unrelated foreign-key or check constraint failure
    mock_session.flush.side_effect = IntegrityError(
        statement="INSERT INTO workspace_members ...",
        params={},
        orig=Exception("violates foreign key constraint 'fk_workspace_members_user_id'"),
    )

    with pytest.raises(IntegrityError):
        await invitation_service.accept_invitation(
            session=mock_session,
            raw_token=raw_token,
            user_context=user_context,
        )

    # Verify that session.rollback was awaited and error was NOT misclassified as InvitationConflictError
    mock_session.rollback.assert_awaited_once()


# ── Production Path Re-Invitation Tests (Decision D-2.2 & Requirement 3) ────

@pytest.mark.asyncio
async def test_send_invitation_owner_can_reinvite_soft_deleted_member(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo, mock_invitation_repo, mock_settings_repo
):
    """Verifies that an authorized OWNER can issue a new explicit invitation

    to a previously soft-deleted member via the production send_invitation() path.
    """
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    invitee_id = uuid.uuid4()
    invitee_email = "soft_deleted_user@example.com"

    mock_workspace = Workspace(id=workspace_id, name="Production WS", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    # Actor is OWNER
    owner_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=owner_id, role="OWNER", status="ACTIVE"
    )

    # Invitee has a historical soft-deleted row:
    # Production get_membership(..., include_deleted=False) returns None
    def member_repo_get_membership(ws_id, u_id, include_suspended=True, include_deleted=False):
        if u_id == owner_id:
            return owner_member
        if u_id == invitee_id and not include_deleted:
            return None  # Soft-deleted member is excluded
        return None

    mock_member_repo.get_membership.side_effect = member_repo_get_membership
    mock_invitation_repo.get_pending_by_workspace_and_email.return_value = None
    mock_settings_repo.get_by_workspace_id.return_value = None

    # Invitee exists in users table
    invitee_user = MagicMock()
    invitee_user.id = invitee_id
    invitee_user.email = invitee_email

    mock_user_res = MagicMock()
    mock_user_res.scalars().first.return_value = invitee_user
    mock_session.execute = AsyncMock(return_value=mock_user_res)

    invitation = await invitation_service.send_invitation(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=owner_id,
        email=invitee_email,
        role="MEMBER",
    )

    assert isinstance(invitation, WorkspaceInvitation)
    assert invitation.role == "MEMBER"
    assert invitation.email == invitee_email
    assert invitation.workspace_id == workspace_id
    mock_session.add.assert_called()


@pytest.mark.asyncio
async def test_send_invitation_admin_can_reinvite_soft_deleted_member(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo, mock_invitation_repo, mock_settings_repo
):
    """Verifies that an authorized ADMIN can issue a new explicit invitation

    to a previously soft-deleted member with the MEMBER role.
    """
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    invitee_id = uuid.uuid4()
    invitee_email = "former_member@example.com"

    mock_workspace = Workspace(id=workspace_id, name="Admin WS", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    admin_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=admin_id, role="ADMIN", status="ACTIVE"
    )

    def member_repo_get_membership(ws_id, u_id, include_suspended=True, include_deleted=False):
        if u_id == admin_id:
            return admin_member
        if u_id == invitee_id and not include_deleted:
            return None
        return None

    mock_member_repo.get_membership.side_effect = member_repo_get_membership
    mock_invitation_repo.get_pending_by_workspace_and_email.return_value = None
    mock_settings_repo.get_by_workspace_id.return_value = None

    invitee_user = MagicMock()
    invitee_user.id = invitee_id
    invitee_user.email = invitee_email

    mock_user_res = MagicMock()
    mock_user_res.scalars().first.return_value = invitee_user
    mock_session.execute = AsyncMock(return_value=mock_user_res)

    invitation = await invitation_service.send_invitation(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=admin_id,
        email=invitee_email,
        role="MEMBER",
    )

    assert isinstance(invitation, WorkspaceInvitation)
    assert invitation.role == "MEMBER"
    assert invitation.email == invitee_email


@pytest.mark.parametrize("unauthorized_role", ["MEMBER", "VIEWER"])
@pytest.mark.asyncio
async def test_send_invitation_unauthorized_member_and_viewer_rejected(
    unauthorized_role, invitation_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """Verifies that non-admin actors (MEMBER, VIEWER) cannot issue invitations

    via the production send_invitation() permission check path.
    """
    workspace_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    mock_workspace = Workspace(id=workspace_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    actor_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=actor_id, role=unauthorized_role, status="ACTIVE"
    )
    mock_member_repo.get_membership.return_value = actor_member

    with pytest.raises(InvitationUnauthorizedError, match="Only workspace OWNER or ADMIN can manage invitations"):
        await invitation_service.send_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=actor_id,
            email="candidate@example.com",
            role="MEMBER",
        )


@pytest.mark.asyncio
async def test_send_invitation_active_existing_member_rejected_conflict(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """Verifies that an active existing member cannot receive a duplicate invitation."""
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    active_member_id = uuid.uuid4()
    active_email = "active_member@example.com"

    mock_workspace = Workspace(id=workspace_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    owner_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=owner_id, role="OWNER", status="ACTIVE"
    )
    existing_active = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=active_member_id, role="MEMBER", status="ACTIVE", is_deleted=False
    )

    def member_repo_get_membership(ws_id, u_id, include_suspended=True, include_deleted=False):
        if u_id == owner_id:
            return owner_member
        if u_id == active_member_id:
            return existing_active
        return None

    mock_member_repo.get_membership.side_effect = member_repo_get_membership

    invitee_user = MagicMock()
    invitee_user.id = active_member_id
    invitee_user.email = active_email

    mock_user_res = MagicMock()
    mock_user_res.scalars().first.return_value = invitee_user
    mock_session.execute = AsyncMock(return_value=mock_user_res)

    with pytest.raises(InvitationConflictError, match="The user is already a member of this workspace"):
        await invitation_service.send_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=owner_id,
            email=active_email,
            role="MEMBER",
        )


@pytest.mark.asyncio
async def test_reinvite_soft_deleted_member_lifecycle_e2e(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo, mock_invitation_repo, mock_settings_repo
):
    """End-to-end verification of Decision D-2.2 lifecycle:

    1. OWNER re-invites previously soft-deleted member via send_invitation().
    2. Invitee accepts via accept_invitation().
    3. Fresh MEMBER membership created with distinct PK and is_deleted=False.
    4. Historical soft-deleted membership remains untouched.
    """
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    invitee_id = uuid.uuid4()
    invitee_email = "former_worker@example.com"
    historical_member_id = uuid.uuid4()

    mock_workspace = Workspace(id=workspace_id, name="E2E Lifecycle WS", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = mock_workspace

    # Historical soft-deleted member record
    historical_member = WorkspaceMember(
        id=historical_member_id,
        workspace_id=workspace_id,
        user_id=invitee_id,
        role="MEMBER",
        status="ACTIVE",
        is_deleted=True,
    )
    owner_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=owner_id, role="OWNER", status="ACTIVE"
    )

    # get_membership returns None for invitee when include_deleted=False
    def member_repo_get_membership(ws_id, u_id, include_suspended=True, include_deleted=False):
        if u_id == owner_id:
            return owner_member
        if u_id == invitee_id and include_deleted:
            return historical_member
        return None

    mock_member_repo.get_membership.side_effect = member_repo_get_membership
    mock_invitation_repo.get_pending_by_workspace_and_email.return_value = None
    mock_settings_repo.get_by_workspace_id.return_value = None

    invitee_user = MagicMock()
    invitee_user.id = invitee_id
    invitee_user.email = invitee_email

    mock_user_res = MagicMock()
    mock_user_res.scalars().first.return_value = invitee_user
    mock_session.execute = AsyncMock(return_value=mock_user_res)

    # Step 1: OWNER sends invitation
    invitation = await invitation_service.send_invitation(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=owner_id,
        email=invitee_email,
        role="MEMBER",
    )
    assert invitation.role == "MEMBER"

    # Step 2: Prepare acceptance
    raw_token, token_selector, token_hash = generate_invitation_token()
    invitation.token_selector = token_selector
    invitation.token_hash = token_hash
    invitation.status = InvitationStatus.PENDING.value
    mock_invitation_repo.get_by_token_selector_for_update.return_value = invitation

    invitee_context = MagicMock()
    invitee_context.id = invitee_id
    invitee_context.email = invitee_email

    # Step 3: Invitee accepts invitation
    result = await invitation_service.accept_invitation(
        session=mock_session,
        raw_token=raw_token,
        user_context=invitee_context,
    )
    assert result["success"] is True
    assert result["role"] == "MEMBER"

    # Step 4: Verify new member was created
    added_members = [
        call_arg[0][0]
        for call_arg in mock_session.add.call_args_list
        if isinstance(call_arg[0][0], WorkspaceMember)
    ]
    assert len(added_members) >= 1
    new_member = added_members[-1]
    assert new_member.id != historical_member_id
    assert new_member.user_id == invitee_id
    assert new_member.workspace_id == workspace_id
    assert new_member.role == "MEMBER"
    assert new_member.is_deleted is False

    # Historical member remains untouched with is_deleted=True
    assert historical_member.is_deleted is True
    assert historical_member.id == historical_member_id
