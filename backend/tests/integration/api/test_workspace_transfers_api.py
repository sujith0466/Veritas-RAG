"""API Integration Tests for Workspace Ownership Transfers.

Governed by Section 7 Batch 1 (REV5).
Mounted under /api/v1/workspaces/{workspace_id}/transfers.
Tests route guards, response schemas, status codes, DTO validation, and privacy filtering.
"""

from datetime import UTC, datetime, timedelta
import os
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from backend.api.v1.routes.workspace_transfers import router as workspace_transfers_router
from backend.api.v1.schemas.workspace_transfer import (
    OwnershipTransferResponse,
    OwnershipTransferUserDTO,
)
from backend.api.v1.workspaces.dependencies import (
    require_active_workspace_member,
    require_active_workspace_owner,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.permissions.rbac import Role
from backend.models.entities.workspace_member import (
    MemberStatus,
    WorkspaceMember,
    WorkspaceRole,
)
from backend.models.entities.workspace_ownership_transfer import (
    TransferStatus,
    WorkspaceOwnershipTransfer,
)
from backend.services.workspace_transfer_service import WorkspaceTransferService

app = FastAPI()
app.include_router(workspace_transfers_router, prefix="/api/v1")


def make_user_context(user_id: uuid.UUID, role: Role = Role.VIEWER) -> UserContext:
    return UserContext(
        id=user_id,
        email=f"user_{user_id.hex[:6]}@example.com",
        role=role,
        is_active=True,
        is_verified=True,
    )


def make_transfer_entity(
    workspace_id: uuid.UUID,
    owner_id: uuid.UUID,
    nominee_id: uuid.UUID,
    transfer_status: str = TransferStatus.PENDING.value,
    expires_delta_days: int = 7,
) -> WorkspaceOwnershipTransfer:
    now = datetime.now(UTC)
    t = WorkspaceOwnershipTransfer(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        nominated_by_user_id=owner_id,
        nominee_user_id=nominee_id,
        status=transfer_status,
        created_at=now,
        expires_at=now + timedelta(days=expires_delta_days),
    )
    t.nominated_by = AsyncMock(id=owner_id, email=f"owner_{owner_id.hex[:4]}@test.com", display_name="Owner User")
    t.nominee = AsyncMock(id=nominee_id, email=f"nominee_{nominee_id.hex[:4]}@test.com", display_name="Nominee User")
    return t


# ==============================================================================
# ROUTE GUARD & NOMINATION TESTS
# ==============================================================================

def test_api_nominate_success():
    ws_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    nominee_id = uuid.uuid4()
    owner_user = make_user_context(owner_id)
    owner_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=owner_id, role="OWNER", status="ACTIVE")

    transfer = make_transfer_entity(ws_id, owner_id, nominee_id)

    app.dependency_overrides[get_current_user] = lambda: owner_user
    app.dependency_overrides[require_active_workspace_owner] = lambda: owner_member
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(WorkspaceTransferService, "initiate_nomination", return_value=transfer) as mock_nom:
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/nominate",
            json={"nominee_user_id": str(nominee_id)},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["id"] == str(transfer.id)
        assert data["workspace_id"] == str(ws_id)
        assert data["status"] == "PENDING"
        assert data["nominated_by"]["id"] == str(owner_id)
        assert data["nominee"]["id"] == str(nominee_id)


def test_api_nominate_ineligible_nominee_400():
    ws_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    nominee_id = uuid.uuid4()
    owner_user = make_user_context(owner_id)
    owner_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=owner_id, role="OWNER", status="ACTIVE")

    app.dependency_overrides[get_current_user] = lambda: owner_user
    app.dependency_overrides[require_active_workspace_owner] = lambda: owner_member
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(
        WorkspaceTransferService,
        "initiate_nomination",
        side_effect=HTTPException(status_code=400, detail="Cannot nominate self as workspace owner"),
    ):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/nominate",
            json={"nominee_user_id": str(nominee_id)},
        )
        assert res.status_code == 400
        assert "Cannot nominate self" in res.json()["detail"]


