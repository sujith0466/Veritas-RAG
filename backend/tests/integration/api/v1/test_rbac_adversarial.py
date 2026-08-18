import pytest
from httpx import AsyncClient, ASGITransport
import uuid
from backend.main import create_app

app = create_app()

async def setup_test_user(client: AsyncClient, role: str = "admin", prefix="adv"):
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

        workspace_id = user_row.workspace_name
        if not workspace_id:
            workspace_id = str(user_row.tenant_id)

    login_res = await client.post("/api/v1/auth/login", json={
        "email": user_email,
        "password": password
    })
    assert login_res.status_code == 200
    access_token = login_res.json()["data"]["access_token"]

    return access_token, workspace_id

@pytest.mark.asyncio
async def test_rbac_and_workspace_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        access_token1, workspace_id1 = await setup_test_user(client, role="admin", prefix="iso1")
        access_token2, workspace_id2 = await setup_test_user(client, role="admin", prefix="iso2")

        # User 1 tries to access User 2's workspace directly
        res = await client.get(f"/api/v1/workspaces/{workspace_id2}", headers={"Authorization": f"Bearer {access_token1}"})
        # The endpoint returns 404 when access is denied to avoid leaking existence, or 403
        assert res.status_code in (403, 404)

        # User 2 tries to access User 1's workspace directly
        res2 = await client.get(f"/api/v1/workspaces/{workspace_id1}", headers={"Authorization": f"Bearer {access_token2}"})
        assert res2.status_code in (403, 404)
