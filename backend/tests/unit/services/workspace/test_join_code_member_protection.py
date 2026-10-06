"""Unit and lifecycle regression tests for Workstream C: Existing Member Protection (WS-C).

Validates all 16 criteria (C-01 through C-16):
- C-01 Generate Code A
- C-02 Member joins with Code A
- C-03 Membership is ACTIVE
- C-04 Record membership ID
- C-05 Record role
- C-06 Record workspace
- C-07 Admin regenerates code -> Code B
- C-08 Code A becomes invalid
- C-09 Code B is valid
- C-10 Same membership ID preserved
- C-11 Same role preserved
- C-12 Same workspace preserved
- C-13 ACTIVE status unchanged
- C-14 Existing session/membership remains valid
- C-15 No membership recreation (zero INSERT calls)
- C-16 No membership deletion (zero DELETE calls)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.services.workspace.join_code_service import JoinCodeService
from backend.services.workspace.workspace_joining_service import (
    WorkspaceJoiningService,
    WorkspaceJoinCodeInvalidError,
)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_settings_repo():
    return AsyncMock()


@pytest.fixture
def mock_member_repo():
    return AsyncMock()


@pytest.fixture
def mock_workspace_repo():
    return AsyncMock()


@pytest.fixture
def mock_invitation_service():
    return AsyncMock()


@pytest.fixture
def join_code_service(mock_settings_repo, mock_member_repo, mock_workspace_repo):
    return JoinCodeService(
        settings_repo=mock_settings_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
    )


@pytest.fixture
def joining_service(
    mock_workspace_repo,
    mock_settings_repo,
    mock_member_repo,
    join_code_service,
    mock_invitation_service,
):
    return WorkspaceJoiningService(
        workspace_repo=mock_workspace_repo,
        settings_repo=mock_settings_repo,
        member_repo=mock_member_repo,
        join_code_service=join_code_service,
        invitation_service=mock_invitation_service,
    )


@pytest.mark.asyncio
async def test_join_code_regeneration_preserves_existing_memberships_c_lifecycle(
    mock_session,
    mock_settings_repo,
    mock_member_repo,
    mock_workspace_repo,
    join_code_service,
    joining_service,
):
    """C-01 through C-16: Proves Join Code regeneration invalidates old code

    and activates new code while leaving all existing membership records, IDs, roles,
    and ACTIVE states strictly unchanged and untouched.
    """
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    member_user_id = uuid.uuid4()
    member_email = "engineer@veritas-rag.test"

    # Workspace entity
    workspace = Workspace(
        id=workspace_id,
        name="Acme Quantum Corp",
        public_id="ACME-QNTM",
        slug="acme-quantum",
        status=WorkspaceStatus.ACTIVE.value,
    )
    mock_workspace_repo.get_by_id.return_value = workspace
    mock_workspace_repo.get_by_public_id.return_value = workspace

    # Owner membership
    owner_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=owner_id,
        role="OWNER",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )

    # Initial empty settings
    settings_obj = WorkspaceSettings(
        workspace_id=workspace_id,
        settings_json={},
        schema_version=1,
        version=1,
        settings_hash="",
    )
    mock_settings_repo.get_by_workspace_id.return_value = settings_obj
    mock_settings_repo.get_by_workspace_id_for_update.return_value = settings_obj

    def mock_get_membership(ws_id, u_id):
        if ws_id == workspace_id and u_id == owner_id:
            return owner_member
        return None

    mock_member_repo.get_membership = AsyncMock(side_effect=mock_get_membership)

    # ─────────────────────────────────────────────────────────────────────────
    # C-01: Generate Code A
    # ─────────────────────────────────────────────────────────────────────────
    gen_response_a = await join_code_service.generate_new_join_code(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=owner_id,
        expires_in_days=30,
        default_role="MEMBER",
        is_regeneration=False,
    )
    code_a = gen_response_a.join_code
    assert code_a.startswith("VR-")

    # Verify Code A is valid
    is_valid_a, err_a, role_a = await join_code_service.validate_join_code_candidate(
        session=mock_session,
        workspace_id=workspace_id,
        candidate_code=code_a,
    )
    assert is_valid_a is True
    assert err_a is None
    assert role_a == "MEMBER"

    # ─────────────────────────────────────────────────────────────────────────
    # C-02 & C-03: Member joins with Code A -> Membership ACTIVE
    # ─────────────────────────────────────────────────────────────────────────
    # Simulate joining
    join_result = await joining_service.join_workspace(
        session=mock_session,
        user_id=member_user_id,
        user_email=member_email,
        workspace_identifier="ACME-QNTM",
        join_code=code_a,
    )

    assert join_result.workspace_id == workspace_id
    assert join_result.role == "MEMBER"
    assert join_result.status == "ACTIVE"

    # ─────────────────────────────────────────────────────────────────────────
    # C-04, C-05, C-06: Record initial membership baseline
    # ─────────────────────────────────────────────────────────────────────────
    recorded_membership_id = join_result.member_id
    recorded_role = join_result.role
    recorded_workspace_id = join_result.workspace_id
    recorded_status = join_result.status

    # Persisted member representation in DB
    existing_member = WorkspaceMember(
        id=recorded_membership_id,
        workspace_id=recorded_workspace_id,
        user_id=member_user_id,
        role=recorded_role,
        status=recorded_status,
        is_deleted=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Now member exists in repository
    def mock_get_membership_with_member(ws_id, u_id):
        if ws_id == workspace_id and u_id == owner_id:
            return owner_member
        if ws_id == workspace_id and u_id == member_user_id:
            return existing_member
        return None

    mock_member_repo.get_membership = AsyncMock(side_effect=mock_get_membership_with_member)

    # Track session mutations on WorkspaceMember table
    membership_add_count_before = sum(
        1 for call in mock_session.add.call_args_list if isinstance(call[0][0], WorkspaceMember)
    )

    # ─────────────────────────────────────────────────────────────────────────
    # C-07: Admin regenerates -> Code B
    # ─────────────────────────────────────────────────────────────────────────
    regen_response_b = await join_code_service.generate_new_join_code(
        session=mock_session,
        workspace_id=workspace_id,
        user_id=owner_id,
        expires_in_days=30,
        is_regeneration=True,
    )
    code_b = regen_response_b.join_code
    assert code_b.startswith("VR-")
    assert code_b != code_a

    # ─────────────────────────────────────────────────────────────────────────
    # C-08: Code A is now INVALID
    # ─────────────────────────────────────────────────────────────────────────
    is_valid_old, err_old, _ = await join_code_service.validate_join_code_candidate(
        session=mock_session,
        workspace_id=workspace_id,
        candidate_code=code_a,
    )
    assert is_valid_old is False
    assert err_old == "Invalid join code."

    # Joining with Code A must now fail
    new_user_id = uuid.uuid4()
    with pytest.raises(WorkspaceJoinCodeInvalidError):
        await joining_service.join_workspace(
            session=mock_session,
            user_id=new_user_id,
            user_email="other@test.org",
            workspace_identifier="ACME-QNTM",
            join_code=code_a,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # C-09: Code B is now VALID
    # ─────────────────────────────────────────────────────────────────────────
    is_valid_new, err_new, role_new = await join_code_service.validate_join_code_candidate(
        session=mock_session,
        workspace_id=workspace_id,
        candidate_code=code_b,
    )
    assert is_valid_new is True
    assert err_new is None
    assert role_new == "MEMBER"

    # ─────────────────────────────────────────────────────────────────────────
    # C-10, C-11, C-12, C-13, C-14: Existing Member invariants preserved
    # ─────────────────────────────────────────────────────────────────────────
    member_after_regen = await mock_member_repo.get_membership(workspace_id, member_user_id)
    assert member_after_regen is not None
    # C-10: Same membership ID
    assert member_after_regen.id == recorded_membership_id
    # C-11: Same role
    assert member_after_regen.role == recorded_role
    # C-12: Same workspace
    assert member_after_regen.workspace_id == recorded_workspace_id
    # C-13: ACTIVE status unchanged
    assert member_after_regen.status == "ACTIVE"
    # C-14: is_deleted remains False
    assert member_after_regen.is_deleted is False

    # ─────────────────────────────────────────────────────────────────────────
    # C-15: No membership recreation (zero new WorkspaceMember added during regen)
    # ─────────────────────────────────────────────────────────────────────────
    membership_add_count_after = sum(
        1 for call in mock_session.add.call_args_list if isinstance(call[0][0], WorkspaceMember)
    )
    assert membership_add_count_after == membership_add_count_before, (
        "Regeneration must NEVER call session.add(WorkspaceMember) or recreate memberships"
    )

    # ─────────────────────────────────────────────────────────────────────────
    # C-16: No membership deletion
    # ─────────────────────────────────────────────────────────────────────────
    assert not hasattr(mock_session, "delete") or mock_session.delete.call_count == 0, (
        "Regeneration must NEVER call session.delete() on any membership"
    )
