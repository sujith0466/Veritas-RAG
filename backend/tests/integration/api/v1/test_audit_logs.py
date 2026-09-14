import pytest
from httpx import AsyncClient, ASGITransport
import uuid
from backend.main import create_app

app = create_app()

async def setup_test_user(client: AsyncClient, role: str = "admin", prefix="aud"):
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
            role=role.upper() if role else "ADMIN",
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

    return access_token

@pytest.mark.asyncio
async def test_audit_logs_unauthenticated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/audit-logs")
        assert res.status_code == 401

@pytest.mark.asyncio
async def test_audit_logs_rbac_forbidden():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        access_token = await setup_test_user(client, role="viewer", prefix="forbidden")
        res = await client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {access_token}"})
        assert res.status_code == 403

@pytest.mark.asyncio
async def test_audit_logs_rbac_allowed():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        access_token = await setup_test_user(client, role="admin", prefix="allowed")
        res = await client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {access_token}"})
        assert res.status_code == 200

@pytest.mark.asyncio
async def test_audit_logs_filtering_and_pagination():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        access_token = await setup_test_user(client, role="owner", prefix="pagi")
        res = await client.get("/api/v1/audit-logs?page=1&page_size=10", headers={"Authorization": f"Bearer {access_token}"})
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "pagination" in data

@pytest.mark.asyncio
async def test_audit_logs_tenant_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        access_token1 = await setup_test_user(client, role="admin", prefix="t1")
        access_token2 = await setup_test_user(client, role="admin", prefix="t2")

        res1 = await client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {access_token1}"})
        assert res1.status_code == 200

        res2 = await client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {access_token2}"})
        assert res2.status_code == 200
