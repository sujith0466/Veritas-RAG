import pytest
from httpx import AsyncClient, ASGITransport
import uuid
from backend.main import create_app

app = create_app()

async def setup_test_user(client: AsyncClient, role: str = "admin", prefix="quota"):
    user_email = f"{prefix}_{uuid.uuid4()}@example.com"
    password = "StrongPassword123!"

    reg_res = await client.post("/api/v1/auth/register", json={
        "email": user_email,
        "password": password,
        "full_name": f"{prefix} User"
    })
    assert reg_res.status_code == 201

    from sqlalchemy import text
    from backend.database.engine import get_session_factory
    async with get_session_factory()() as session:
        await session.execute(
            text("UPDATE users SET is_verified = true, role = :role, workspace_name = :tid WHERE email = :email"),
            {"email": user_email, "role": role, "tid": str(uuid.uuid4())}
        )
        await session.commit()

        result = await session.execute(
            text("SELECT id, tenant_id, workspace_name FROM users WHERE email = :email"),
            {"email": user_email}
        )
        user_row = result.fetchone()

        # Need a workspace name if tenant_id is used from it
        if not user_row.tenant_id and user_row.workspace_name:
            tenant_id = user_row.workspace_name
        else:
            tenant_id = str(user_row.tenant_id) if user_row.tenant_id else str(uuid.uuid4())
            # For tests where tenant_id might not be set automatically
            await session.execute(
                text("UPDATE users SET tenant_id = :tid, workspace_name = :tid WHERE email = :email"),
                {"email": user_email, "tid": tenant_id}
            )
            await session.commit()

    login_res = await client.post("/api/v1/auth/login", json={
        "email": user_email,
        "password": password
    })
    assert login_res.status_code == 200
    access_token = login_res.json()["data"]["access_token"]

    return access_token, tenant_id

@pytest.mark.asyncio
async def test_quotas_unauthenticated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/v1/analytics/v1/quotas/{uuid.uuid4()}")
        assert res.status_code == 401

@pytest.mark.asyncio
async def test_quotas_rbac_forbidden():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        access_token, tenant_id = await setup_test_user(client, role="viewer", prefix="qf")
        res = await client.get(f"/api/v1/analytics/v1/quotas/{tenant_id}", headers={"Authorization": f"Bearer {access_token}"})
        assert res.status_code == 403

@pytest.mark.asyncio
async def test_quotas_tenant_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        access_token1, tenant_id1 = await setup_test_user(client, role="admin", prefix="qt1")
        access_token2, tenant_id2 = await setup_test_user(client, role="admin", prefix="qt2")

        # User 1 tries to access User 2's quota
        res = await client.get(f"/api/v1/analytics/v1/quotas/{tenant_id2}", headers={"Authorization": f"Bearer {access_token1}"})
        assert res.status_code == 403

@pytest.mark.asyncio
async def test_quotas_crud_owner():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        access_token, tenant_id = await setup_test_user(client, role="owner", prefix="qo")

        res = await client.get(f"/api/v1/analytics/v1/quotas/{tenant_id}", headers={"Authorization": f"Bearer {access_token}"})
        assert res.status_code == 200
        assert res.json()["monthly_token_limit"] == 10000000

        res_put = await client.put(f"/api/v1/analytics/v1/quotas/{tenant_id}", json={
            "monthly_token_limit": 5000,
            "monthly_budget_usd": 10.0,
            "warning_threshold_pct": 0.5,
            "is_hard_enforced": True
        }, headers={"Authorization": f"Bearer {access_token}"})
        assert res_put.status_code == 200
        assert res_put.json()["monthly_token_limit"] == 5000
