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
        "full_name": f"{prefix} User",
    })
    assert reg_res.status_code == 201

    from sqlalchemy import select
    from backend.database.engine import get_session_factory
    from backend.models.entities.user import User
    from backend.models.entities.workspace import Workspace, WorkspaceStatus
    from backend.models.entities.workspace_member import WorkspaceMember, MemberStatus

    ws_id = uuid.uuid4()
    async with get_session_factory()() as session:
        user = (await session.execute(select(User).where(User.email == user_email))).scalar_one()
        user.is_verified = True
        user.role = role

        ws = Workspace(
            id=ws_id,
            name=f"{prefix} Workspace",
            slug=f"{prefix}-ws-{uuid.uuid4().hex[:8]}",
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
        user.tenant_id = str(ws_id)
        await session.commit()

    login_res = await client.post("/api/v1/auth/login", json={
        "email": user_email,
        "password": password
    })
    assert login_res.status_code == 200
    access_token = login_res.json()["data"]["access_token"]

    return access_token, str(ws_id)

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
