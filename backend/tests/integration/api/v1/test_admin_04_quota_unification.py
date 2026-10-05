import pytest
from httpx import AsyncClient, ASGITransport
import uuid
from backend.main import create_app
from backend.modules.analytics.services.quota import QuotaGovernor

app = create_app()

async def setup_test_workspace_user(role: str = "owner", prefix="q_unit"):
    from backend.database.engine import get_session_factory
    from backend.models.entities.user import User
    from backend.models.entities.workspace import Workspace, WorkspaceStatus
    from backend.models.entities.workspace_member import WorkspaceMember, MemberStatus
    from backend.core.security.jwt import get_jwt_service

    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    user_email = f"{prefix}_{uuid.uuid4()}@example.com"

    async with get_session_factory()() as session:
        user = User(
            id=user_id,
            email=user_email,
            hashed_password="mockhashedpassword123",
            display_name=f"{prefix} User",
            is_active=True,
            is_verified=True,
            role=role.lower(),
            tenant_id=str(ws_id),
        )
        session.add(user)

        ws = Workspace(
            id=ws_id,
            name=f"{prefix} Workspace",
            slug=f"{prefix}-ws-{uuid.uuid4().hex[:8]}",
            public_id=f"{prefix.upper()}-PUB-{uuid.uuid4().hex[:6].upper()}",
            storage_prefix=f"workspaces/{ws_id}",
            qdrant_namespace=f"raguard_knowledge_{ws_id}",
            status=WorkspaceStatus.ACTIVE.value,
        )
        session.add(ws)

        member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=user.id,
            role=role.upper() if role else "OWNER",
            status=MemberStatus.ACTIVE.value,
        )
        session.add(member)
        await session.commit()

        jwt_service = get_jwt_service()
        access_token, _, _ = await jwt_service.issue_tokens(user, session)

    return access_token, ws_id

