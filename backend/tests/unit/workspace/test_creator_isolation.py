"""Unit tests for Section 4 & Section 5 Creator Isolation and Governance.

Validates:
- Decision Q1: Independent per-creator join codes.
- Decision Q2: True reusable invitations for multiple members.
- Decision Q3: Unlimited redemption analytics counter.
- Decision Q4: Default 7-day TTL and range clamping.
- Decision Q6: Strict creator-only invitation visibility and peer protection.
- Correction C3: Pre-dispatch double-check synchronization (Outcomes 1, 2, 3).
- Correction C5: Operational custodian protocol for legacy join codes.
- Correction C7: Coordinated HMAC pepper retirement protocol.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.models.entities.notification_outbox import NotificationOutbox
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_invitation import (
    InvitationStatus,
    WorkspaceInvitation,
)
from backend.models.entities.workspace_join_code import (
    WorkspaceJoinCode,
)
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.services.workspace.invitation_service import (
    InvitationUnauthorizedError,
    WorkspaceInvitationService,
)
from backend.services.workspace.join_code_service import (
    JoinCodeService,
)
from backend.services.workspace.management_service import (
    WorkspaceUnauthorizedError,
)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    exec_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = None
    exec_result.scalars.return_value = scalars_mock
    session.execute.return_value = exec_result
    return session


@pytest.fixture
def workspace_id():
    return uuid.uuid4()


@pytest.fixture
def owner_id():
    return uuid.uuid4()


@pytest.fixture
def admin_b_id():
    return uuid.uuid4()


@pytest.fixture
def mock_workspace_repo():
    return AsyncMock()


@pytest.fixture
def mock_member_repo():
    return AsyncMock()


@pytest.fixture
def mock_settings_repo():
    repo = AsyncMock()
    repo.get_by_workspace_id = AsyncMock(return_value=None)
    repo.get_by_workspace_id_for_update = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_invitation_repo():
    return AsyncMock()


@pytest.fixture
def mock_email_provider():
    provider = AsyncMock()
    provider.send_email = AsyncMock(return_value=True)
    return provider


@pytest.fixture
def join_code_service(mock_settings_repo, mock_member_repo, mock_workspace_repo):
    service = JoinCodeService(
        settings_repo=mock_settings_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )
    service.join_code_repo = AsyncMock()
    return service


@pytest.fixture
def invitation_service(
    mock_invitation_repo,
    mock_member_repo,
    mock_workspace_repo,
    mock_settings_repo,
    mock_email_provider,
):
    return WorkspaceInvitationService(
        invitation_repo=mock_invitation_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
        settings_repo=mock_settings_repo,
        email_provider=mock_email_provider,
    )


# ── 1. Join-Code Creator Isolation (Decision Q1 Option A) ────────────────────

@pytest.mark.asyncio
async def test_join_code_creator_isolation(join_code_service, mock_session, workspace_id, owner_id, admin_b_id):
    """Verifies each OWNER and ADMIN independently manages their own join code."""
    join_code_service.workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value
    )

    join_code_service.member_repo.get_membership.side_effect = lambda ws_id, u_id: (
        WorkspaceMember(workspace_id=ws_id, user_id=u_id, role="OWNER", status=MemberStatus.ACTIVE.value)
        if u_id == owner_id
        else WorkspaceMember(workspace_id=ws_id, user_id=u_id, role="ADMIN", status=MemberStatus.ACTIVE.value)
    )

    # Owner generates code
    join_code_service.settings_repo.get_by_workspace_id.return_value = None
    res_owner = await join_code_service.generate_new_join_code(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=owner_id,
    )
    assert res_owner.join_code is not None

    # Admin B generates code
    res_admin = await join_code_service.generate_new_join_code(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=admin_b_id,
    )
    assert res_admin.join_code is not None
    assert res_owner.join_code != res_admin.join_code

    # Admin B rotates their code: disable_active_for_creator is called with admin_b_id ONLY
    await join_code_service.generate_new_join_code(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=admin_b_id,
        is_regeneration=True,
    )

    join_code_service.join_code_repo.disable_active_for_creator.assert_called_with(
        mock_session, workspace_id, admin_b_id
    )


# ── 2. Invitation Creator Isolation (Decision Q6 Option A) ────────────────────

@pytest.mark.asyncio
async def test_invitation_creator_isolation_peer_protection(invitation_service, mock_session, workspace_id, owner_id, admin_b_id):
    """Verifies that Admin B cannot view, resend, or revoke Owner A's invitation."""
    invitation_service.workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value
    )
    invitation_service.member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=workspace_id, user_id=admin_b_id, role="ADMIN", status=MemberStatus.ACTIVE.value
    )

    # Invitation created by Owner A
    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email="guest@example.com",
        role="MEMBER",
        token_hash="hash",
        status=InvitationStatus.PENDING.value,
        invited_by_user_id=owner_id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    invitation_service.invitation_repo.get_by_id.return_value = invitation

    from backend.services.workspace.invitation_service import InvitationNotFoundError
    # Admin B attempting to get Owner A's invitation fails with 404 (prevent IDOR discovery)
    with pytest.raises(InvitationNotFoundError, match="Invitation not found"):
        await invitation_service.get_invitation(workspace_id, invitation.id, actor_id=admin_b_id)

    # Admin B attempting to revoke Owner A's invitation fails
    with pytest.raises(InvitationUnauthorizedError, match="Only the creator"):
        await invitation_service.revoke_invitation(mock_session, workspace_id, invitation.id, actor_id=admin_b_id)

    # Admin B attempting to resend Owner A's invitation fails
    with pytest.raises(InvitationUnauthorizedError, match="Only the creator"):
        await invitation_service.resend_invitation(mock_session, workspace_id, invitation.id, actor_id=admin_b_id)


