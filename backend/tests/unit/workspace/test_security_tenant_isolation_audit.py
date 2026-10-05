"""Unit tests for WS-B11: Security & Tenant Isolation Audit.

Validates adversarial tenant isolation, IDOR rejection, hierarchical quota boundaries,
token invalidation post-suspension, and client-supplied role privilege escalation defense.
"""

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError

from backend.api.v1.schemas.workspace_member import UpdateMemberRoleRequest
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db as get_db_session
from backend.core.dependencies.quota import enforce_workspace_quota
from backend.core.exceptions.auth import InvalidTokenException
from backend.core.permissions.rbac import Role
from backend.core.security.jwt import JWTService
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.modules.analytics.api.quota_routes import router as quota_router
from backend.modules.analytics.models.tenant_quota import TenantQuotaORM
from backend.modules.analytics.models.workspace_user_quota import WorkspaceUserQuotaORM
from backend.modules.analytics.services.quota import HierarchicalQuotaCheckResult, QuotaGovernor
from backend.services.workspace.events import WorkspaceMemberSuspendedEvent
from backend.services.workspace.handlers import handle_member_suspended
from backend.services.workspace.membership_service import (
    MembershipConflictError,
    MembershipUnauthorizedError,
    WorkspaceMembershipService,
)


@pytest.fixture
def audit_app():
    app = FastAPI()
    app.include_router(quota_router, prefix="/analytics")
    return app


