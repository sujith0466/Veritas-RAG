"""Security test suite for WP-6: Platform Admin Ownerless-Workspace Recovery (DEC-01 / WP-6).

Comprehensive coverage under Project Owner Decisions D-3.1 through D-3.7 and Option 3A:
1. Valid Platform Admin recovery.
2. Missing caller.
3. Inactive caller.
4. Deleted caller.
5. Caller without Platform Admin role.
6. Missing target.
7. Inactive target.
8. Deleted target.
9. Unverified target.
10. Caller and target are the same User — one User lock only.
11. Caller/target IDs are locked in ascending order.
12. Existing active non-deleted OWNER returns 409.
13. Existing suspended non-deleted OWNER returns 409.
14. Existing inactive non-deleted OWNER returns 409.
15. Confirmed legacy `workspace_owner` non-deleted membership returns 409.
16. Target membership ineligible or soft-deleted.
17. Ticket ID/reason validation failures.
18. Audit flush failure triggers rollback and preserves failure.
19. Intentional HTTPException remains unchanged if rollback succeeds.
20. Intentional HTTPException remains unchanged if rollback and invalidation fail.
21. Unexpected exception with successful rollback.
22. Unexpected exception with rollback failure and successful invalidation.
23. Unexpected exception with both rollback and invalidation failure.
24. In-memory target state restoration after failed persistence.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from backend.api.v1.routes.platform_admin import router as platform_admin_router
from backend.api.v1.schemas.owner_recovery import OwnerRecoveryRequest
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.exceptions.auth import AuthenticationException, InsufficientRoleException
from backend.core.permissions.rbac import Role
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.services.workspace.owner_recovery_service import OwnerRecoveryService


@pytest.fixture
def test_app():
    app = FastAPI()

    @app.exception_handler(InsufficientRoleException)
    async def insufficient_role_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationException)
    async def auth_exception_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(exc)})

    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session
    app.include_router(platform_admin_router, prefix="/api/v1")
    return app


def create_smart_mock_session(
    users: dict[uuid.UUID, User | None] | None = None,
    workspace: Workspace | None = None,
    existing_owners: list[WorkspaceMember] | None = None,
    target_member: WorkspaceMember | None = None,
):
    """Create an AsyncMock session that routes queries based on entity type and parameters."""
    mock_session = AsyncMock()
    users_store = users or {}
    owners_store = existing_owners or []
    executed_statements = []

    async def mock_execute(stmt, *args, **kwargs):
        executed_statements.append(stmt)
        res = MagicMock()
        entity = stmt.column_descriptions[0]["entity"]
        params = stmt.compile().params

        if entity is User:
            # Match user by checking parameter values against users_store
            found_user = None
            for p_val in params.values():
                if isinstance(p_val, uuid.UUID) and p_val in users_store:
                    found_user = users_store[p_val]
                    break
            res.scalar_one_or_none.return_value = found_user
            return res

        elif entity is Workspace:
            res.scalar_one_or_none.return_value = workspace
            return res

        elif entity is WorkspaceMember:
            # Distinguish owner check query (uses btrim) from target member query (direct member lookup)
            if "btrim" in str(stmt).lower():
                res.scalars.return_value.all.return_value = owners_store
                return res
            else:
                res.scalar_one_or_none.return_value = target_member
                return res
                return res

        res.scalar_one_or_none.return_value = None
        res.scalars.return_value.all.return_value = []
        return res

    mock_session.execute = AsyncMock(side_effect=mock_execute)
    mock_session.executed_statements = executed_statements
    return mock_session


# ---------------------------------------------------------------------------
# Test Cases 1-5: Caller Authorization and Eligibility
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_denied_for_non_platform_admins(test_app):
    """1. Non-platform admin callers (token role != platform_admin) denied with 403."""
    ws_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    payload = {
        "target_user_id": str(target_user_id),
        "justification_ticket_id": "SEC-9999",
        "justification_reason": "Emergency recovery of orphaned workspace",
    }

    for forbidden_role in [Role.OWNER, Role.ADMIN, Role.MEMBER, Role.VIEWER]:
        user = UserContext(
            id=uuid.uuid4(),
            email=f"{forbidden_role.value.lower()}@test.com",
            role=forbidden_role.value,
            workspace_id=ws_id,
            tenant_id=str(ws_id),
        )
        test_app.dependency_overrides[get_current_user] = lambda u=user: u

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner",
                json=payload,
            )
            assert res.status_code == 403


@pytest.mark.asyncio
async def test_recovery_missing_caller(test_app):
    """2. Caller row not found in users table -> 403 Forbidden."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    # Caller missing from DB
    mock_session = create_smart_mock_session(users={caller_id: None, target_id: MagicMock(spec=User)})
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-1001",
            "justification_reason": "Recovery ticket with sufficient length",
        })
        assert res.status_code == 403
        assert "not found or deactivated" in res.json()["detail"]


