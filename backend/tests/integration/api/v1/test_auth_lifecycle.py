import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import create_app
import uuid
import asyncio

app = create_app()

@pytest.mark.asyncio
async def test_auth_full_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register
        user_email = f"test_{uuid.uuid4()}@example.com"
        password = "Password123!"

        reg_res = await client.post("/api/v1/auth/register", json={
            "email": user_email,
            "password": password,
            "full_name": "Test User"
        })
        assert reg_res.status_code == 201

        # Bypass email verification for testing
        from sqlalchemy import text
        from backend.database.engine import get_session_factory
        async with get_session_factory()() as session:
            await session.execute(
                text("UPDATE users SET is_verified = true WHERE email = :email"),
                {"email": user_email}
            )
            await session.commit()

        # 2. Login
        login_res = await client.post("/api/v1/auth/login", json={
            "email": user_email,
            "password": password
        })
        assert login_res.status_code == 200
        access_token = login_res.json()["data"]["access_token"]
        assert access_token is not None

        # Verify cookie is set
        cookies = client.cookies
        assert "refresh_token" in cookies

        # 3. GET /auth/me
        me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert me_res.status_code == 200
        assert me_res.json()["data"]["email"] == user_email

        # 4. Forged JWT -> 401
        forged_token = access_token[:-5] + "aaaaa"
        forged_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
        assert forged_res.status_code == 401

        # Extract cookie from headers
        set_cookie_header = login_res.headers.get("set-cookie", "")
        import re
        match = re.search(r"refresh_token=([^;]+)", set_cookie_header)
        old_refresh_token = match.group(1) if match else ""

        # 5. Refresh rotation -> success
        refresh_res = await client.post(
            "/api/v1/auth/refresh",
            headers={"Cookie": f"refresh_token={old_refresh_token}"}
        )
        assert refresh_res.status_code == 200, refresh_res.text
        new_access_token = refresh_res.json()["data"]["access_token"]
        assert new_access_token != access_token

        new_refresh_cookie = refresh_res.cookies.get("refresh_token")
        assert new_refresh_cookie != old_refresh_token

        # 6. Refresh replay -> 401 (use the old refresh cookie explicitly)
        replay_res = await client.post(
            "/api/v1/auth/refresh",
            headers={"Cookie": f"refresh_token={old_refresh_token}"}
        )
        assert replay_res.status_code == 401

        # 7. Password change -> success
        # Login again since token family might be compromised or we just want fresh token
        login_res2 = await client.post("/api/v1/auth/login", json={
            "email": user_email,
            "password": password
        })
        assert login_res2.status_code == 200
        access_token_3 = login_res2.json()["data"]["access_token"]

        new_password = "NewPassword123!"
        pw_change_res = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": password,
                "new_password": new_password
            },
            headers={"Authorization": f"Bearer {access_token_3}"}
        )
        assert pw_change_res.status_code == 200

        # 8. Old token after global revocation -> rejected
        old_token_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token_3}"})
        assert old_token_res.status_code == 401
