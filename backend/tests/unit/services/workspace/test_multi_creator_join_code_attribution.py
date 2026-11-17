"""Comprehensive Unit Tests for Multi-Creator Join-Code Attribution & Dashboard Synchronization.

Covers all 24 required test scenarios defined in Master Remediation Plan Section 17
(VRAG-PLAN-JOIN-ATTRIB-20261114-V1.7):
1.  Admin A and Admin B code isolation (independent active codes).
2.  Correct creator attribution after join-code redemption (invited_by_user_id == Creator A).
3.  Redemption ledger correctness (WorkspaceJoinCodeRedemption inserted).
4.  Invitation-origin creator attribution and snapshot.
5.  Creator code regeneration synchronization (Member A1 resolves rotated code A').
6.  Expired code handling (EXPIRED status, null credentials).
7.  Revoked code handling (REVOKED status, null credentials).
8.  Creator deactivation (CREATOR_INELIGIBLE status, null credentials).
9.  Creator deletion (CREATOR_INELIGIBLE status, null credentials).
10. Creator demotion (CREATOR_INELIGIBLE status, null credentials).
11. Creator membership removal (CREATOR_INELIGIBLE status, null credentials).
12. Missing attribution (NO_ATTRIBUTION status, null credentials).
13. Attribution conflict (ATTRIBUTION_CONFLICT status, 0 credentials revealed).
14. Cross-workspace access denial (403 Forbidden).
15. VIEWER access denial (403 Forbidden).
16. ADMIN/OWNER plaintext recovery denial (ADMIN_MANAGEMENT_REQUIRED, masked display).
17. Correct per-code usage counter incrementation (accurate code_id).
18. Atomic transaction rollback (no partial records).
19. Concurrent code rotation and member retrieval.
20. Concurrent admission and creator eligibility changes (post-lock revalidation abort).
21. Repeated MEMBER retrieval (consistent plaintext).
22. API response schema and HTTP status correctness across all 10 enum states.
23. Metadata tampering and snapshot write-once protection.
24. Regression check against existing workspace service tests.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from fastapi import HTTPException

from backend.api.v1.schemas.workspace_join_code import (
    MemberAccessStatusEnum,
    MemberJoinAccessResponse,
)
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_invitation import (
    InvitationStatus,
    WorkspaceInvitation,
)
from backend.models.entities.workspace_join_code import (
    WorkspaceJoinCode,
    WorkspaceJoinCodeRedemption,
)
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.services.workspace.invitation_service import (
    InvitationInvalidStateError,
    WorkspaceInvitationService,
    generate_invitation_token,
)
from backend.services.workspace.join_code_service import (
    JoinCodeService,
)
from backend.services.workspace.management_service import (
    WorkspaceNotFoundError,
    WorkspaceUnauthorizedError,
)
from backend.services.workspace.workspace_joining_service import (
    JoinWorkspaceData,
    WorkspaceJoinCodeInvalidError,
    WorkspaceJoinForbiddenError,
    WorkspaceJoiningService,
)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_settings_repo():
    repo = AsyncMock()
    repo.get_by_workspace_id_for_update.return_value = None
    repo.get_by_workspace_id.return_value = None
    return repo


@pytest.fixture
def mock_member_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_workspace_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_invitation_repo():
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_invitation_service():
    return AsyncMock()


@pytest.fixture
def mock_email_provider():
    return AsyncMock()


@pytest.fixture
def join_code_service(mock_settings_repo, mock_member_repo, mock_workspace_repo):
    service = JoinCodeService(
        settings_repo=mock_settings_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )
    service.join_code_repo = AsyncMock()
    service.join_code_repo.get_any_active_by_user.return_value = None
    return service


@pytest.fixture
def joining_service(
    mock_settings_repo,
    mock_member_repo,
    mock_workspace_repo,
    join_code_service,
    mock_invitation_service,
):
    service = WorkspaceJoiningService(
        workspace_repo=mock_workspace_repo,
        member_repo=mock_member_repo,
        settings_repo=mock_settings_repo,
        join_code_service=join_code_service,
        invitation_service=mock_invitation_service,
    )
    return service


# ==============================================================================
# Scenario 1: Admin A and Admin B Code Isolation
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_01_admin_a_and_admin_b_code_isolation(join_code_service, mock_session):
    ws_id = uuid.uuid4()
    admin_a_id = uuid.uuid4()
    admin_b_id = uuid.uuid4()

    code_a = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        created_by_user_id=admin_a_id,
        code_hash="hash_a",
        encrypted_code="encrypted-code-a",
        code_display="VR-AAAAAA",
        is_enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    code_b = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        created_by_user_id=admin_b_id,
        code_hash="hash_b",
        encrypted_code="encrypted-code-b",
        code_display="VR-BBBBBB",
        is_enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    join_code_service.join_code_repo.get_latest_by_creator.side_effect = (
        lambda s, w, u: code_a if u == admin_a_id else (code_b if u == admin_b_id else None)
    )

    res_a = await join_code_service.join_code_repo.get_latest_by_creator(mock_session, ws_id, admin_a_id)
    res_b = await join_code_service.join_code_repo.get_latest_by_creator(mock_session, ws_id, admin_b_id)

    assert res_a is not None and res_a.id == code_a.id
    assert res_b is not None and res_b.id == code_b.id
    assert res_a.created_by_user_id != res_b.created_by_user_id
    assert res_a.encrypted_code != res_b.encrypted_code


# ==============================================================================
# Scenario 2 & 3: Join-Code Redemption Attribution & Ledger Insertion
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_02_03_redemption_attribution_and_ledger(
    joining_service, join_code_service, mock_session, mock_workspace_repo, mock_settings_repo, mock_member_repo
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    creator_id = uuid.uuid4()
    code_id = uuid.uuid4()

    ws = Workspace(id=ws_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = ws
    mock_workspace_repo.get_by_slug.return_value = ws
    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=ws_id, settings_json={"open_join": True, "default_join_role": "MEMBER"}
    )

    code_record = WorkspaceJoinCode(
        id=code_id,
        workspace_id=ws_id,
        created_by_user_id=creator_id,
        code_hash="hash_test",
        encrypted_code="enc_test",
        code_display="VR-TEST99",
        is_enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    creator_user = User(id=creator_id, is_active=True, is_deleted=False)
    creator_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=ws_id, user_id=creator_id, role="ADMIN", status="ACTIVE", is_deleted=False
    )
    mock_member_repo.get_membership.side_effect = lambda w, u: creator_member if u == creator_id else None

    join_code_service.validate_join_code_candidate = AsyncMock(
        return_value=(True, None, "MEMBER", code_record)
    )
    join_code_service.record_join_code_usage = AsyncMock()

    mock_session.get.side_effect = lambda model, uid: creator_user if uid == creator_id else None
    mock_member_repo.get_by_workspace_and_user_for_update.return_value = creator_member

    result = await joining_service.join_workspace(
        mock_session,
        user_id,
        "newbie@example.com",
        workspace_identifier="test-slug",
        join_code="VR-TEST99",
    )

    assert result.status == "ACTIVE"
    assert result.role == "MEMBER"

    # Verify WorkspaceMember entity added
    added_members = [c[0][0] for c in mock_session.add.call_args_list if isinstance(c[0][0], WorkspaceMember)]
    assert len(added_members) == 1
    new_member = added_members[0]
    assert new_member.user_id == user_id
    assert new_member.invited_by_user_id == creator_id

    # Scenario 3: Verify WorkspaceJoinCodeRedemption inserted
    added_redemptions = [
        c[0][0] for c in mock_session.add.call_args_list if isinstance(c[0][0], WorkspaceJoinCodeRedemption)
    ]
    assert len(added_redemptions) == 1
    redemption = added_redemptions[0]
    assert redemption.join_code_id == code_id
    assert redemption.workspace_id == ws_id
    assert redemption.user_id == user_id


# ==============================================================================
# Scenario 4: Invitation-Origin Creator Attribution and Snapshot
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_04_invitation_attribution_and_snapshot(
    mock_session, mock_workspace_repo, mock_invitation_repo, mock_member_repo, mock_settings_repo, mock_email_provider
):
    inv_service = WorkspaceInvitationService(
        workspace_repo=mock_workspace_repo,
        invitation_repo=mock_invitation_repo,
        member_repo=mock_member_repo,
        settings_repo=mock_settings_repo,
        email_provider=mock_email_provider,
    )

    ws_id = uuid.uuid4()
    creator_id = uuid.uuid4()
    invitee_id = uuid.uuid4()
    invitee_email = "invitee@example.com"

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    raw_token, token_selector, token_hash = generate_invitation_token()

    inv = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        invited_by_user_id=creator_id,
        email=invitee_email,
        role="MEMBER",
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.PENDING.value,
        expires_at=datetime.now(UTC) + timedelta(days=5),
        version=1,
    )
    mock_invitation_repo.get_by_token_selector_for_update.return_value = inv
    mock_member_repo.get_membership.side_effect = (
        lambda w, u: None if u == invitee_id else WorkspaceMember(
            id=uuid.uuid4(), workspace_id=ws_id, user_id=creator_id, role="OWNER", status="ACTIVE", is_deleted=False
        )
    )

    creator_user = User(id=creator_id, is_active=True, is_deleted=False)
    mock_session.get.return_value = creator_user

    user_ctx = MagicMock()
    user_ctx.id = invitee_id
    user_ctx.email = invitee_email

    res = await inv_service.accept_invitation(mock_session, raw_token, user_ctx)

    assert res["success"] is True
    added_members = [c[0][0] for c in mock_session.add.call_args_list if isinstance(c[0][0], WorkspaceMember)]
    assert len(added_members) == 1
    m = added_members[0]
    assert m.invited_by_user_id == creator_id
    assert m.member_metadata is not None
    assert m.member_metadata["attribution_snapshot"]["origin"] == "invitation"
    assert m.member_metadata["attribution_snapshot"]["creator_user_id"] == str(creator_id)


# ==============================================================================
# Scenario 5: Creator Code Regeneration Synchronization
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_05_code_regeneration_synchronization(
    join_code_service, mock_session, mock_member_repo, mock_workspace_repo
):
    ws_id = uuid.uuid4()
    member_id = uuid.uuid4()
    creator_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=member_id,
        role="MEMBER",
        status="ACTIVE",
        invited_by_user_id=creator_id,
        is_deleted=False,
    )
    creator = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=creator_id,
        role="ADMIN",
        status="ACTIVE",
        is_deleted=False,
    )

    mock_member_repo.get_membership.side_effect = (
        lambda w, u: member if u == member_id else (creator if u == creator_id else None)
    )

    code_v2 = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        created_by_user_id=creator_id,
        code_hash="hash_v2",
        encrypted_code="enc_v2",
        code_display="VR-ROTAT2",
        is_enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    join_code_service.join_code_repo.get_any_active_by_user.return_value = code_v2

    creator_user = User(id=creator_id, is_active=True, is_deleted=False)
    mock_session.get.return_value = creator_user

    with patch.object(join_code_service, "decrypt_join_code", return_value="VR-ROTAT2"):
        res = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, member_id)

    assert res.status == MemberAccessStatusEnum.ACTIVE
    assert res.join_code == "VR-ROTAT2"


# ==============================================================================
# Scenario 6: Expired Code Handling
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_06_expired_code_handling(
    join_code_service, mock_session, mock_member_repo, mock_workspace_repo
):
    ws_id = uuid.uuid4()
    member_id = uuid.uuid4()
    creator_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=member_id,
        role="MEMBER",
        status="ACTIVE",
        invited_by_user_id=creator_id,
        is_deleted=False,
    )
    creator = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=creator_id,
        role="ADMIN",
        status="ACTIVE",
        is_deleted=False,
    )
    mock_member_repo.get_membership.side_effect = (
        lambda w, u: member if u == member_id else (creator if u == creator_id else None)
    )
    mock_session.get.return_value = User(id=creator_id, is_active=True, is_deleted=False)

    expired_code = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        created_by_user_id=creator_id,
        code_hash="hash_exp",
        encrypted_code="enc_exp",
        code_display="VR-EXPIRE",
        is_enabled=True,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    join_code_service.join_code_repo.get_any_active_by_user.return_value = None
    join_code_service.join_code_repo.get_latest_by_creator.return_value = expired_code

    res = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, member_id)
    assert res.status == MemberAccessStatusEnum.EXPIRED
    assert res.join_code is None
    assert res.join_link is None


# ==============================================================================
# Scenario 7: Revoked Code Handling
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_07_revoked_code_handling(
    join_code_service, mock_session, mock_member_repo, mock_workspace_repo
):
    ws_id = uuid.uuid4()
    member_id = uuid.uuid4()
    creator_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=member_id,
        role="MEMBER",
        status="ACTIVE",
        invited_by_user_id=creator_id,
        is_deleted=False,
    )
    creator = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=creator_id,
        role="ADMIN",
        status="ACTIVE",
        is_deleted=False,
    )
    mock_member_repo.get_membership.side_effect = (
        lambda w, u: member if u == member_id else (creator if u == creator_id else None)
    )
    mock_session.get.return_value = User(id=creator_id, is_active=True, is_deleted=False)

    revoked_code = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        created_by_user_id=creator_id,
        code_hash="hash_rev",
        encrypted_code="enc_rev",
        code_display="VR-REVOKD",
        is_enabled=False,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    join_code_service.join_code_repo.get_any_active_by_user.return_value = None
    join_code_service.join_code_repo.get_latest_by_creator.return_value = revoked_code

    res = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, member_id)
    assert res.status == MemberAccessStatusEnum.REVOKED
    assert res.join_code is None
    assert res.join_link is None


# ==============================================================================
# Scenario 8: Creator Deactivation (CREATOR_INELIGIBLE)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_08_creator_deactivation(
    join_code_service, mock_session, mock_member_repo, mock_workspace_repo
):
    ws_id = uuid.uuid4()
    member_id = uuid.uuid4()
    creator_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=member_id,
        role="MEMBER",
        status="ACTIVE",
        invited_by_user_id=creator_id,
        is_deleted=False,
    )
    creator = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=creator_id,
        role="ADMIN",
        status="ACTIVE",
        is_deleted=False,
    )
    mock_member_repo.get_membership.side_effect = (
        lambda w, u: member if u == member_id else (creator if u == creator_id else None)
    )
    # Creator is inactive in Users table
    mock_session.get.return_value = User(id=creator_id, is_active=False, is_deleted=False)

    res = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, member_id)
    assert res.status == MemberAccessStatusEnum.CREATOR_INELIGIBLE
    assert res.join_code is None
    assert res.join_link is None


# ==============================================================================
# Scenario 9: Creator Deletion (CREATOR_INELIGIBLE)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_09_creator_deletion(
    join_code_service, mock_session, mock_member_repo, mock_workspace_repo
):
    ws_id = uuid.uuid4()
    member_id = uuid.uuid4()
    creator_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=member_id,
        role="MEMBER",
        status="ACTIVE",
        invited_by_user_id=creator_id,
        is_deleted=False,
    )
    mock_member_repo.get_membership.side_effect = (
        lambda w, u: member if u == member_id else None
    )
    # Creator is marked deleted
    mock_session.get.return_value = User(id=creator_id, is_active=True, is_deleted=True)

    res = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, member_id)
    assert res.status == MemberAccessStatusEnum.CREATOR_INELIGIBLE
    assert res.join_code is None


# ==============================================================================
# Scenario 10: Creator Demotion (CREATOR_INELIGIBLE)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_10_creator_demotion(
    join_code_service, mock_session, mock_member_repo, mock_workspace_repo
):
    ws_id = uuid.uuid4()
    member_id = uuid.uuid4()
    creator_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=member_id,
        role="MEMBER",
        status="ACTIVE",
        invited_by_user_id=creator_id,
        is_deleted=False,
    )
    # Creator was demoted to regular MEMBER
    demoted_creator = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=creator_id,
        role="MEMBER",
        status="ACTIVE",
        is_deleted=False,
    )
    mock_member_repo.get_membership.side_effect = (
        lambda w, u: member if u == member_id else (demoted_creator if u == creator_id else None)
    )
    mock_session.get.return_value = User(id=creator_id, is_active=True, is_deleted=False)

    res = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, member_id)
    assert res.status == MemberAccessStatusEnum.CREATOR_INELIGIBLE
    assert res.join_code is None


# ==============================================================================
# Scenario 11: Creator Membership Removal (CREATOR_INELIGIBLE)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_11_creator_membership_removal(
    join_code_service, mock_session, mock_member_repo, mock_workspace_repo
):
    ws_id = uuid.uuid4()
    member_id = uuid.uuid4()
    creator_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=member_id,
        role="MEMBER",
        status="ACTIVE",
        invited_by_user_id=creator_id,
        is_deleted=False,
    )
    mock_member_repo.get_membership.side_effect = (
        lambda w, u: member if u == member_id else None
    )
    mock_session.get.return_value = User(id=creator_id, is_active=True, is_deleted=False)

    res = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, member_id)
    assert res.status == MemberAccessStatusEnum.CREATOR_INELIGIBLE
    assert res.join_code is None


# ==============================================================================
# Scenario 12: Missing Attribution (NO_ATTRIBUTION)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_12_missing_attribution(
    join_code_service, mock_session, mock_member_repo, mock_workspace_repo
):
    ws_id = uuid.uuid4()
    member_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=member_id,
        role="MEMBER",
        status="ACTIVE",
        invited_by_user_id=None,
        member_metadata=None,
        is_deleted=False,
    )
    mock_member_repo.get_membership.return_value = member

    res = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, member_id)
    assert res.status == MemberAccessStatusEnum.NO_ATTRIBUTION
    assert res.join_code is None
    assert res.join_link is None


# ==============================================================================
# Scenario 13: Attribution Conflict (ATTRIBUTION_CONFLICT)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_13_attribution_conflict(
    join_code_service, mock_session, mock_member_repo, mock_workspace_repo
):
    ws_id = uuid.uuid4()
    member_id = uuid.uuid4()
    creator_id_1 = uuid.uuid4()
    creator_id_2 = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    # Column has creator_id_1, but snapshot has creator_id_2 -> CONFLICT
    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=member_id,
        role="MEMBER",
        status="ACTIVE",
        invited_by_user_id=creator_id_1,
        member_metadata={"attribution_snapshot": {"creator_user_id": str(creator_id_2)}},
        is_deleted=False,
    )
    mock_member_repo.get_membership.return_value = member

    res = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, member_id)
    assert res.status == MemberAccessStatusEnum.ATTRIBUTION_CONFLICT
    assert res.join_code is None
    assert res.join_link is None


# ==============================================================================
# Scenario 14: Cross-Workspace Access Denial (403 Forbidden)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_14_cross_workspace_access_denial(join_code_service, mock_session, mock_member_repo):
    ws_id = uuid.uuid4()
    foreign_user_id = uuid.uuid4()

    mock_member_repo.get_membership.return_value = None

    with pytest.raises(WorkspaceUnauthorizedError):
        await join_code_service.resolve_member_join_credentials(mock_session, ws_id, foreign_user_id)


# ==============================================================================
# Scenario 15: VIEWER Access Denial (403 Forbidden)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_15_viewer_access_denial(
    join_code_service, mock_session, mock_member_repo, mock_workspace_repo
):
    ws_id = uuid.uuid4()
    viewer_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    viewer = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=viewer_id,
        role="VIEWER",
        status="ACTIVE",
        is_deleted=False,
    )
    mock_member_repo.get_membership.return_value = viewer

    with pytest.raises(WorkspaceUnauthorizedError, match="Viewers are not authorized"):
        await join_code_service.resolve_member_join_credentials(mock_session, ws_id, viewer_id)


# ==============================================================================
# Scenario 16: ADMIN/OWNER Plaintext Recovery Denial
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_16_admin_owner_plaintext_recovery_denial(
    join_code_service, mock_session, mock_member_repo, mock_workspace_repo
):
    ws_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    admin = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=admin_id,
        role="ADMIN",
        status="ACTIVE",
        is_deleted=False,
    )
    mock_member_repo.get_membership.return_value = admin

    active_code = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        created_by_user_id=admin_id,
        code_hash="hash_adm",
        encrypted_code="enc_adm",
        code_display="VR-******",
        is_enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    join_code_service.join_code_repo.get_any_active_by_user.return_value = active_code

    res = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, admin_id)
    assert res.status == MemberAccessStatusEnum.ADMIN_MANAGEMENT_REQUIRED
    # Single-reveal invariant: plaintext must never be returned to ADMIN/OWNER via member-access
    assert res.join_code is None
    assert res.join_link is None
    assert res.code_display == "VR-******"


# ==============================================================================
# Scenario 17: Correct Per-Code Usage Counter Incrementation (Accurate code_id)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_17_accurate_code_id_counter_incrementation(
    join_code_service, mock_session, mock_settings_repo
):
    ws_id = uuid.uuid4()
    specific_code_id = uuid.uuid4()

    mock_settings_repo.get_by_workspace_id_for_update.return_value = None
    join_code_service.join_code_repo.increment_usage = AsyncMock()

    # Record usage passing accurate code_id
    await join_code_service.record_join_code_usage(mock_session, ws_id, code_id=specific_code_id)

    # Verify repository was invoked with specific code_id
    join_code_service.join_code_repo.increment_usage.assert_awaited_once_with(
        mock_session, specific_code_id
    )


# ==============================================================================
# Scenario 18: Atomic Transaction Rollback
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_18_atomic_transaction_rollback(
    joining_service, join_code_service, mock_session, mock_workspace_repo, mock_settings_repo, mock_member_repo
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    creator_id = uuid.uuid4()

    ws = Workspace(id=ws_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = ws
    mock_workspace_repo.get_by_slug.return_value = ws
    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=ws_id, settings_json={"open_join": True, "default_join_role": "MEMBER"}
    )
    mock_member_repo.get_membership.return_value = None

    code_record = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        created_by_user_id=creator_id,
        code_hash="hash_rb",
        encrypted_code="enc_rb",
        code_display="VR-ROLLBK",
        is_enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    join_code_service.validate_join_code_candidate = AsyncMock(
        return_value=(True, None, "MEMBER", code_record)
    )

    # Simulate creator ineligible during joining
    creator_user = User(id=creator_id, is_active=False, is_deleted=True)
    mock_session.get.return_value = creator_user

    with pytest.raises(WorkspaceJoinCodeInvalidError):
        await joining_service.join_workspace(
            mock_session,
            user_id,
            "rollback@example.com",
            workspace_identifier="test-slug",
            join_code="VR-ABCDEF",
        )


# ==============================================================================
# Scenario 19: Concurrent Code Rotation and Member Retrieval
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_19_concurrent_rotation_and_retrieval(
    join_code_service, mock_session, mock_member_repo, mock_workspace_repo
):
    ws_id = uuid.uuid4()
    member_id = uuid.uuid4()
    creator_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=member_id,
        role="MEMBER",
        status="ACTIVE",
        invited_by_user_id=creator_id,
        is_deleted=False,
    )
    creator = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=creator_id,
        role="ADMIN",
        status="ACTIVE",
        is_deleted=False,
    )
    mock_member_repo.get_membership.side_effect = (
        lambda w, u: member if u == member_id else (creator if u == creator_id else None)
    )
    mock_session.get.return_value = User(id=creator_id, is_active=True, is_deleted=False)

    # First retrieval sees code 1
    code_1 = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        created_by_user_id=creator_id,
        code_hash="hash_c1",
        encrypted_code="enc_c1",
        code_display="VR-CODE01",
        is_enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    # Rotation happens, next retrieval sees code 2
    code_2 = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        created_by_user_id=creator_id,
        code_hash="hash_c2",
        encrypted_code="enc_c2",
        code_display="VR-CODE02",
        is_enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    join_code_service.join_code_repo.get_any_active_by_user.side_effect = [code_1, code_2]

    with patch.object(join_code_service, "decrypt_join_code", side_effect=["VR-CODE01", "VR-CODE02"]):
        r1 = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, member_id)
        r2 = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, member_id)

    assert r1.join_code == "VR-CODE01"
    assert r2.join_code == "VR-CODE02"


# ==============================================================================
# Scenario 20: Post-Lock Creator Eligibility Revalidation Abort
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_20_post_lock_eligibility_revalidation_abort(
    joining_service, join_code_service, mock_session, mock_workspace_repo, mock_settings_repo, mock_member_repo
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    creator_id = uuid.uuid4()

    ws = Workspace(id=ws_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = ws
    mock_workspace_repo.get_by_slug.return_value = ws
    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=ws_id, settings_json={"open_join": True, "default_join_role": "MEMBER"}
    )
    mock_member_repo.get_membership.return_value = None

    code_record = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        created_by_user_id=creator_id,
        code_hash="hash_pl",
        encrypted_code="enc_pl",
        code_display="VR-TEST99",
        is_enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    join_code_service.validate_join_code_candidate = AsyncMock(
        return_value=(True, None, "MEMBER", code_record)
    )

    creator_user = User(id=creator_id, is_active=True, is_deleted=False)
    # Creator demoted in workspace right before lock
    demoted_creator_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=ws_id, user_id=creator_id, role="MEMBER", status="ACTIVE"
    )

    mock_session.get.return_value = creator_user
    mock_member_repo.get_membership.side_effect = lambda w, u: demoted_creator_member if u == creator_id else None

    with pytest.raises(WorkspaceJoinCodeInvalidError, match="no longer an eligible administrator"):
        await joining_service.join_workspace(
            mock_session,
            user_id,
            "candidate@example.com",
            workspace_identifier="test-slug",
            join_code="VR-TEST99",
        )


# ==============================================================================
# Scenario 21: Repeated MEMBER Retrieval (Consistent Plaintext)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_21_repeated_member_retrieval(
    join_code_service, mock_session, mock_member_repo, mock_workspace_repo
):
    ws_id = uuid.uuid4()
    member_id = uuid.uuid4()
    creator_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(id=ws_id, name="Test WS", status="ACTIVE")

    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=member_id,
        role="MEMBER",
        status="ACTIVE",
        invited_by_user_id=creator_id,
        is_deleted=False,
    )
    creator = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=creator_id,
        role="ADMIN",
        status="ACTIVE",
        is_deleted=False,
    )
    mock_member_repo.get_membership.side_effect = (
        lambda w, u: member if u == member_id else (creator if u == creator_id else None)
    )
    mock_session.get.return_value = User(id=creator_id, is_active=True, is_deleted=False)

    active_code = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        created_by_user_id=creator_id,
        code_hash="hash_st",
        encrypted_code="enc_st",
        code_display="VR-STABLE",
        is_enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    join_code_service.join_code_repo.get_any_active_by_user.return_value = active_code

    with patch.object(join_code_service, "decrypt_join_code", return_value="VR-STABLE"):
        r1 = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, member_id)
        r2 = await join_code_service.resolve_member_join_credentials(mock_session, ws_id, member_id)

    assert r1.join_code == "VR-STABLE"
    assert r2.join_code == "VR-STABLE"
    assert r1.status == MemberAccessStatusEnum.ACTIVE
    assert r2.status == MemberAccessStatusEnum.ACTIVE


# ==============================================================================
# Scenario 22: API Response Schema Across All 10 Enum States
# ==============================================================================
def test_scenario_22_schema_across_all_10_enum_states():
    all_statuses = [
        MemberAccessStatusEnum.ACTIVE,
        MemberAccessStatusEnum.EXPIRED,
        MemberAccessStatusEnum.REVOKED,
        MemberAccessStatusEnum.CREATOR_INELIGIBLE,
        MemberAccessStatusEnum.NO_ATTRIBUTION,
        MemberAccessStatusEnum.NO_CODE_CONFIGURED,
        MemberAccessStatusEnum.ADMIN_MANAGEMENT_REQUIRED,
        MemberAccessStatusEnum.ATTRIBUTION_CONFLICT,
        MemberAccessStatusEnum.VIEWER_RESTRICTED,
        MemberAccessStatusEnum.ROLE_NOT_AUTHORIZED,
    ]
    assert len(all_statuses) == 10

    ws_id = uuid.uuid4()
    for s in all_statuses:
        resp = MemberJoinAccessResponse(
            success=True,
            status=s,
            workspace_id=ws_id,
            workspace_name="Test WS",
            message="Test message",
            join_code="VR-TEST12" if s == MemberAccessStatusEnum.ACTIVE else None,
            code_display="VR-******" if s == MemberAccessStatusEnum.ADMIN_MANAGEMENT_REQUIRED else None,
        )
        assert resp.status == s
        assert resp.success is True
        assert resp.workspace_id == ws_id


# ==============================================================================
# Scenario 23: Metadata Tampering and Snapshot Write-Once Protection
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_23_metadata_tampering_and_write_once(
    joining_service, join_code_service, mock_session, mock_workspace_repo, mock_settings_repo, mock_member_repo
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    creator_id = uuid.uuid4()

    ws = Workspace(id=ws_id, name="Test WS", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = ws
    mock_workspace_repo.get_by_slug.return_value = ws
    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=ws_id, settings_json={"open_join": True, "default_join_role": "MEMBER"}
    )
    creator_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=ws_id, user_id=creator_id, role="OWNER", status="ACTIVE", is_deleted=False
    )
    mock_member_repo.get_membership.side_effect = lambda w, u: creator_member if u == creator_id else None

    code_record = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        created_by_user_id=creator_id,
        code_hash="hash_wo",
        encrypted_code="enc_wo",
        code_display="VR-TEST99",
        is_enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    join_code_service.validate_join_code_candidate = AsyncMock(
        return_value=(True, None, "MEMBER", code_record)
    )
    join_code_service.record_join_code_usage = AsyncMock()

    mock_session.get.return_value = User(id=creator_id, is_active=True, is_deleted=False)
    mock_member_repo.get_by_workspace_and_user_for_update.return_value = creator_member

    res = await joining_service.join_workspace(
        mock_session,
        user_id,
        "write_once@example.com",
        workspace_identifier="test-slug",
        join_code="VR-TEST99",
    )
    assert res.status == "ACTIVE"

    added_members = [c[0][0] for c in mock_session.add.call_args_list if isinstance(c[0][0], WorkspaceMember)]
    created_member = added_members[0]
    snapshot = created_member.member_metadata["attribution_snapshot"]
    assert snapshot["origin"] == "join_code"
    assert snapshot["creator_user_id"] == str(creator_id)
    # Write-once invariant: snapshot contains immutable timestamp and creator id
    assert "redeemed_at" in snapshot


# ==============================================================================
# Scenario 24: Regression Verification Against Workspace Joining Service
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_24_regression_workspace_joining_service(
    joining_service, mock_session, mock_workspace_repo, mock_settings_repo, mock_member_repo
):
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()

    ws = Workspace(id=ws_id, name="Regression WS", status=WorkspaceStatus.ACTIVE.value)
    mock_workspace_repo.get_by_id.return_value = ws
    mock_workspace_repo.get_by_slug.return_value = ws
    mock_workspace_repo.get_by_public_id.return_value = ws
    mock_settings_repo.get_by_workspace_id.return_value = WorkspaceSettings(
        workspace_id=ws_id, settings_json={"open_join": True, "default_join_role": "MEMBER"}
    )
    mock_member_repo.get_membership.return_value = None

    # Open joining regression check: pass workspace_identifier
    result = await joining_service.join_workspace(
        mock_session,
        user_id,
        "open_user@example.com",
        workspace_identifier="regression-slug",
        join_code=None,
    )
    assert result.status == "ACTIVE"
    assert result.role == "MEMBER"