@pytest.mark.asyncio
async def test_recovery_inactive_caller(test_app):
    """3. Caller account is inactive (is_active=False) -> 403 Forbidden."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    db_caller = MagicMock(spec=User, id=caller_id, is_active=False, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=target_id, is_active=True, is_verified=True, is_deleted=False)

    mock_session = create_smart_mock_session(users={caller_id: db_caller, target_id: db_target})
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-1002",
            "justification_reason": "Recovery ticket with sufficient length",
        })
        assert res.status_code == 403
        assert "deactivated" in res.json()["detail"]


@pytest.mark.asyncio
async def test_recovery_deleted_caller(test_app):
    """4. Caller account is soft-deleted -> 403 Forbidden."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    # Soft-deleted caller returns None from select(User).where(is_deleted == False)
    mock_session = create_smart_mock_session(users={caller_id: None, target_id: MagicMock(spec=User)})
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-1003",
            "justification_reason": "Recovery ticket with sufficient length",
        })
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_recovery_caller_not_platform_admin(test_app):
    """5. Caller database role is not platform_admin -> 403 Forbidden."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="member")
    db_target = MagicMock(spec=User, id=target_id, is_active=True, is_verified=True, is_deleted=False)

    mock_session = create_smart_mock_session(users={caller_id: db_caller, target_id: db_target})
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-1004",
            "justification_reason": "Recovery ticket with sufficient length",
        })
        assert res.status_code == 403
        assert "not a platform admin" in res.json()["detail"]


# ---------------------------------------------------------------------------
# Test Cases 6-9: Target User Eligibility
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_missing_target(test_app):
    """6. Target user not found in database -> 404 Not Found."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    mock_session = create_smart_mock_session(users={caller_id: db_caller, target_id: None})
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-1005",
            "justification_reason": "Recovery ticket with sufficient length",
        })
        assert res.status_code == 404
        assert "Target user record not found" in res.json()["detail"]


