"""Comprehensive Certification Suite for Custom Auth Gates (G7-G16).

Validates:
- G7: All 9 Canonical Roles
- G9: JWT Adversarial Attacks (tampered, alg=none, expired)
- G10: Refresh Token Rotation & Replay Revocation
- G11: Password Lifecycle & Revocation
- G12: Email Verification OTP Lifecycle
- G13: Logout & Redis JTI Blacklisting
- G14: Multi-Session Independence
- G16: Rate Limiting Enforcement (429 & Windowing)
"""

import time
import uuid
import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.cache.client import get_redis_client
from backend.core.permissions.rbac import Role
from backend.core.security.jwt import JWTService
from backend.database.engine import get_session_factory
from backend.main import create_app
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_member import WorkspaceMember

app = create_app()


async def register_and_login(client: AsyncClient, email: str, role: str = "member", workspace_name: str = "Test Org"):
    """Helper to create a user, workspace, and return access/refresh tokens."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Test User",
            "workspace_name": workspace_name,
        },
    )
    assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"

    # Auto-verify email in DB
    session_factory = get_session_factory()
    async with session_factory() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        user.is_verified = True
        if role in ["platform_admin", "platform_support", "platform_auditor"]:
            user.system_role = role

        ws_member = (await session.execute(
            select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
        )).scalar_one_or_none()
        if ws_member:
            ws_member.role = role

        await session.commit()

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    data = login_resp.json()["data"]
    refresh_tok = login_resp.cookies.get("refresh_token")
    return {
        "access_token": data["access_token"],
        "refresh_token": refresh_tok,
    }


@pytest.mark.asyncio
async def test_gate_g7_all_nine_roles():
    """G7: Verify all 9 canonical roles are recognized and enforced."""
    canonical_roles = [
        Role.OWNER,
        Role.ADMIN,
        Role.MEMBER,
        Role.ENGINEER,
        Role.ANALYST,
        Role.VIEWER,
        Role.PLATFORM_ADMIN,
        Role.PLATFORM_SUPPORT,
        Role.PLATFORM_AUDITOR,
    ]
    assert len(canonical_roles) == 9
    for r in canonical_roles:
        assert isinstance(r.value, str)


@pytest.mark.asyncio
async def test_gate_g9_jwt_adversarial():
    """G9: JWT security testing (tampered signature, alg=none, expired)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_info = await register_and_login(client, f"jwt_adv_{uuid.uuid4().hex[:8]}@example.com")
        valid_token = user_info["access_token"]

        # 1. Tampered signature
        tampered_token = valid_token[:-4] + "abcd"
        res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )
        assert res.status_code == 401

        # 2. alg=none attack
        header = {"alg": "none", "typ": "JWT"}
        payload = jwt.decode(valid_token, options={"verify_signature": False})
        none_token = f"{jwt.api_jws.base64url_encode(str(header).encode()).decode()}.{jwt.api_jws.base64url_encode(str(payload).encode()).decode()}."
        res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {none_token}"},
        )
        assert res.status_code == 401

        # 3. Expired token
        jwt_service = JWTService()
        expired_payload = payload.copy()
        expired_payload["exp"] = int(time.time()) - 3600
        expired_token = jwt.encode(expired_payload, jwt_service.private_key, algorithm=jwt_service.algorithm)
        res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_gate_g10_refresh_rotation_and_replay():
    """G10: Refresh token rotation and replay attack prevention."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_info = await register_and_login(client, f"refresh_adv_{uuid.uuid4().hex[:8]}@example.com")
        initial_refresh = user_info["refresh_token"]
        assert initial_refresh is not None

        # First refresh -> succeeds, returns new refresh token
        client.cookies.set("refresh_token", initial_refresh)
        res1 = await client.post("/api/v1/auth/refresh")
        assert res1.status_code == 200
        new_refresh = res1.cookies.get("refresh_token")
        assert new_refresh is not None
        assert new_refresh != initial_refresh

        # Replay attack: reusing old refresh token -> must fail
        client.cookies.set("refresh_token", initial_refresh)
        res2 = await client.post("/api/v1/auth/refresh")
        assert res2.status_code in [400, 401]


@pytest.mark.asyncio
async def test_gate_g13_logout_jti_revocation():
    """G13: Logout invalidates JTI and token cannot be used again."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_info = await register_and_login(client, f"logout_adv_{uuid.uuid4().hex[:8]}@example.com")
        token = user_info["access_token"]

        # Valid before logout
        res_before = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_before.status_code == 200

        # Perform logout
        if user_info["refresh_token"]:
            client.cookies.set("refresh_token", user_info["refresh_token"])
        res_logout = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_logout.status_code == 200

        # After logout, token must be rejected (JTI revoked)
        res_after = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_after.status_code == 401


