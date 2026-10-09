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

        # 7. Password change
        # Login again since token family might be compromised or we just want fresh token
        login_res2 = await client.post("/api/v1/auth/login", json={
            "email": user_email,
            "password": password
        })
        assert login_res2.status_code == 200
        access_token_3 = login_res2.json()["data"]["access_token"]

        new_password = "NewPassword123!"

        # 7a. Path A: Incorrect current password is rejected with 401 Unauthorized
        invalid_pwd_attempt = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "WrongPassword999!",
                "new_password": new_password
            },
            headers={"Authorization": f"Bearer {access_token_3}"}
        )
        assert invalid_pwd_attempt.status_code == 401

        # 7b. Authorized security-code flow
        from unittest.mock import AsyncMock, patch
        with patch("backend.services.auth.password_reset_service.get_email_provider") as mock_email_fn:
            mock_provider = AsyncMock()
            mock_provider.send_security_code_email = AsyncMock(return_value=True)
            mock_email_fn.return_value = mock_provider

            # Request code
            req_code = await client.post(
                "/api/v1/auth/change-password/request-code",
                headers={"Authorization": f"Bearer {access_token_3}"}
            )
            assert req_code.status_code == 200
            _, raw_code = mock_provider.send_security_code_email.call_args[0]

            # Verify code -> change_token
            verify_res = await client.post(
                "/api/v1/auth/change-password/verify-code",
                json={"code": raw_code},
                headers={"Authorization": f"Bearer {access_token_3}"}
            )
            assert verify_res.status_code == 200
            change_token = verify_res.json()["data"]["change_token"]

            # Complete password change
            pw_change_res = await client.post(
                "/api/v1/auth/change-password/complete",
                json={
                    "change_token": change_token,
                    "new_password": new_password
                },
                headers={"Authorization": f"Bearer {access_token_3}"}
            )
            assert pw_change_res.status_code == 200

        # 8. Old token after global revocation -> rejected
        old_token_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token_3}"})
        assert old_token_res.status_code == 401