@pytest.mark.asyncio
async def test_recovery_inactive_target(test_app):
    """7. Target user is inactive (is_active=False) -> 400 Bad Request."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=target_id, is_active=False, is_verified=True, is_deleted=False)

    mock_session = create_smart_mock_session(users={caller_id: db_caller, target_id: db_target})
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-1006",
            "justification_reason": "Recovery ticket with sufficient length",
        })
        assert res.status_code == 400
        assert "inactive or unverified" in res.json()["detail"]


@pytest.mark.asyncio
async def test_recovery_deleted_target(test_app):
    """8. Target user is deleted -> 404 Not Found."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    # Soft deleted target returns None from query
    mock_session = create_smart_mock_session(users={caller_id: db_caller, target_id: None})
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-1007",
            "justification_reason": "Recovery ticket with sufficient length",
        })
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_recovery_unverified_target(test_app):
    """9. Target user is unverified (is_verified=False) -> 400 Bad Request."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=target_id, is_active=True, is_verified=False, is_deleted=False)

    mock_session = create_smart_mock_session(users={caller_id: db_caller, target_id: db_target})
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-1008",
            "justification_reason": "Recovery ticket with sufficient length",
        })
        assert res.status_code == 400
        assert "inactive or unverified" in res.json()["detail"]


# ---------------------------------------------------------------------------
# Test Cases 10-11: Deterministic User Locking Sequence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_same_user_single_lock():
    """10. Caller and target are the same User — row lock acquired exactly once."""
    user_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    db_user = MagicMock(spec=User, id=user_id, is_active=True, is_verified=True, is_deleted=False, role="platform_admin")
    db_workspace = MagicMock(spec=Workspace, id=ws_id, is_deleted=False)
    target_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=user_id, role="MEMBER", status=MemberStatus.ACTIVE.value, is_deleted=False, version=1)

    mock_session = create_smart_mock_session(
        users={user_id: db_user},
        workspace=db_workspace,
        existing_owners=[],
        target_member=target_member,
    )

    service = OwnerRecoveryService(mock_session)
    req = OwnerRecoveryRequest(target_user_id=user_id, justification_ticket_id="SEC-2001", justification_reason="Self-recovery operation")
    res = await service.recover_ownerless_workspace(ws_id, user_id, req)

    assert res.recovery_status == "COMPLETED"
    # Verify User query was executed exactly once
    user_queries = [s for s in mock_session.executed_statements if s.column_descriptions[0]["entity"] is User]
    assert len(user_queries) == 1


@pytest.mark.asyncio
async def test_recovery_sorted_user_locking_order():
    """11. Caller/target IDs are locked in deterministic ascending primary-key order."""
    id_low = uuid.UUID("00000000-0000-0000-0000-000000000001")
    id_high = uuid.UUID("00000000-0000-0000-0000-000000000002")
    ws_id = uuid.uuid4()

    # Case A: Caller is high, target is low
    db_caller = MagicMock(spec=User, id=id_high, is_active=True, is_verified=True, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=id_low, is_active=True, is_verified=True, is_deleted=False)
    db_ws = MagicMock(spec=Workspace, id=ws_id, is_deleted=False)
    target_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=id_low, role="MEMBER", status=MemberStatus.ACTIVE.value, is_deleted=False, version=1)

    mock_session = create_smart_mock_session(
        users={id_high: db_caller, id_low: db_target},
        workspace=db_ws,
        existing_owners=[],
        target_member=target_member,
    )

    service = OwnerRecoveryService(mock_session)
    req = OwnerRecoveryRequest(target_user_id=id_low, justification_ticket_id="SEC-2002", justification_reason="Ascending lock order test")
    res = await service.recover_ownerless_workspace(ws_id, id_high, req)
    assert res.recovery_status == "COMPLETED"

    user_queries = [s for s in mock_session.executed_statements if s.column_descriptions[0]["entity"] is User]
    assert len(user_queries) == 2
    # Verify first query locked id_low, second locked id_high
    params_q1 = user_queries[0].compile().params
    params_q2 = user_queries[1].compile().params
    assert id_low in params_q1.values()
    assert id_high in params_q2.values()


# ---------------------------------------------------------------------------
# Test Cases 12-15: Option 3A Existing Non-Deleted Owner Safeguards
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_rejected_if_existing_active_owner(test_app):
    """12. Existing active non-deleted OWNER -> 409 Conflict."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=target_id, is_active=True, is_verified=True, is_deleted=False)
    db_ws = MagicMock(spec=Workspace, id=ws_id, is_deleted=False)

    existing_owner = MagicMock(spec=WorkspaceMember, role="OWNER", status="ACTIVE", is_deleted=False)
    mock_session = create_smart_mock_session(
        users={caller_id: db_caller, target_id: db_target},
        workspace=db_ws,
        existing_owners=[existing_owner],
    )
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-3001",
            "justification_reason": "Emergency recovery testing active owner conflict",
        })
        assert res.status_code == 409, res.json()
        assert "currently has 1 active OWNER" in res.json()["detail"]