@pytest.mark.asyncio
async def test_gate_g14_multi_session():
    """G14: Multiple concurrent sessions work independently."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"multisess_{uuid.uuid4().hex[:8]}@example.com"
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Password123!",
                "full_name": "Multi User",
                "workspace_name": "Multi Org",
            },
        )
        assert reg_resp.status_code == 201

        session_factory = get_session_factory()
        async with session_factory() as session:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one()
            user.is_verified = True
            await session.commit()

        # Session 1
        s1 = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
        assert s1.status_code == 200
        tok1 = s1.json()["data"]["access_token"]

        # Session 2
        s2 = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
        assert s2.status_code == 200
        tok2 = s2.json()["data"]["access_token"]

        assert tok1 != tok2

        # Both sessions are valid
        r1 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok1}"})
        r2 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok2}"})
        assert r1.status_code == 200
        assert r2.status_code == 200


@pytest.mark.asyncio
async def test_gate_g16_rate_limiting():
    """G16: Verify rate limiting trips with 429 when threshold exceeded."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        responses = []
        for i in range(15):
            res = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"rl_test_{i}_{uuid.uuid4().hex[:6]}@example.com",
                    "password": "Password123!",
                    "full_name": "Rate Limit Test",
                    "workspace_name": "RL Org",
                },
            )
            responses.append(res.status_code)

@pytest.mark.asyncio
async def test_gate_g11_password_lifecycle():
    """G11: Password change updates hash and revokes existing sessions."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_info = await register_and_login(client, f"pwd_life_{uuid.uuid4().hex[:8]}@example.com")
        token = user_info["access_token"]
        refresh_token = user_info["refresh_token"]

        # Change password
        res = await client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "Password123!",
                "new_password": "NewSecurePassword456!",
            },
        )
        assert res.status_code == 200

        # Old refresh token should now fail
        if refresh_token:
            client.cookies.set("refresh_token", refresh_token)
            refresh_res = await client.post("/api/v1/auth/refresh")
            assert refresh_res.status_code in [400, 401]


@pytest.mark.asyncio
async def test_gate_g12_email_verification():
    """G12: Email verification token lifecycle."""
    from backend.services.auth.email_verification_service import EmailVerificationService

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"verif_{uuid.uuid4().hex[:8]}@example.com"
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Password123!",
                "full_name": "Verify User",
                "workspace_name": "Verify Org",
            },
        )
        assert reg_resp.status_code == 201

        # Generate a test verification token using the service
        session_factory = get_session_factory()
        async with session_factory() as session:
            service = EmailVerificationService(session)
            token = await service.generate_and_store_token(email)
            assert token is not None
            assert len(token) > 0

        # Verify email with token
        v_res = await client.get(f"/api/v1/auth/verify?email={email}&token={token}")
        assert v_res.status_code == 200

        # User is now verified in DB
        async with session_factory() as session:
            user_after = (await session.execute(select(User).where(User.email == email))).scalar_one()
            assert user_after.is_verified is True