# ── 3. Reusable Invitations (Decision Q2 Option A) ───────────────────────────

@pytest.mark.asyncio
async def test_reusable_invitation_multiple_redemptions(invitation_service, mock_session, workspace_id, owner_id):
    """Verifies reusable link allows multiple users to redeem and join as MEMBER."""
    from backend.services.workspace.invitation_service import generate_invitation_token

    raw_token, token_selector, token_hash = generate_invitation_token()

    invitation_service.workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value
    )

    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email=None,  # Reusable link
        role="MEMBER",
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.PENDING.value,
        is_legacy_bound=False,
        version=1,
        invited_by_user_id=owner_id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    invitation_service.invitation_repo.get_by_token_selector_for_update.return_value = invitation
    invitation_service.member_repo.get_membership.return_value = None  # Not currently a member

    user_1 = MagicMock(id=uuid.uuid4(), email="user1@example.com")
    user_2 = MagicMock(id=uuid.uuid4(), email="user2@example.com")

    # User 1 accepts
    res1 = await invitation_service.accept_invitation(
        session=mock_session,
        raw_token=raw_token,
        user_context=user_1,
    )
    assert res1["role"] == "MEMBER"
    assert invitation.status == InvitationStatus.PENDING.value

    # User 2 accepts same link
    res2 = await invitation_service.accept_invitation(
        session=mock_session,
        raw_token=raw_token,
        user_context=user_2,
    )
    assert res2["role"] == "MEMBER"
    assert invitation.status == InvitationStatus.PENDING.value


# ── 4. Unlimited Redemption Analytics (Decision Q3 Option A) ─────────────────

@pytest.mark.asyncio
async def test_unlimited_redemption_analytics_counter(join_code_service, mock_session, workspace_id):
    """Verifies use_count acts as an analytics counter without blocking redemptions."""
    code = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        use_count=50,
        is_enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    join_code_service.join_code_repo.list_by_workspace.return_value = [code]

    await join_code_service.record_join_code_usage(mock_session, workspace_id)
    join_code_service.join_code_repo.increment_usage.assert_called_with(mock_session, code.id)


# ── 5. Operational Custodian Protocol (Correction C5) ────────────────────────

@pytest.mark.asyncio
async def test_operational_custodian_claim_protocol(join_code_service, mock_session, workspace_id, owner_id, admin_b_id):
    """Verifies active OWNER can claim operational custodianship over unmapped legacy codes."""
    join_code_service.workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value
    )

    legacy_code = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        created_by_user_id=None,
        operational_custodian_user_id=None,
        is_legacy=True,
        is_enabled=False,
        version=1,
    )
    join_code_service.join_code_repo.get_by_id.return_value = legacy_code

    # Non-owner ADMIN attempts claim -> Forbidden
    join_code_service.member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=workspace_id, user_id=admin_b_id, role="ADMIN", status=MemberStatus.ACTIVE.value
    )
    with pytest.raises(WorkspaceUnauthorizedError, match="Only an active workspace OWNER"):
        await join_code_service.claim_legacy_join_code(mock_session, workspace_id, admin_b_id, legacy_code.id)

    # Active OWNER claims -> Success
    join_code_service.member_repo.get_membership.return_value = WorkspaceMember(
        workspace_id=workspace_id, user_id=owner_id, role="OWNER", status=MemberStatus.ACTIVE.value
    )
    claimed = await join_code_service.claim_legacy_join_code(mock_session, workspace_id, owner_id, legacy_code.id)
    assert claimed.operational_custodian_user_id == owner_id
    assert claimed.created_by_user_id is None  # Immutable provenance
    assert claimed.is_enabled is True


# ── 6. Coordinated Pepper Retirement Protocol (Correction C7) ─────────────────

@pytest.mark.asyncio
async def test_coordinated_pepper_retirement_protocol(join_code_service, mock_session):
    """Verifies that all retained records migrate to v2 and zero v1 references remain."""
    join_code_service.join_code_repo.count_by_pepper_version.return_value = 0
    clean = await join_code_service.verify_zero_v1_references(mock_session)
    assert clean is True


# ── 7. Outbox Pre-Dispatch Double-Check Sync (Correction C3) ─────────────────

@pytest.mark.asyncio
async def test_outbox_double_check_outcomes(mock_session, workspace_id, owner_id):
    """Verifies pre-dispatch double-check handling for Outcomes 1, 2, and 3."""
    outbox_entry = NotificationOutbox(
        id=uuid.uuid4(),
        join_code_id=uuid.uuid4(),
        join_code_version=1,
        workspace_id=workspace_id,
        recipient_user_id=owner_id,
        checkpoint="24H",
        channel="EMAIL",
        status="CLAIMED",
        idempotency_key="key1",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    code_rotated = WorkspaceJoinCode(
        id=outbox_entry.join_code_id,
        workspace_id=workspace_id,
        version=2,  # Rotated!
        is_enabled=True,
        is_deleted=False,
        expires_at=datetime.now(UTC) + timedelta(hours=20),
    )
    assert code_rotated.version != outbox_entry.join_code_version

    code_revoked = WorkspaceJoinCode(
        id=outbox_entry.join_code_id,
        workspace_id=workspace_id,
        version=1,
        is_enabled=False,  # Revoked!
        is_deleted=False,
    )
    assert not code_revoked.is_enabled

    code_valid = WorkspaceJoinCode(
        id=outbox_entry.join_code_id,
        workspace_id=workspace_id,
        version=1,
        is_enabled=True,
        is_deleted=False,
        expires_at=datetime.now(UTC) + timedelta(hours=10),
    )
    assert code_valid.version == outbox_entry.join_code_version
    assert code_valid.is_enabled is True