@pytest.mark.asyncio
async def test_recovery_rejected_if_existing_suspended_owner(test_app):
    """13. Existing suspended non-deleted OWNER -> 409 Conflict (Option 3A)."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=target_id, is_active=True, is_verified=True, is_deleted=False)
    db_ws = MagicMock(spec=Workspace, id=ws_id, is_deleted=False)

    suspended_owner = MagicMock(spec=WorkspaceMember, role="OWNER", status="SUSPENDED", is_deleted=False)
    mock_session = create_smart_mock_session(
        users={caller_id: db_caller, target_id: db_target},
        workspace=db_ws,
        existing_owners=[suspended_owner],
    )
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-3002",
            "justification_reason": "Emergency recovery testing suspended owner conflict",
        })
        assert res.status_code == 409, res.json()
        assert "Option 3A" in res.json()["detail"]


@pytest.mark.asyncio
async def test_recovery_rejected_if_existing_inactive_owner(test_app):
    """14. Existing inactive non-deleted OWNER -> 409 Conflict (Option 3A)."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=target_id, is_active=True, is_verified=True, is_deleted=False)
    db_ws = MagicMock(spec=Workspace, id=ws_id, is_deleted=False)

    inactive_owner = MagicMock(spec=WorkspaceMember, role="OWNER", status="INACTIVE", is_deleted=False)
    mock_session = create_smart_mock_session(
        users={caller_id: db_caller, target_id: db_target},
        workspace=db_ws,
        existing_owners=[inactive_owner],
    )
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-3003",
            "justification_reason": "Emergency recovery testing inactive owner conflict",
        })
        assert res.status_code == 409, res.json()
        assert "Option 3A" in res.json()["detail"]


@pytest.mark.asyncio
async def test_recovery_rejected_if_existing_legacy_workspace_owner(test_app):
    """15. Confirmed legacy workspace_owner non-deleted membership returns 409."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=target_id, is_active=True, is_verified=True, is_deleted=False)
    db_ws = MagicMock(spec=Workspace, id=ws_id, is_deleted=False)

    legacy_owner = MagicMock(spec=WorkspaceMember, role="workspace_owner", status="ACTIVE", is_deleted=False)
    mock_session = create_smart_mock_session(
        users={caller_id: db_caller, target_id: db_target},
        workspace=db_ws,
        existing_owners=[legacy_owner],
    )
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-3004",
            "justification_reason": "Emergency recovery testing legacy workspace_owner alias",
        })
        assert res.status_code == 409, res.json()


# ---------------------------------------------------------------------------
# Test Cases 16-17: Target Membership & Validation Failures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_rejected_if_target_not_member(test_app):
    """16. Target user not an active workspace member -> 404 Not Found."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=target_id, is_active=True, is_verified=True, is_deleted=False)
    db_ws = MagicMock(spec=Workspace, id=ws_id, is_deleted=False)

    mock_session = create_smart_mock_session(
        users={caller_id: db_caller, target_id: db_target},
        workspace=db_ws,
        existing_owners=[],
        target_member=None,
    )
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-4001",
            "justification_reason": "Emergency recovery testing target member not found",
        })
        assert res.status_code == 404
        assert "not an active member" in res.json()["detail"]


