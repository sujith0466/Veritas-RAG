"""API Integration Tests for Workspace Ownership Transfers - Section 7, Batch 2.

Governed by Section 7 Batch 2 (V3.0) and ratified Project Owner Decisions:
- WP 7.4: Former OWNER STAY/LEAVE (TC-7.4-01 through TC-7.4-09)
- WP 7.5: New OWNER Role Decision & Action Tickets (TC-7.5-01 through TC-7.5-08)
- WP 7.8: Owner Departure Protection (TC-7.8-01 through TC-7.8-04)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from backend.api.v1.routes.workspace_members import workspace_members_router
from backend.api.v1.routes.workspace_transfers import router as workspace_transfers_router
from backend.api.v1.schemas.workspace_member import WorkspaceMemberData, WorkspaceMemberResponse
from backend.api.v1.schemas.workspace_transfer import OwnershipTransferResponse
from backend.api.v1.workspaces.dependencies import (
    require_active_workspace_member,
    require_active_workspace_owner,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_db,
    get_workspace_membership_service,
)
from backend.core.permissions.rbac import Role
from backend.models.entities.workspace_member import (
    MemberStatus,
    WorkspaceMember,
    WorkspaceRole,
)
from backend.models.entities.workspace_ownership_transfer import (
    DecisionStatus,
    FormerOwnerChoice,
    TransferStatus,
    WorkspaceOwnershipTransfer,
)
from backend.services.workspace.membership_service import (
    MembershipConflictError,
    WorkspaceMembershipService,
)
from backend.services.workspace_transfer_service import WorkspaceTransferService

app = FastAPI()
app.include_router(workspace_transfers_router, prefix="/api/v1")
app.include_router(workspace_members_router, prefix="/api/v1")


def make_user_context(user_id: uuid.UUID, role: Role = Role.VIEWER) -> UserContext:
    return UserContext(
        id=user_id,
        email=f"user_{user_id.hex[:6]}@example.com",
        role=role,
        is_active=True,
        is_verified=True,
    )


def make_batch2_transfer_entity(
    workspace_id: uuid.UUID,
    former_owner_id: uuid.UUID,
    new_owner_id: uuid.UUID,
    transfer_status: str = TransferStatus.ACCEPTED.value,
    former_choice: str = FormerOwnerChoice.PENDING.value,
    decision_status: str = DecisionStatus.PENDING.value,
    deadline_delta_days: int = 30,
) -> WorkspaceOwnershipTransfer:
    now = datetime.now(UTC)
    t = WorkspaceOwnershipTransfer(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        nominated_by_user_id=former_owner_id,
        nominee_user_id=new_owner_id,
        status=transfer_status,
        created_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=6),
        responded_at=now,
        former_owner_choice=former_choice,
        decision_status=decision_status,
        decision_deadline_at=now + timedelta(days=deadline_delta_days),
    )
    t.nominated_by = AsyncMock(
        id=former_owner_id,
        email=f"former_{former_owner_id.hex[:4]}@test.com",
        display_name="Former Owner",
    )
    t.nominee = AsyncMock(
        id=new_owner_id,
        email=f"new_{new_owner_id.hex[:4]}@test.com",
        display_name="New Owner",
    )
    return t


# ==============================================================================
# WORK PACKAGE 7.4: FORMER OWNER STAY/LEAVE (TC-7.4-01 through TC-7.4-09)
# ==============================================================================

def test_tc_7_4_01_former_owner_selects_stay():
    """TC-7.4-01: Former owner successfully selects STAY before deadline."""
    ws_id = uuid.uuid4()
    former_id = uuid.uuid4()
    new_owner_id = uuid.uuid4()
    former_user = make_user_context(former_id)

    transfer = make_batch2_transfer_entity(
        ws_id,
        former_id,
        new_owner_id,
        transfer_status="ACCEPTED",
        former_choice="STAY",
        decision_status="PENDING",
    )

    app.dependency_overrides[get_current_user] = lambda: former_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(WorkspaceTransferService, "record_former_owner_choice", return_value=transfer):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/{transfer.id}/former-owner-choice",
            json={"choice": "STAY", "notes": "I would like to stay and help."},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ACCEPTED"
        assert data["former_owner_choice"] == "STAY"
        assert data["decision_status"] == "PENDING"


def test_tc_7_4_02_former_owner_selects_leave():
    """TC-7.4-02: Former owner successfully selects LEAVE before deadline."""
    ws_id = uuid.uuid4()
    former_id = uuid.uuid4()
    new_owner_id = uuid.uuid4()
    former_user = make_user_context(former_id)

    transfer = make_batch2_transfer_entity(
        ws_id,
        former_id,
        new_owner_id,
        transfer_status="ACCEPTED",
        former_choice="LEAVE",
        decision_status="DECIDED_REMOVED",
    )

    app.dependency_overrides[get_current_user] = lambda: former_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(WorkspaceTransferService, "record_former_owner_choice", return_value=transfer):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/{transfer.id}/former-owner-choice",
            json={"choice": "LEAVE", "notes": "Handing off completely."},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ACCEPTED"
        assert data["former_owner_choice"] == "LEAVE"
        assert data["decision_status"] == "DECIDED_REMOVED"


def test_tc_7_4_03_unauthorized_third_party_choice_forbidden_403():
    """TC-7.4-03: Unauthorized third party attempts former owner choice -> 403 Forbidden."""
    ws_id = uuid.uuid4()
    stranger_id = uuid.uuid4()
    stranger_user = make_user_context(stranger_id)

    app.dependency_overrides[get_current_user] = lambda: stranger_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(
        WorkspaceTransferService,
        "record_former_owner_choice",
        side_effect=HTTPException(
            status_code=403,
            detail="Only the former workspace owner can submit this disposition choice",
        ),
    ):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/former-owner-choice",
            json={"choice": "STAY"},
        )
        assert res.status_code == 403
        assert "Only the former workspace owner" in res.json()["detail"]


def test_tc_7_4_04_new_owner_attempts_former_owner_choice_forbidden_403():
    """TC-7.4-04: Newly accepted owner attempts to make former owner choice -> 403 Forbidden."""
    ws_id = uuid.uuid4()
    new_owner_id = uuid.uuid4()
    new_owner_user = make_user_context(new_owner_id)

    app.dependency_overrides[get_current_user] = lambda: new_owner_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(
        WorkspaceTransferService,
        "record_former_owner_choice",
        side_effect=HTTPException(
            status_code=403,
            detail="Only the former workspace owner can submit this disposition choice",
        ),
    ):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/former-owner-choice",
            json={"choice": "LEAVE"},
        )
        assert res.status_code == 403


def test_tc_7_4_05_invalid_choice_string_validation_422():
    """TC-7.4-05: Former owner attempts invalid choice string -> 422 Unprocessable Entity."""
    ws_id = uuid.uuid4()
    former_id = uuid.uuid4()
    former_user = make_user_context(former_id)

    app.dependency_overrides[get_current_user] = lambda: former_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    client = TestClient(app)
    res = client.post(
        f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/former-owner-choice",
        json={"choice": "MAYBE"},
    )
    assert res.status_code == 422


def test_tc_7_4_06_choice_on_non_accepted_transfer_409():
    """TC-7.4-06: Choice attempted on non-accepted transfer (e.g. PENDING) -> 409 Conflict."""
    ws_id = uuid.uuid4()
    former_id = uuid.uuid4()
    former_user = make_user_context(former_id)

    app.dependency_overrides[get_current_user] = lambda: former_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(
        WorkspaceTransferService,
        "record_former_owner_choice",
        side_effect=HTTPException(
            status_code=409,
            detail="Former owner choice cannot be recorded in transfer status PENDING",
        ),
    ):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/former-owner-choice",
            json={"choice": "STAY"},
        )
        assert res.status_code == 409
        assert "cannot be recorded in transfer status" in res.json()["detail"]


def test_tc_7_4_07_repeated_choice_submission_conflict_409():
    """TC-7.4-07: Former owner already chose STAY; attempting repeated choice -> 409 Conflict."""
    ws_id = uuid.uuid4()
    former_id = uuid.uuid4()
    former_user = make_user_context(former_id)

    app.dependency_overrides[get_current_user] = lambda: former_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(
        WorkspaceTransferService,
        "record_former_owner_choice",
        side_effect=HTTPException(
            status_code=409,
            detail="Former owner choice has already been recorded",
        ),
    ):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/former-owner-choice",
            json={"choice": "LEAVE"},
        )
        assert res.status_code == 409
        assert "already been recorded" in res.json()["detail"]


@pytest.mark.asyncio
async def test_tc_7_4_08_zero_workspace_access_during_transfer_pending():
    """TC-7.4-08: Former owner in TRANSFER_PENDING status is denied access to workspace routes with HTTP 403."""
    ws_id = uuid.uuid4()
    former_owner_id = uuid.uuid4()
    caller_ctx = make_user_context(former_owner_id)

    mock_session = AsyncMock()
    mock_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=former_owner_id,
        role=WorkspaceRole.ADMIN.value,
        status=MemberStatus.TRANSFER_PENDING.value,
    )

    with patch("backend.core.dependencies.workspace.WorkspaceMemberRepository") as MockRepo:
        mock_repo_inst = AsyncMock()
        mock_repo_inst.get_membership.return_value = mock_member
        MockRepo.return_value = mock_repo_inst

        with pytest.raises(HTTPException) as exc_info:
            await require_active_workspace_member(
                workspace_id=ws_id,
                current_user=caller_ctx,
                session=mock_session,
            )

        assert exc_info.value.status_code == 403
        assert "not an active member" in exc_info.value.detail


def test_tc_7_4_09_former_owner_choice_after_deadline_409():
    """TC-7.4-09: Former owner submits STAY after Day 30 deadline has passed -> 409 Conflict."""
    ws_id = uuid.uuid4()
    former_id = uuid.uuid4()
    former_user = make_user_context(former_id)

    app.dependency_overrides[get_current_user] = lambda: former_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(
        WorkspaceTransferService,
        "record_former_owner_choice",
        side_effect=HTTPException(
            status_code=409,
            detail="Former owner choice window has expired",
        ),
    ):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/former-owner-choice",
            json={"choice": "STAY"},
        )
        assert res.status_code == 409
        assert "expired" in res.json()["detail"]


# ==============================================================================
# WORK PACKAGE 7.5: NEW OWNER ROLE DECISION (TC-7.5-01 through TC-7.5-08)
# ==============================================================================

def test_tc_7_5_01_new_owner_grants_admin():
    """TC-7.5-01: New owner grants ADMIN role to former owner (State 8)."""
    ws_id = uuid.uuid4()
    former_id = uuid.uuid4()
    new_owner_id = uuid.uuid4()
    new_owner_user = make_user_context(new_owner_id)
    owner_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=ws_id, user_id=new_owner_id, role="OWNER", status="ACTIVE"
    )

    transfer = make_batch2_transfer_entity(
        ws_id,
        former_id,
        new_owner_id,
        transfer_status="ACCEPTED",
        former_choice="STAY",
        decision_status="DECIDED_ADMIN",
    )

    app.dependency_overrides[get_current_user] = lambda: new_owner_user
    app.dependency_overrides[require_active_workspace_owner] = lambda: owner_member
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(WorkspaceTransferService, "decide_former_owner_role", return_value=transfer):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/{transfer.id}/role-decision",
            json={"decision": "ADMIN", "notes": "Granted co-admin privileges."},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["decision_status"] == "DECIDED_ADMIN"


def test_tc_7_5_01b_new_owner_grants_member():
    """TC-7.5-01B: New owner grants MEMBER role to former owner (State 9)."""
    ws_id = uuid.uuid4()
    former_id = uuid.uuid4()
    new_owner_id = uuid.uuid4()
    new_owner_user = make_user_context(new_owner_id)
    owner_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=ws_id, user_id=new_owner_id, role="OWNER", status="ACTIVE"
    )

    transfer = make_batch2_transfer_entity(
        ws_id,
        former_id,
        new_owner_id,
        transfer_status="ACCEPTED",
        former_choice="STAY",
        decision_status="DECIDED_MEMBER",
    )

    app.dependency_overrides[get_current_user] = lambda: new_owner_user
    app.dependency_overrides[require_active_workspace_owner] = lambda: owner_member
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(WorkspaceTransferService, "decide_former_owner_role", return_value=transfer):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/{transfer.id}/role-decision",
            json={"decision": "MEMBER", "notes": "Continuing as standard contributor."},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["decision_status"] == "DECIDED_MEMBER"


def test_tc_7_5_02_new_owner_removes_former_owner():
    """TC-7.5-02: New owner removes former owner from workspace (State 10)."""
    ws_id = uuid.uuid4()
    former_id = uuid.uuid4()
    new_owner_id = uuid.uuid4()
    new_owner_user = make_user_context(new_owner_id)
    owner_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=ws_id, user_id=new_owner_id, role="OWNER", status="ACTIVE"
    )

    transfer = make_batch2_transfer_entity(
        ws_id,
        former_id,
        new_owner_id,
        transfer_status="ACCEPTED",
        former_choice="STAY",
        decision_status="DECIDED_REMOVED",
    )

    app.dependency_overrides[get_current_user] = lambda: new_owner_user
    app.dependency_overrides[require_active_workspace_owner] = lambda: owner_member
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(WorkspaceTransferService, "decide_former_owner_role", return_value=transfer):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/{transfer.id}/role-decision",
            json={"decision": "REMOVE", "notes": "Full departure requested."},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["decision_status"] == "DECIDED_REMOVED"


def test_tc_7_5_03_prohibited_viewer_role_rejected_422():
    """TC-7.5-03: Attempt to assign prohibited VIEWER role is rejected with 422 Unprocessable Entity."""
    ws_id = uuid.uuid4()
    new_owner_id = uuid.uuid4()
    new_owner_user = make_user_context(new_owner_id)
    owner_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=ws_id, user_id=new_owner_id, role="OWNER", status="ACTIVE"
    )

    app.dependency_overrides[get_current_user] = lambda: new_owner_user
    app.dependency_overrides[require_active_workspace_owner] = lambda: owner_member
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    client = TestClient(app)
    res = client.post(
        f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/role-decision",
        json={"decision": "VIEWER"},
    )
    assert res.status_code == 422
    # Schema level rejection specifies permitted options
    assert "ADMIN" in str(res.json()) or "MEMBER" in str(res.json())


def test_tc_7_5_05_non_owner_role_decision_forbidden_403():
    """TC-7.5-05: Non-owner member attempts role decision -> 403 Forbidden."""
    ws_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    admin_user = make_user_context(admin_id)

    def mock_guard_raise():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Operation restricted to active workspace OWNER.",
        )

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[require_active_workspace_owner] = mock_guard_raise
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    client = TestClient(app)
    res = client.post(
        f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/role-decision",
        json={"decision": "ADMIN"},
    )
    assert res.status_code == 403
    assert "restricted to active workspace OWNER" in res.json()["detail"]


def test_tc_7_5_06_role_decision_before_stay_conflict_409():
    """TC-7.5-06: New owner attempts role decision before former owner chooses STAY -> 409 Conflict."""
    ws_id = uuid.uuid4()
    new_owner_id = uuid.uuid4()
    new_owner_user = make_user_context(new_owner_id)
    owner_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=ws_id, user_id=new_owner_id, role="OWNER", status="ACTIVE"
    )

    app.dependency_overrides[get_current_user] = lambda: new_owner_user
    app.dependency_overrides[require_active_workspace_owner] = lambda: owner_member
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(
        WorkspaceTransferService,
        "decide_former_owner_role",
        side_effect=HTTPException(
            status_code=409,
            detail="Role decision cannot be made before the former owner explicitly selects STAY",
        ),
    ):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/role-decision",
            json={"decision": "ADMIN"},
        )
        assert res.status_code == 409
        assert "before the former owner explicitly selects STAY" in res.json()["detail"]


def test_tc_7_5_07_unauthenticated_role_decision_401():
    """TC-7.5-07: Unauthenticated role decision request returns 401 Unauthorized."""
    ws_id = uuid.uuid4()

    def mock_auth_unauthenticated():
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    app.dependency_overrides[get_current_user] = mock_auth_unauthenticated
    app.dependency_overrides.pop(require_active_workspace_owner, None)
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    try:
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/role-decision",
            json={"decision": "ADMIN"},
        )
        assert res.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# WORK PACKAGE 7.8: OWNER DEPARTURE PROTECTION (TC-7.8-01 through TC-7.8-04)
# ==============================================================================

def test_tc_7_8_01_active_owner_cannot_leave_workspace_409():
    """TC-7.8-01: Active owner attempting to leave returns HTTP 409 CANNOT_LEAVE_AS_OWNER."""
    ws_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    owner_user = make_user_context(owner_id)
    owner_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=ws_id, user_id=owner_id, role="OWNER", status="ACTIVE"
    )

    mock_service = AsyncMock(spec=WorkspaceMembershipService)
    mock_service.member_repo = AsyncMock()
    mock_service.member_repo.get_membership.return_value = owner_member
    mock_service.remove_member.side_effect = MembershipConflictError(
        "Cannot leave as owner. You must transfer workspace ownership before leaving."
    )

    app.dependency_overrides[get_current_user] = lambda: owner_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_workspace_membership_service] = lambda: mock_service

    try:
        client = TestClient(app)
        res = client.post(f"/api/v1/workspaces/{ws_id}/members/leave")
        assert res.status_code == 409
        detail = res.json()["detail"]
        assert isinstance(detail, dict)
        assert detail["error"] == "CANNOT_LEAVE_AS_OWNER"
        assert "transfer workspace ownership" in detail["message"]
    finally:
        app.dependency_overrides.clear()


def test_tc_7_8_02_admin_cannot_remove_active_owner():
    """TC-7.8-02: Admin attempting to remove active owner receives HTTP 409 / 403 error."""
    ws_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    owner_member_id = uuid.uuid4()
    admin_user = make_user_context(admin_id)

    mock_service = AsyncMock(spec=WorkspaceMembershipService)
    mock_service.remove_member.side_effect = MembershipConflictError(
        "Cannot remove the last remaining owner of the workspace. Transfer ownership first."
    )

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_workspace_membership_service] = lambda: mock_service

    try:
        client = TestClient(app)
        res = client.delete(f"/api/v1/workspaces/{ws_id}/members/{owner_member_id}")
        assert res.status_code == 409
        detail = res.json()["detail"]
        assert detail["error"] == "CANNOT_LEAVE_AS_OWNER"
    finally:
        app.dependency_overrides.clear()


def test_tc_7_8_03_non_owner_member_can_leave_normally():
    """TC-7.8-03: Non-owner member (ADMIN or MEMBER) can leave workspace normally with HTTP 200."""
    ws_id = uuid.uuid4()
    member_user_id = uuid.uuid4()
    member_user = make_user_context(member_user_id)
    member_rec = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=member_user_id,
        role="MEMBER",
        status="ACTIVE",
    )

    now = datetime.now(UTC)
    departed_member = WorkspaceMember(
        id=member_rec.id,
        workspace_id=ws_id,
        user_id=member_user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
        is_former_owner=False,
        is_deleted=True,
        version=1,
        created_at=now,
        updated_at=now,
    )

    mock_service = AsyncMock(spec=WorkspaceMembershipService)
    mock_service.member_repo = AsyncMock()
    mock_service.member_repo.get_membership.return_value = member_rec
    mock_service.remove_member.return_value = departed_member

    app.dependency_overrides[get_current_user] = lambda: member_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_workspace_membership_service] = lambda: mock_service

    try:
        client = TestClient(app)
        res = client.post(f"/api/v1/workspaces/{ws_id}/members/leave")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "Successfully left the workspace" in data["message"]
    finally:
        app.dependency_overrides.clear()


def test_tc_7_8_04_former_owner_as_admin_can_leave_normally():
    """TC-7.8-04: Former owner (who is now ADMIN with is_former_owner=True) can leave workspace normally."""
    ws_id = uuid.uuid4()
    former_owner_id = uuid.uuid4()
    former_user = make_user_context(former_owner_id)
    former_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=former_owner_id,
        role="ADMIN",
        status="ACTIVE",
        is_former_owner=True,
    )

    now = datetime.now(UTC)
    departed_former = WorkspaceMember(
        id=former_member.id,
        workspace_id=ws_id,
        user_id=former_owner_id,
        role="ADMIN",
        status=MemberStatus.ACTIVE.value,
        is_former_owner=True,
        is_deleted=True,
        version=1,
        created_at=now,
        updated_at=now,
    )

    mock_service = AsyncMock(spec=WorkspaceMembershipService)
    mock_service.member_repo = AsyncMock()
    mock_service.member_repo.get_membership.return_value = former_member
    mock_service.remove_member.return_value = departed_former

    app.dependency_overrides[get_current_user] = lambda: former_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_workspace_membership_service] = lambda: mock_service

    try:
        client = TestClient(app)
        res = client.post(f"/api/v1/workspaces/{ws_id}/members/leave")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "Successfully left the workspace" in data["message"]
    finally:
        app.dependency_overrides.clear()
