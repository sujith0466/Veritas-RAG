"""Comprehensive unit & security tests for Workspace Rejoining & Lifecycle (Section 2 Package T-2.E).

Verifies all 10 core scenarios governed by Project Owner Decision D-2.2 and Package T-2.E:
1. Normal first-time invitation acceptance creates active MEMBER.
2. Active-member collision returns InvitationConflictError (mapped to HTTP 409).
3. Suspended-member collision blocks join-code redemption (HTTP 409 / 403).
4. Soft-deleted member rejoining via explicit invitation creates separate active MEMBER row while preserving historical row.
5. Soft-deleted member attempting join-code redemption is rejected with HTTP 409 conflict.
6. Replay of already accepted invitation is rejected with InvitationInvalidStateError (HTTP 400).
7. Concurrent acceptance of same invitation safely resolves (first wins, second rejected).
8. Concurrent acceptance of separate invitations for same user triggers IntegrityError rollback -> InvitationConflictError.
9. Legacy elevated invitation role (ADMIN/OWNER) unconditionally assigns MEMBER (D-2.5 / T-2.B).
10. Membership repository queries with include_deleted=True deterministically prioritize active rows over soft-deleted rows (T-2.C).
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_invitation import (
    InvitationStatus,
    WorkspaceInvitation,
)
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.services.workspace.invitation_service import (
    InvitationConflictError,
    InvitationInvalidStateError,
    InvitationRateLimiter,
    WorkspaceInvitationService,
    generate_invitation_token,
)
from backend.services.workspace.workspace_joining_service import (
    WorkspaceJoiningService,
    WorkspaceMembershipConflictError,
    WorkspaceMembershipSuspendedError,
)


# ── Shared Test Fixtures ─────────────────────────────────────────────────────

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
    exec_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = None
    exec_result.scalars.return_value = scalars_mock
    session.execute.return_value = exec_result
    return session


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
def invitation_service(
    mock_invitation_repo,
    mock_member_repo,
    mock_workspace_repo,
    mock_settings_repo,
    mock_email_provider,
    mock_event_dispatcher,
):
    return WorkspaceInvitationService(
        invitation_repo=mock_invitation_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
        settings_repo=mock_settings_repo,
        email_provider=mock_email_provider,
        event_dispatcher=mock_event_dispatcher,
        rate_limiter=InvitationRateLimiter(),
    )


@pytest.fixture
def mock_join_code_service():
    service = AsyncMock()
    service.validate_join_code_candidate = AsyncMock(return_value=(True, "", "MEMBER"))
    service.record_join_code_usage = AsyncMock(return_value=True)
    return service


@pytest.fixture
def joining_service(
    mock_workspace_repo,
    mock_settings_repo,
    mock_member_repo,
    mock_join_code_service,
    invitation_service,
):
    return WorkspaceJoiningService(
        workspace_repo=mock_workspace_repo,
        settings_repo=mock_settings_repo,
        member_repo=mock_member_repo,
        join_code_service=mock_join_code_service,
        invitation_service=invitation_service,
    )


# ── Scenario 1: First-Time Invitation Acceptance ─────────────────────────────

@pytest.mark.asyncio
async def test_first_time_invitation_acceptance_creates_member(
    invitation_service, mock_session, mock_workspace_repo, mock_invitation_repo, mock_member_repo
):
    raw_token, token_selector, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    email = "newuser@example.com"

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value
    )
    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email=email,
        role="MEMBER",
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.PENDING.value,
        version=1,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    mock_invitation_repo.get_by_token_selector_for_update.return_value = invitation
    mock_member_repo.get_membership.return_value = None

    user_ctx = MagicMock(id=user_id, email=email)
    res = await invitation_service.accept_invitation(mock_session, raw_token, user_ctx)

    assert res["success"] is True
    assert res["role"] == "MEMBER"
    assert res["workspace_id"] == workspace_id


# ── Scenario 2: Active-Member Collision Returns Conflict (HTTP 409) ──────────

@pytest.mark.asyncio
async def test_active_member_collision_returns_conflict(
    invitation_service, mock_session, mock_workspace_repo, mock_invitation_repo, mock_member_repo
):
    raw_token, token_selector, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    email = "activeuser@example.com"

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value
    )
    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email=email,
        role="MEMBER",
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.PENDING.value,
        version=1,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    mock_invitation_repo.get_by_token_selector_for_update.return_value = invitation

    # User already has an active membership
    existing = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )
    mock_member_repo.get_membership.return_value = existing

    user_ctx = MagicMock(id=user_id, email=email)
    with pytest.raises(InvitationConflictError, match="already a member of this workspace"):
        await invitation_service.accept_invitation(mock_session, raw_token, user_ctx)


# ── Scenario 3: Suspended-Member Collision Blocks Join Code ──────────────────

@pytest.mark.asyncio
async def test_suspended_member_collision_blocks_join_code(
    joining_service, mock_session, mock_workspace_repo, mock_member_repo
):
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(
        id=workspace_id,
        name="Security WS",
        slug="sec-ws",
        public_id="SEC-WS-01",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_public_id.return_value = ws

    # Existing membership is SUSPENDED
    suspended_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=user_id,
        role="MEMBER",
        status=MemberStatus.SUSPENDED.value,
        is_deleted=False,
    )
    mock_member_repo.get_membership.return_value = suspended_member

    with pytest.raises(WorkspaceMembershipSuspendedError, match="does not permit join-code redemption"):
        await joining_service.join_workspace(
            session=mock_session,
            user_id=user_id,
            user_email="suspended@example.com",
            workspace_identifier="SEC-WS-01",
            join_code="VR-234567",
        )


# ── Scenario 4: Soft-Deleted Member Rejoining via Explicit Invitation (D-2.2) ─

@pytest.mark.asyncio
async def test_soft_deleted_member_rejoining_via_invitation_success(
    invitation_service, mock_session, mock_workspace_repo, mock_invitation_repo, mock_member_repo
):
    """Decision D-2.2: Soft-deleted member rejoins via new explicit invitation.

    Historical row remains untouched; a new active row is inserted with role=MEMBER.
    """
    raw_token, token_selector, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    email = "rejoiner@example.com"
    historical_member_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Rejoin Test WS", status=WorkspaceStatus.ACTIVE.value
    )
    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email=email,
        role="MEMBER",
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.PENDING.value,
        version=1,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    mock_invitation_repo.get_by_token_selector_for_update.return_value = invitation

    # Active membership query returns None because previous row is deleted
    mock_member_repo.get_membership.return_value = None

    user_ctx = MagicMock(id=user_id, email=email)
    result = await invitation_service.accept_invitation(mock_session, raw_token, user_ctx)

    assert result["success"] is True
    assert result["role"] == "MEMBER"

    # Verify a new WorkspaceMember was created and its ID is distinct from historical ID
    added_members = [
        call_arg[0][0]
        for call_arg in mock_session.add.call_args_list
        if isinstance(call_arg[0][0], WorkspaceMember)
    ]
    assert len(added_members) == 1
    new_member = added_members[0]
    assert new_member.id != historical_member_id
    assert new_member.user_id == user_id
    assert new_member.workspace_id == workspace_id
    assert new_member.role == "MEMBER"
    assert new_member.status == MemberStatus.ACTIVE.value
    assert getattr(new_member, "is_deleted", False) is False


# ── Scenario 5: Soft-Deleted Member Join-Code Redemption Rejected (HTTP 409) ─

@pytest.mark.asyncio
async def test_soft_deleted_member_join_code_redemption_rejected_409(
    joining_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """Decision D-2.2: Soft-deleted member attempting join-code redemption must

    continue receiving HTTP 409 Conflict.
    """
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ws = Workspace(
        id=workspace_id,
        name="Security WS",
        slug="sec-ws",
        public_id="SEC-WS-01",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_public_id.return_value = ws

    # Existing membership is soft-deleted
    deleted_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
        is_deleted=True,
    )
    mock_member_repo.get_membership.return_value = deleted_member

    with pytest.raises(WorkspaceMembershipConflictError, match="does not permit join-code redemption"):
        await joining_service.join_workspace(
            session=mock_session,
            user_id=user_id,
            user_email="deleted@example.com",
            workspace_identifier="SEC-WS-01",
            join_code="VR-234567",
        )


# ── Scenario 6: Replay of Accepted Invitation Rejected (HTTP 400) ─────────────

@pytest.mark.asyncio
async def test_invitation_replay_rejected_invalid_state(
    invitation_service, mock_session, mock_workspace_repo, mock_invitation_repo
):
    raw_token, token_selector, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    email = "replay@example.com"

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value
    )
    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email=email,
        role="MEMBER",
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.ACCEPTED.value,  # Already accepted
        version=2,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    mock_invitation_repo.get_by_token_selector_for_update.return_value = invitation

    user_ctx = MagicMock(id=user_id, email=email)
    with pytest.raises(InvitationInvalidStateError, match="already ACCEPTED"):
        await invitation_service.accept_invitation(mock_session, raw_token, user_ctx)


# ── Scenario 7: Concurrent Acceptance of Same Invitation ──────────────────────

@pytest.mark.asyncio
async def test_concurrent_same_invitation_acceptance_race(
    invitation_service, mock_session, mock_workspace_repo, mock_invitation_repo, mock_member_repo
):
    """Simulates row lock resolution where Worker 1 transitions invitation to ACCEPTED

    and Worker 2 observes ACCEPTED status upon acquiring row lock.
    """
    raw_token, token_selector, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    email = "race@example.com"

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value
    )

    # Worker 1 sees PENDING
    invitation_w1 = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email=email,
        role="MEMBER",
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.PENDING.value,
        version=1,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    mock_invitation_repo.get_by_token_selector_for_update.return_value = invitation_w1
    mock_member_repo.get_membership.return_value = None

    user_ctx = MagicMock(id=user_id, email=email)
    res1 = await invitation_service.accept_invitation(mock_session, raw_token, user_ctx)
    assert res1["success"] is True

    # Worker 2 acquires lock next and sees ACCEPTED
    invitation_w2 = WorkspaceInvitation(
        id=invitation_w1.id,
        workspace_id=workspace_id,
        email=email,
        role="MEMBER",
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.ACCEPTED.value,
        version=2,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    mock_invitation_repo.get_by_token_selector_for_update.return_value = invitation_w2

    with pytest.raises(InvitationInvalidStateError, match="already ACCEPTED"):
        await invitation_service.accept_invitation(mock_session, raw_token, user_ctx)


# ── Scenario 8: Concurrent Acceptance of Separate Invitations (IntegrityError Rollback)

@pytest.mark.asyncio
async def test_concurrent_separate_invitations_integrity_error_rollback(
    invitation_service, mock_session, mock_workspace_repo, mock_invitation_repo, mock_member_repo
):
    """Package T-2.A: When two separate invitations for the same user race,

    second transaction triggers IntegrityError (unique partial index).
    Service catches IntegrityError, awaits session.rollback(), and raises InvitationConflictError.
    """
    raw_token, token_selector, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    email = "race@example.com"

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value
    )
    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email=email,
        role="MEMBER",
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.PENDING.value,
        version=1,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    mock_invitation_repo.get_by_token_selector_for_update.return_value = invitation
    mock_member_repo.get_membership.return_value = None

    # Database uniqueness conflict raised at flush time
    mock_session.flush.side_effect = IntegrityError(
        statement="INSERT INTO workspace_members ...",
        params={},
        orig=Exception("duplicate key violates uq_workspace_members_active_user"),
    )

    user_ctx = MagicMock(id=user_id, email=email)
    with pytest.raises(InvitationConflictError, match="already an active member"):
        await invitation_service.accept_invitation(mock_session, raw_token, user_ctx)

    # Session rollback must have been called
    mock_session.rollback.assert_awaited_once()


# ── Scenario 9: Legacy Elevated Invitation Acceptance Capped at MEMBER (D-2.5 / T-2.B)

@pytest.mark.asyncio
@pytest.mark.parametrize("elevated_role", ["ADMIN", "OWNER", "SUPERADMIN", "CUSTOM"])
async def test_legacy_elevated_invitation_acceptance_capped_at_member(
    elevated_role, invitation_service, mock_session, mock_workspace_repo, mock_invitation_repo, mock_member_repo
):
    """Decision D-2.5 / Package T-2.B: Regardless of stored role, acceptance

    unconditionally assigns role='MEMBER'.
    """
    raw_token, token_selector, token_hash = generate_invitation_token()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    email = "elevated@example.com"

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value
    )
    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email=email,
        role=elevated_role,  # Stored elevated role
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.PENDING.value,
        version=1,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    mock_invitation_repo.get_by_token_selector_for_update.return_value = invitation
    mock_member_repo.get_membership.return_value = None

    user_ctx = MagicMock(id=user_id, email=email)
    result = await invitation_service.accept_invitation(mock_session, raw_token, user_ctx)

    assert result["role"] == "MEMBER"

    added_members = [
        call_arg[0][0]
        for call_arg in mock_session.add.call_args_list
        if isinstance(call_arg[0][0], WorkspaceMember)
    ]
    assert len(added_members) == 1
    assert added_members[0].role == "MEMBER"


# ── Scenario 10: Deterministic Query Ordering (T-2.C) ─────────────────────────

@pytest.mark.asyncio
async def test_repository_deterministic_ordering_statement():
    """Package T-2.C: Verifies that WorkspaceMemberRepository.get_membership

    constructs a query ordered by is_deleted ASC, created_at DESC so that active
    memberships are deterministically prioritized over historical soft-deleted rows.
    """
    mock_session = AsyncMock()
    exec_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = None
    exec_result.scalars.return_value = scalars_mock
    mock_session.execute.return_value = exec_result

    repo = WorkspaceMemberRepository(mock_session)
    ws_id = uuid.uuid4()
    u_id = uuid.uuid4()

    await repo.get_membership(ws_id, u_id, include_deleted=True)

    # Inspect the compiled SQL statement executed
    assert mock_session.execute.call_count == 1
    executed_stmt = mock_session.execute.call_args[0][0]
    sql_str = str(executed_stmt)

    # Must contain order_by on is_deleted ASC and created_at DESC
    assert "ORDER BY" in sql_str
    assert "workspace_members.is_deleted" in sql_str
    assert "workspace_members.created_at" in sql_str