@pytest.mark.asyncio
async def test_recovery_validation_requires_ticket_and_reason(test_app):
    """17. Missing, blank, or short ticket ID/reason rejected with 422 Unprocessable Entity."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Blank ticket id
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(uuid.uuid4()),
            "justification_ticket_id": "   ",
            "justification_reason": "Valid reason with plenty of length",
        })
        assert res.status_code == 422

        # Too short reason
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(uuid.uuid4()),
            "justification_ticket_id": "SEC-1234",
            "justification_reason": "short",
        })
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# Test Cases 18-20: Tier 1 Intentional HTTPException Handling & Cleanup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_intentional_http_exception_rollback_success():
    """19. Intentional HTTPException triggers rollback and re-raises original exception intact."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    mock_session = create_smart_mock_session(users={caller_id: None, target_id: None})
    service = OwnerRecoveryService(mock_session)

    req = OwnerRecoveryRequest(target_user_id=target_id, justification_ticket_id="SEC-5001", justification_reason="Test intentional exception")
    with pytest.raises(HTTPException) as exc_info:
        await service.recover_ownerless_workspace(ws_id, caller_id, req)

    assert exc_info.value.status_code == 403
    assert "not found or deactivated" in exc_info.value.detail
    mock_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_recovery_intentional_http_exception_cleanup_failure_preserves_exception():
    """20. Intentional HTTPException remains unchanged even if rollback and invalidation both fail."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    mock_session = create_smart_mock_session(users={caller_id: None, target_id: None})
    mock_session.rollback.side_effect = RuntimeError("Rollback driver failure")
    mock_session.invalidate = AsyncMock(side_effect=RuntimeError("Invalidate driver failure"))

    service = OwnerRecoveryService(mock_session)
    req = OwnerRecoveryRequest(target_user_id=target_id, justification_ticket_id="SEC-5002", justification_reason="Test intentional exception with cleanup failure")

    with pytest.raises(HTTPException) as exc_info:
        await service.recover_ownerless_workspace(ws_id, caller_id, req)

    # Primary HTTPException must be preserved without conversion to 500
    assert exc_info.value.status_code == 403
    assert "not found or deactivated" in exc_info.value.detail
    mock_session.rollback.assert_awaited_once()
    mock_session.invalidate.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test Cases 18, 21-24: Tier 2 Unexpected Persistence Exceptions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_audit_flush_failure_triggers_rollback_and_reverts_elevation(test_app):
    """18 & 21. Audit flush failure triggers rollback, reverts in-memory state, and returns HTTP 500."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=target_id, is_active=True, is_verified=True, is_deleted=False)
    db_ws = MagicMock(spec=Workspace, id=ws_id, is_deleted=False)
    target_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=target_id, role="MEMBER", status=MemberStatus.ACTIVE.value, is_deleted=False, version=3)

    mock_session = create_smart_mock_session(
        users={caller_id: db_caller, target_id: db_target},
        workspace=db_ws,
        existing_owners=[],
        target_member=target_member,
    )
    # Simulate DB flush failure during audit log insertion
    mock_session.flush.side_effect = RuntimeError("Simulated DB flush failure")
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-6001",
            "justification_reason": "Testing flush failure rollback handling",
        })
        assert res.status_code == 500
        assert "transaction rolled back" in res.json()["detail"]

    mock_session.rollback.assert_awaited_once()
    mock_session.expunge.assert_called_once_with(target_member)
    assert target_member.role == "MEMBER"
    assert target_member.version == 3


@pytest.mark.asyncio
async def test_recovery_unexpected_exception_rollback_failure_invalidation_success():
    """22. Unexpected exception with rollback failure and successful invalidation -> 500 stating invalidation succeeded."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=target_id, is_active=True, is_verified=True, is_deleted=False)
    db_ws = MagicMock(spec=Workspace, id=ws_id, is_deleted=False)
    target_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=target_id, role="MEMBER", status=MemberStatus.ACTIVE.value, is_deleted=False, version=1)

    mock_session = create_smart_mock_session(
        users={caller_id: db_caller, target_id: db_target},
        workspace=db_ws,
        existing_owners=[],
        target_member=target_member,
    )
    mock_session.flush.side_effect = RuntimeError("Primary DB flush crash")
    mock_session.rollback.side_effect = RuntimeError("Rollback failed")
    mock_session.invalidate = AsyncMock()

    service = OwnerRecoveryService(mock_session)
    req = OwnerRecoveryRequest(target_user_id=target_id, justification_ticket_id="SEC-6002", justification_reason="Testing invalidation success message")

    with pytest.raises(HTTPException) as exc_info:
        await service.recover_ownerless_workspace(ws_id, caller_id, req)

    assert exc_info.value.status_code == 500
    assert "session was invalidated" in exc_info.value.detail
    mock_session.invalidate.assert_awaited_once()


@pytest.mark.asyncio
async def test_recovery_unexpected_exception_both_cleanup_fail():
    """23. Unexpected exception with both rollback and invalidation failure -> 500 stating both failed."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=target_id, is_active=True, is_verified=True, is_deleted=False)
    db_ws = MagicMock(spec=Workspace, id=ws_id, is_deleted=False)
    target_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=target_id, role="MEMBER", status=MemberStatus.ACTIVE.value, is_deleted=False, version=1)

    mock_session = create_smart_mock_session(
        users={caller_id: db_caller, target_id: db_target},
        workspace=db_ws,
        existing_owners=[],
        target_member=target_member,
    )
    mock_session.flush.side_effect = RuntimeError("Primary DB flush crash")
    mock_session.rollback.side_effect = RuntimeError("Rollback failed")
    mock_session.invalidate = AsyncMock(side_effect=RuntimeError("Invalidation failed"))

    service = OwnerRecoveryService(mock_session)
    req = OwnerRecoveryRequest(target_user_id=target_id, justification_ticket_id="SEC-6003", justification_reason="Testing double cleanup failure message")

    with pytest.raises(HTTPException) as exc_info:
        await service.recover_ownerless_workspace(ws_id, caller_id, req)

    assert exc_info.value.status_code == 500
    assert "both transaction rollback and session invalidation failed" in exc_info.value.detail
    mock_session.rollback.assert_awaited_once()
    mock_session.invalidate.assert_awaited_once()


