import pytest
from httpx import AsyncClient, ASGITransport
import uuid
from backend.main import create_app

app = create_app()

async def setup_test_user(client: AsyncClient, role: str = "admin", prefix="plat"):
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

    login_res = await client.post("/api/v1/auth/login", json={
        "email": user_email,
        "password": password
    })
    assert login_res.status_code == 200
    access_token = login_res.json()["data"]["access_token"]

    return access_token

@pytest.mark.asyncio
async def test_platform_admin_workspaces_unauthenticated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/platform-admin/workspaces")
        assert res.status_code == 401

@pytest.mark.asyncio
async def test_platform_admin_workspaces_forbidden_roles():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        access_token = await setup_test_user(client, role="admin", prefix="pf")
        res = await client.get("/api/v1/platform-admin/workspaces", headers={"Authorization": f"Bearer {access_token}"})
        assert res.status_code == 403

@pytest.mark.asyncio
async def test_platform_admin_workspaces_allowed():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        access_token = await setup_test_user(client, role="platform_admin", prefix="pa")
        res = await client.get("/api/v1/platform-admin/workspaces", headers={"Authorization": f"Bearer {access_token}"})
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert isinstance(data["items"], list)