def test_api_nominate_pending_exists_409():
    ws_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    nominee_id = uuid.uuid4()
    owner_user = make_user_context(owner_id)
    owner_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=owner_id, role="OWNER", status="ACTIVE")

    app.dependency_overrides[get_current_user] = lambda: owner_user
    app.dependency_overrides[require_active_workspace_owner] = lambda: owner_member
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(
        WorkspaceTransferService,
        "initiate_nomination",
        side_effect=HTTPException(status_code=409, detail="A pending ownership nomination already exists for this workspace"),
    ):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/nominate",
            json={"nominee_user_id": str(nominee_id)},
        )
        assert res.status_code == 409
        assert "pending ownership nomination already exists" in res.json()["detail"]


# ==============================================================================
# ACCEPTANCE TESTS
# ==============================================================================

def test_api_accept_success():
    ws_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    nominee_id = uuid.uuid4()
    nominee_user = make_user_context(nominee_id)

    transfer = make_transfer_entity(ws_id, owner_id, nominee_id, transfer_status="ACCEPTED")

    app.dependency_overrides[get_current_user] = lambda: nominee_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(WorkspaceTransferService, "accept_transfer", return_value=transfer):
        client = TestClient(app)
        res = client.post(f"/api/v1/workspaces/{ws_id}/transfers/{transfer.id}/accept")
        assert res.status_code == 200
        assert res.json()["status"] == "ACCEPTED"


def test_api_accept_non_nominee_forbidden_403():
    ws_id = uuid.uuid4()
    stranger_id = uuid.uuid4()
    stranger_user = make_user_context(stranger_id)

    app.dependency_overrides[get_current_user] = lambda: stranger_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(
        WorkspaceTransferService,
        "accept_transfer",
        side_effect=HTTPException(status_code=403, detail="Only the designated nominee can accept this nomination"),
    ):
        client = TestClient(app)
        res = client.post(f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/accept")
        assert res.status_code == 403
        assert "designated nominee" in res.json()["detail"]


def test_api_accept_expired_410():
    ws_id = uuid.uuid4()
    nominee_id = uuid.uuid4()
    nominee_user = make_user_context(nominee_id)

    app.dependency_overrides[get_current_user] = lambda: nominee_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(
        WorkspaceTransferService,
        "accept_transfer",
        side_effect=HTTPException(status_code=410, detail="Ownership nomination has expired"),
    ):
        client = TestClient(app)
        res = client.post(f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/accept")
        assert res.status_code == 410
        assert "expired" in res.json()["detail"]


# ==============================================================================
# REJECTION TESTS
# ==============================================================================

def test_api_reject_success():
    ws_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    nominee_id = uuid.uuid4()
    nominee_user = make_user_context(nominee_id)

    transfer = make_transfer_entity(ws_id, owner_id, nominee_id, transfer_status="REJECTED")
    transfer.rejection_reason = "Busy with other projects"

    app.dependency_overrides[get_current_user] = lambda: nominee_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(WorkspaceTransferService, "reject_transfer", return_value=transfer):
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/{transfer.id}/reject",
            json={"rejection_reason": "Busy with other projects"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "REJECTED"
        assert res.json()["rejection_reason"] == "Busy with other projects"


def test_api_reject_reason_max_length_validation_422():
    ws_id = uuid.uuid4()
    nominee_id = uuid.uuid4()
    nominee_user = make_user_context(nominee_id)

    app.dependency_overrides[get_current_user] = lambda: nominee_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    client = TestClient(app)
    # 501 characters violates max_length=500
    oversized_reason = "x" * 501
    res = client.post(
        f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/reject",
        json={"rejection_reason": oversized_reason},
    )
    assert res.status_code == 422


# ==============================================================================
# CANCELLATION TESTS
# ==============================================================================

def test_api_cancel_success():
    ws_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    nominee_id = uuid.uuid4()
    owner_user = make_user_context(owner_id)
    owner_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=owner_id, role="OWNER", status="ACTIVE")

    transfer = make_transfer_entity(ws_id, owner_id, nominee_id, transfer_status="CANCELLED")

    app.dependency_overrides[get_current_user] = lambda: owner_user
    app.dependency_overrides[require_active_workspace_owner] = lambda: owner_member
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(WorkspaceTransferService, "cancel_transfer", return_value=transfer):
        client = TestClient(app)
        res = client.post(f"/api/v1/workspaces/{ws_id}/transfers/{transfer.id}/cancel")
        assert res.status_code == 200
        assert res.json()["status"] == "CANCELLED"


def test_api_cancel_unauthorized_non_owner_403_unconditional():
    ws_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    admin_user = make_user_context(admin_id)

    # Route guard throws 403 before reaching service
    def mock_guard_raise():
        raise HTTPException(status_code=403, detail="Forbidden: Operation restricted to active workspace OWNER.")

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[require_active_workspace_owner] = mock_guard_raise
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    client = TestClient(app)
    res = client.post(f"/api/v1/workspaces/{ws_id}/transfers/{uuid.uuid4()}/cancel")
    assert res.status_code == 403
    assert "restricted to active workspace OWNER" in res.json()["detail"]


# ==============================================================================
# ACTIVE TRANSFER GET & PRIVACY TESTS
# ==============================================================================

def test_api_get_active_returns_transfer_for_owner_or_nominee():
    ws_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    nominee_id = uuid.uuid4()
    owner_user = make_user_context(owner_id)
    member_record = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=owner_id, role="OWNER", status="ACTIVE")

    transfer = make_transfer_entity(ws_id, owner_id, nominee_id)

    app.dependency_overrides[get_current_user] = lambda: owner_user
    app.dependency_overrides[require_active_workspace_member] = lambda: member_record
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(WorkspaceTransferService, "get_active_transfer", return_value=transfer):
        client = TestClient(app)
        res = client.get(f"/api/v1/workspaces/{ws_id}/transfers/active")
        assert res.status_code == 200
        data = res.json()
        assert data is not None
        assert data["id"] == str(transfer.id)
        assert data["status"] == "PENDING"


def test_api_get_active_returns_null_for_third_party_or_none():
    ws_id = uuid.uuid4()
    third_party_id = uuid.uuid4()
    third_party_user = make_user_context(third_party_id)
    member_record = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=third_party_id, role="MEMBER", status="ACTIVE")

    app.dependency_overrides[get_current_user] = lambda: third_party_user
    app.dependency_overrides[require_active_workspace_member] = lambda: member_record
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(WorkspaceTransferService, "get_active_transfer", return_value=None):
        client = TestClient(app)
        res = client.get(f"/api/v1/workspaces/{ws_id}/transfers/active")
        assert res.status_code == 200
        assert res.json() is None