@pytest.mark.asyncio
async def test_admin_quota_mutation_updates_authoritative_tenant_quota():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        access_token, ws_id = await setup_test_workspace_user(role="owner", prefix="q_mut")
        tenant_str = str(ws_id)

        governor = QuotaGovernor()

        # Step 1: Baseline check
        initial_quota = await governor.get_quota_settings(workspace_id=ws_id)
        assert initial_quota.monthly_token_limit == 10_000_000

        # Step 2: Mutate quota to 2000 through API
        res_put = await client.put(
            f"/api/v1/analytics/v1/quotas/{tenant_str}",
            json={
                "monthly_token_limit": 2000,
                "monthly_budget_usd": 50.0,
                "warning_threshold_pct": 0.70,
                "is_hard_enforced": True,
            },
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert res_put.status_code == 200
        data = res_put.json()
        assert data["monthly_token_limit"] == 2000
        assert data["monthly_budget_usd"] == 50.0

        # Step 3: Verify QuotaGovernor reads the exact same value
        gov_quota = await governor.get_quota_settings(workspace_id=ws_id)
        assert gov_quota.monthly_token_limit == 2000
        assert gov_quota.monthly_budget_usd == 50.0
        assert gov_quota.is_hard_enforced is True

        # Step 4: Verify check_quota uses the updated limit
        is_exceeded, used, limit, is_hard = await governor.check_quota(workspace_id=ws_id)
        assert limit == 2000
        assert is_exceeded is False

        # Step 5: Test lower value (500)
        res_put_lower = await client.put(
            f"/api/v1/analytics/v1/quotas/{tenant_str}",
            json={"monthly_token_limit": 500},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert res_put_lower.status_code == 200
        assert res_put_lower.json()["monthly_token_limit"] == 500

        # Verify QuotaGovernor immediately reflects 500
        gov_quota_500 = await governor.get_quota_settings(workspace_id=ws_id)
        assert gov_quota_500.monthly_token_limit == 500

        # Step 6: Verify GET endpoint returns authoritative 500
        res_get = await client.get(
            f"/api/v1/analytics/v1/quotas/{tenant_str}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert res_get.status_code == 200
        assert res_get.json()["monthly_token_limit"] == 500

@pytest.mark.asyncio
async def test_quota_governor_runtime_enforcement_blocks_when_exceeded():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        access_token, ws_id = await setup_test_workspace_user(role="owner", prefix="q_enf")
        tenant_str = str(ws_id)

        governor = QuotaGovernor()

        # Set limit to 100 tokens with hard enforcement
        res_put = await client.put(
            f"/api/v1/analytics/v1/quotas/{tenant_str}",
            json={
                "monthly_token_limit": 100,
                "is_hard_enforced": True,
            },
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert res_put.status_code == 200

        # Consume 150 tokens
        await governor.record_usage(workspace_id=ws_id, tokens=150, queries=1)

        # check_quota must report exceeded
        is_exceeded, used, limit, is_hard = await governor.check_quota(workspace_id=ws_id)
        assert is_exceeded is True
        assert used >= 150
        assert limit == 100

        # Now raise limit to 500
        res_put2 = await client.put(
            f"/api/v1/analytics/v1/quotas/{tenant_str}",
            json={"monthly_token_limit": 500},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert res_put2.status_code == 200

        # check_quota must now report NOT exceeded
        is_exceeded2, used2, limit2, is_hard2 = await governor.check_quota(workspace_id=ws_id)
        assert is_exceeded2 is False
        assert limit2 == 500

@pytest.mark.asyncio
async def test_quota_mutation_rbac_and_tenant_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        owner_tok, ws1 = await setup_test_workspace_user(role="owner", prefix="q_rb_o")
        member_tok, ws2 = await setup_test_workspace_user(role="member", prefix="q_rb_m")

        # Member rejected (403)
        res_mem = await client.put(
            f"/api/v1/analytics/v1/quotas/{ws2}",
            json={"monthly_token_limit": 1000},
            headers={"Authorization": f"Bearer {member_tok}"}
        )
        assert res_mem.status_code == 403

        # Cross-tenant mutation rejected (403)
        res_cross = await client.put(
            f"/api/v1/analytics/v1/quotas/{ws2}",
            json={"monthly_token_limit": 1000},
            headers={"Authorization": f"Bearer {owner_tok}"}
        )
        assert res_cross.status_code == 403

        # Unauthenticated rejected (401)
        res_unauth = await client.put(
            f"/api/v1/analytics/v1/quotas/{ws1}",
            json={"monthly_token_limit": 1000}
        )
        assert res_unauth.status_code == 401

@pytest.mark.asyncio
async def test_quota_validation_rejects_invalid_values():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        owner_tok, ws = await setup_test_workspace_user(role="owner", prefix="q_val")

        # Negative token limit -> 422
        res_neg = await client.put(
            f"/api/v1/analytics/v1/quotas/{ws}",
            json={"monthly_token_limit": -100},
            headers={"Authorization": f"Bearer {owner_tok}"}
        )
        assert res_neg.status_code == 422

        # Zero token limit -> 422
        res_zero = await client.put(
            f"/api/v1/analytics/v1/quotas/{ws}",
            json={"monthly_token_limit": 0},
            headers={"Authorization": f"Bearer {owner_tok}"}
        )
        assert res_zero.status_code == 422

        # Negative budget -> 422
        res_neg_budget = await client.put(
            f"/api/v1/analytics/v1/quotas/{ws}",
            json={"monthly_budget_usd": -10.0},
            headers={"Authorization": f"Bearer {owner_tok}"}
        )
        assert res_neg_budget.status_code == 422

        # Invalid warning threshold (> 1.0) -> 422
        res_warn_high = await client.put(
            f"/api/v1/analytics/v1/quotas/{ws}",
            json={"warning_threshold_pct": 1.5},
            headers={"Authorization": f"Bearer {owner_tok}"}
        )
        assert res_warn_high.status_code == 422

@pytest.mark.asyncio
async def test_workspace_settings_patch_synchronizes_tenant_quota():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        owner_tok, ws = await setup_test_workspace_user(role="owner", prefix="q_ws_sync")

        # Fetch settings to get updated_at
        res_get = await client.get(
            f"/api/v1/workspaces/{ws}/settings",
            headers={"Authorization": f"Bearer {owner_tok}"}
        )
        assert res_get.status_code == 200
        updated_at = res_get.json()["data"]["updated_at"]

        # Patch workspace settings with limits.monthly_token_budget = 4000
        res_patch = await client.patch(
            f"/api/v1/workspaces/{ws}/settings",
            json={
                "expected_updated_at": updated_at,
                "settings": {
                    "limits": {
                        "monthly_token_budget": 4000,
                    }
                }
            },
            headers={"Authorization": f"Bearer {owner_tok}"}
        )
        assert res_patch.status_code == 200

        # Verify QuotaGovernor reads synchronized 4000
        governor = QuotaGovernor()
        quota = await governor.get_quota_settings(workspace_id=ws)
        assert quota.monthly_token_limit == 4000