@pytest.mark.asyncio
async def test_recovery_in_memory_target_state_restoration():
    """24. In-memory target state (role, version) restored and entity expunged on failure."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=target_id, is_active=True, is_verified=True, is_deleted=False)
    db_ws = MagicMock(spec=Workspace, id=ws_id, is_deleted=False)
    target_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=target_id, role="MEMBER", status=MemberStatus.ACTIVE.value, is_deleted=False, version=7)

    mock_session = create_smart_mock_session(
        users={caller_id: db_caller, target_id: db_target},
        workspace=db_ws,
        existing_owners=[],
        target_member=target_member,
    )
    mock_session.commit.side_effect = RuntimeError("Simulated commit disk error")

    service = OwnerRecoveryService(mock_session)
    req = OwnerRecoveryRequest(target_user_id=target_id, justification_ticket_id="SEC-6004", justification_reason="Testing in-memory reversion")

    with pytest.raises(HTTPException):
        await service.recover_ownerless_workspace(ws_id, caller_id, req)

    # Assert attributes reverted to pre-mutation values
    assert target_member.role == "MEMBER"
    assert target_member.version == 7
    mock_session.expunge.assert_called_once_with(target_member)


# ---------------------------------------------------------------------------
# Additional Integration / Route Success & Version Increment Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_success_promotes_target_and_emits_audit(test_app):
    """Valid ownerless workspace recovery promotes target to OWNER and creates AuditLog."""
    ws_id = uuid.uuid4()
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()

    user_ctx = UserContext(id=caller_id, email="admin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id, tenant_id=str(ws_id))
    test_app.dependency_overrides[get_current_user] = lambda: user_ctx

    db_caller = MagicMock(spec=User, id=caller_id, is_active=True, is_deleted=False, role="platform_admin")
    db_target = MagicMock(spec=User, id=target_id, is_active=True, is_verified=True, is_deleted=False)
    db_ws = MagicMock(spec=Workspace, id=ws_id, is_deleted=False)
    target_member = WorkspaceMember(id=uuid.uuid4(), workspace_id=ws_id, user_id=target_id, role="MEMBER", status=MemberStatus.ACTIVE.value, is_deleted=False, version=1)

    mock_session = create_smart_mock_session(
        users={caller_id: db_caller, target_id: db_target},
        workspace=db_ws,
        existing_owners=[],
        target_member=target_member,
    )
    test_app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/platform-admin/workspaces/{ws_id}/recover-owner", json={
            "target_user_id": str(target_id),
            "justification_ticket_id": "SEC-9999",
            "justification_reason": "Emergency recovery of orphaned workspace with full justification",
        })
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["workspace_id"] == str(ws_id)
        assert data["promoted_user_id"] == str(target_id)
        assert data["previous_role"] == "MEMBER"
        assert data["new_role"] == "OWNER"
        assert data["justification_ticket_id"] == "SEC-9999"
        assert data["recovery_status"] == "COMPLETED"

    assert target_member.role == "OWNER"
    assert target_member.version == 2
    mock_session.flush.assert_awaited_once()
    mock_session.commit.assert_awaited_once()

    added_objects = [call[0][0] for call in mock_session.add.call_args_list]
    audit_logs = [obj for obj in added_objects if isinstance(obj, AuditLog)]
    assert len(audit_logs) == 1
    audit = audit_logs[0]
    assert audit.action == "WORKSPACE_OWNER_RECOVERED"
    assert audit.tenant_id == ws_id
    assert audit.user_id == caller_id
    assert audit.details["new_role"] == "OWNER"