def test_api_get_active_non_member_forbidden_403():
    ws_id = uuid.uuid4()
    stranger_id = uuid.uuid4()
    stranger_user = make_user_context(stranger_id)

    def mock_member_guard_raise():
        raise HTTPException(status_code=403, detail="Forbidden: You are not an active member of this workspace.")

    app.dependency_overrides[get_current_user] = lambda: stranger_user
    app.dependency_overrides[require_active_workspace_member] = mock_member_guard_raise
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    client = TestClient(app)
    res = client.get(f"/api/v1/workspaces/{ws_id}/transfers/active")
    assert res.status_code == 403
    assert "not an active member" in res.json()["detail"]


# ==============================================================================
# GAP CLOSURE TESTS (TC-7.1-11, TC-7.2-05)
# ==============================================================================

def test_api_nominate_unauthenticated_401():
    """TC-7.1-11: Unauthenticated request to nominate endpoint returns HTTP 401."""
    ws_id = uuid.uuid4()
    nominee_id = uuid.uuid4()

    def mock_auth_unauthenticated():
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    app.dependency_overrides[get_current_user] = mock_auth_unauthenticated
    app.dependency_overrides.pop(require_active_workspace_owner, None)
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    try:
        client = TestClient(app)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/transfers/nominate",
            json={"nominee_user_id": str(nominee_id)},
        )
        assert res.status_code == 401
        assert "Could not validate credentials" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_former_owner_denied_access_post_acceptance_403():
    """TC-7.2-05: Former owner in TRANSFER_PENDING status is denied access to workspace routes with HTTP 403."""
    ws_id = uuid.uuid4()
    former_owner_id = uuid.uuid4()
    caller_ctx = make_user_context(former_owner_id)

    # Mock session and repository returning a member with TRANSFER_PENDING status
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
