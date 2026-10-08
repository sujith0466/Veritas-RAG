"""Integration tests for Enterprise Password Recovery API endpoints."""

import asyncio
import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from backend.cache.client import get_redis_client
from backend.core.security.jwt import get_jwt_service
from backend.core.security.password import get_password_hash
from backend.database.engine import get_session_factory
from backend.main import create_app
from backend.models.entities.password_otp import PasswordRecoveryOTP
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole

app = create_app()


async def create_api_test_user():
    session_factory = get_session_factory()
    unique_email = f"recovery_api_{uuid.uuid4().hex[:8]}@example.com"
    initial_password = "InitialPassword123!"
    user_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    rand_hex = uuid.uuid4().hex[:6]

    async with session_factory() as session:
        user = User(
            id=user_id,
            email=unique_email,
            hashed_password=get_password_hash(initial_password),
            is_active=True,
            is_verified=True,
            role="member",
        )
        session.add(user)

        workspace = Workspace(
            id=workspace_id,
            name=f"WS_{rand_hex}",
            slug=f"ws-{rand_hex}",
            public_id=f"pub_{rand_hex}",
            storage_prefix=f"sp_{rand_hex}",
            qdrant_namespace=f"qn_{rand_hex}",
        )
        session.add(workspace)

        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=WorkspaceRole.MEMBER.value,
            status=MemberStatus.ACTIVE.value,
        )
        session.add(member)
        await session.commit()

    return {
        "id": user_id,
        "email": unique_email,
        "password": initial_password,
        "workspace_id": workspace_id,
    }


async def cleanup_api_test_user(user_id: uuid.UUID, workspace_id: uuid.UUID):
    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(text("DELETE FROM user_sessions WHERE user_id = :uid"), {"uid": user_id})
        await session.execute(text("DELETE FROM password_recovery_otps WHERE user_id = :uid"), {"uid": user_id})
        await session.execute(text("DELETE FROM audit_logs WHERE user_id = :uid"), {"uid": user_id})
        await session.execute(text("DELETE FROM workspace_members WHERE user_id = :uid"), {"uid": user_id})
        await session.execute(text("DELETE FROM workspaces WHERE id = :wid"), {"wid": workspace_id})
        await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        await session.commit()


@pytest.mark.asyncio
async def test_full_password_recovery_lifecycle():
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    user = await create_api_test_user()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            mock_provider = AsyncMock()
            mock_provider.send_otp_email = AsyncMock(return_value=True)
            with patch("backend.services.auth.password_reset_service.get_email_provider", return_value=mock_provider):
                # Step 1: Request Recovery Code
                req_res = await client.post(
                    "/api/v1/auth/password-reset/request",
                    json={"email": user["email"]}
                )
                assert req_res.status_code == 200, req_res.text
                assert req_res.json()["success"] is True
                assert "verification code" in req_res.json()["data"]["message"].lower()

                assert mock_provider.send_otp_email.call_count == 1
                _, raw_otp = mock_provider.send_otp_email.call_args[0]
                assert len(raw_otp) == 6

                # Step 2: Verify Recovery Code -> Receive reset_token
                verify_res = await client.post(
                    "/api/v1/auth/password-reset/verify",
                    json={"email": user["email"], "otp": raw_otp}
                )
                assert verify_res.status_code == 200, verify_res.text
                verify_data = verify_res.json()["data"]
                reset_token = verify_data["reset_token"]
                assert reset_token is not None
                assert verify_data["expires_in_seconds"] == 900

                # Step 3: Complete Password Reset
                new_password = "NewSecurePassword789!"
                complete_res = await client.post(
                    "/api/v1/auth/password-reset/complete",
                    json={
                        "email": user["email"],
                        "reset_token": reset_token,
                        "new_password": new_password,
                    }
                )
                assert complete_res.status_code == 200, complete_res.text
                assert complete_res.json()["success"] is True

                # Step 4: Old password must fail at login
                old_login_res = await client.post(
                    "/api/v1/auth/login",
                    json={"email": user["email"], "password": user["password"]}
                )
                assert old_login_res.status_code == 401

                # Step 5: New password must succeed at login
                new_login_res = await client.post(
                    "/api/v1/auth/login",
                    json={"email": user["email"], "password": new_password}
                )
                assert new_login_res.status_code == 200, new_login_res.text
                assert "access_token" in new_login_res.json()["data"]
    finally:
        await cleanup_api_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_password_recovery_legacy_aliases():
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    user = await create_api_test_user()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            mock_provider = AsyncMock()
            mock_provider.send_otp_email = AsyncMock(return_value=True)
            with patch("backend.services.auth.password_reset_service.get_email_provider", return_value=mock_provider):
                # Alias 1: /password/otp/request
                req_res = await client.post(
                    "/api/v1/auth/password/otp/request",
                    json={"email": user["email"]}
                )
                assert req_res.status_code == 200, req_res.text
                _, raw_otp = mock_provider.send_otp_email.call_args[0]

                # Alias 2: /password/otp/verify
                verify_res = await client.post(
                    "/api/v1/auth/password/otp/verify",
                    json={"email": user["email"], "otp": raw_otp}
                )
                assert verify_res.status_code == 200, verify_res.text
                assert "reset_token" in verify_res.json()["data"]

                # Alias 3: /password/otp/reset
                new_password = "AliasPassword123!"
                reset_res = await client.post(
                    "/api/v1/auth/password/otp/reset",
                    json={
                        "email": user["email"],
                        "otp": raw_otp,
                        "new_password": new_password,
                    }
                )
                assert reset_res.status_code == 200, reset_res.text

                # Login with new password
                login_res = await client.post(
                    "/api/v1/auth/login",
                    json={"email": user["email"], "password": new_password}
                )
                assert login_res.status_code == 200, login_res.text
    finally:
        await cleanup_api_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_recovery_non_existent_account_timing_and_enumeration():
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        fake_email = f"nonexistent_{uuid.uuid4().hex[:8]}@example.com"
        res = await client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": fake_email}
        )
        assert res.status_code == 200, res.text
        assert res.json()["success"] is True
        assert "verification code" in res.json()["data"]["message"].lower()

        # Immediate repeat should trigger 429 cooldown even for non-existent account
        repeat_res = await client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": fake_email}
        )
        assert repeat_res.status_code == 429