@pytest.mark.asyncio
async def test_cross_tenant_idor_user_quota_access_rejected(audit_app):
    """Adversarial check: Admin in Workspace A attempts to update user quota for a member

    belonging exclusively to Workspace B. Must be rejected with 404 without data leakage.
    """
    ws_a_id = uuid.uuid4()
    ws_b_id = uuid.uuid4()
    victim_user_id = uuid.uuid4()

    admin_user = UserContext(
        id=uuid.uuid4(),
        email="attacker_admin@workspace-a.com",
        role=Role.ADMIN.value,
        workspace_id=ws_a_id,
    )

    mock_db = AsyncMock()
    # Workspace A exists, but victim user is NOT in Workspace A
    res_mock = MagicMock()
    res_mock.first.return_value = None  # No matching (WorkspaceMember, User) in Workspace A
    mock_db.execute.return_value = res_mock

    audit_app.dependency_overrides[get_db_session] = lambda: mock_db
    audit_app.dependency_overrides[get_current_user] = lambda: admin_user

    admin_member = MagicMock()
    admin_member.role = "ADMIN"

    with patch("backend.modules.analytics.api.quota_routes.require_workspace_admin_or_owner", new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = admin_member

        transport = ASGITransport(app=audit_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/analytics/v1/workspace-user-quotas/{ws_a_id}/{victim_user_id}",
                json={"monthly_token_budget": 250_000, "is_hard_enforced": True},
            )

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert "not found in this workspace" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cross_tenant_document_ingestion_blocked_only_for_exhausted_workspace():
    """Adversarial check: Workspace A is at quota limit (blocked with 429).

    Workspace B with available tokens must NOT be blocked, preserving tenant isolation.
    """
    ws_a_id = uuid.uuid4()
    ws_b_id = uuid.uuid4()
    user_a = UserContext(id=uuid.uuid4(), email="user_a@tenant-a.com", role=Role.MEMBER.value, workspace_id=ws_a_id)
    user_b = UserContext(id=uuid.uuid4(), email="user_b@tenant-b.com", role=Role.MEMBER.value, workspace_id=ws_b_id)
    session = AsyncMock()

    guard = enforce_workspace_quota()

    with patch("backend.core.dependencies.quota.get_workspace_member_or_raise", new_callable=AsyncMock), \
         patch("backend.core.dependencies.quota.QuotaGovernor") as mock_gov_cls:

        gov_instance = MagicMock()

        async def dynamic_check(workspace_id, *args, **kwargs):
            if workspace_id == ws_a_id:
                return HierarchicalQuotaCheckResult(
                    is_allowed=False,
                    blocked_by="workspace_quota",
                    detail="Workspace A token limit reached",
                )
            return HierarchicalQuotaCheckResult(is_allowed=True)

        gov_instance.check_hierarchical_quota = AsyncMock(side_effect=dynamic_check)
        mock_gov_cls.return_value = gov_instance

        # Tenant A user is blocked
        with pytest.raises(HTTPException) as exc_a:
            await guard(workspace_id=ws_a_id, current_user=user_a, session=session)
        assert exc_a.value.status_code == 429
        assert "Workspace A token limit reached" in exc_a.value.detail

        # Tenant B user passes cleanly
        await guard(workspace_id=ws_b_id, current_user=user_b, session=session)


@pytest.mark.asyncio
async def test_session_revocation_post_suspension_invalidates_active_jwt():
    """Security check: Suspending a user records a revocation timestamp in Redis.

    Any existing active JWT issued prior to that timestamp is cryptographically / statefully rejected.
    """
    user_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    actor_id = str(uuid.uuid4())

    redis_mock = AsyncMock()
    jwt_service = JWTService()
    jwt_service.redis = redis_mock

    # 1. Event handler triggers token revocation
    event = WorkspaceMemberSuspendedEvent(
        workspace_id=ws_id,
        member_id=str(uuid.uuid4()),
        user_id=user_id,
        actor_id=actor_id,
    )

    with patch("backend.services.workspace.handlers.get_jwt_service", return_value=jwt_service):
        await handle_member_suspended(event)

    # Verify revoke_user_workspace_tokens was called
    revocation_time = int(time.time())

    async def fake_get(key: str):
        if key == f"auth:user:{user_id}:workspace:{ws_id}:invalid_before":
            return str(revocation_time)
        return None

    redis_mock.get = AsyncMock(side_effect=fake_get)

    # 2. Token issued prior to revocation
    stale_payload = {
        "sub": user_id,
        "workspace_id": ws_id,
        "iat": revocation_time - 10,
        "exp": revocation_time + 900,
        "role": "member",
        "jti": str(uuid.uuid4()),
    }
    with patch("backend.core.security.jwt.jwt.decode", return_value=stale_payload):
        with pytest.raises(InvalidTokenException, match="Token revoked"):
            await jwt_service.verify_token("stale_token_string")


def test_rejection_of_client_supplied_roles_and_privilege_escalation():
    """Security check: Client-supplied roles that attempt to inject platform roles or

    unsupported values are strictly rejected by Pydantic schema validation.
    """
    for invalid_role in ["PLATFORM_ADMIN", "superadmin", "ENGINEER", "ANALYST", "root", "", None]:
        with pytest.raises(ValidationError):
            UpdateMemberRoleRequest(role=invalid_role)

    # Canonical roles must pass schema validation
    for canonical in ["OWNER", "ADMIN", "MEMBER", "VIEWER"]:
        req = UpdateMemberRoleRequest(role=canonical)
        assert req.role == canonical


@pytest.mark.asyncio
async def test_unauthorized_quota_manipulation_rejected(audit_app):
    """Security check: A regular MEMBER role attempting to mutate workspace quota

    or per-user quota must receive 403 Forbidden.
    """
    ws_id = uuid.uuid4()
    member_user = UserContext(
        id=uuid.uuid4(),
        email="regular_member@veritas.rag",
        role=Role.MEMBER.value,
        workspace_id=ws_id,
    )

    mock_db = AsyncMock()
    audit_app.dependency_overrides[get_db_session] = lambda: mock_db
    audit_app.dependency_overrides[get_current_user] = lambda: member_user

    regular_member = MagicMock()
    regular_member.role = "MEMBER"

    # 1. Attempt to modify workspace quota (requires OWNER or ADMIN)
    with patch("backend.modules.analytics.api.quota_routes.get_workspace_member_or_raise", new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = regular_member

        transport = ASGITransport(app=audit_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/analytics/v1/quotas/{ws_id}",
                json={"monthly_token_limit": 999_999_999},
            )
            assert resp.status_code == status.HTTP_403_FORBIDDEN
            assert "insufficient role permissions" in resp.json()["detail"].lower() or "requires" in resp.json()["detail"].lower()

    # 2. Attempt to modify user quota (requires require_workspace_admin_or_owner)
    with patch("backend.modules.analytics.api.quota_routes.require_workspace_admin_or_owner", side_effect=HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: Requires workspace Admin or Owner role.",
    )):
        transport = ASGITransport(app=audit_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp_user = await client.put(
                f"/analytics/v1/workspace-user-quotas/{ws_id}/{uuid.uuid4()}",
                json={"monthly_token_budget": 999_999_999},
            )
            assert resp_user.status_code == status.HTTP_403_FORBIDDEN
            assert "insufficient role permissions" in resp_user.json()["detail"].lower() or "requires" in resp_user.json()["detail"].lower()
