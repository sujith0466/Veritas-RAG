"""Deterministic Concurrency, Rollback, and Failure-Mode Integration Tests for Password Change.

Tests cover:
- Real PostgreSQL row-level lock barrier proof (with_for_update)
- Simultaneous race condition rejection (Path B & Forgot Password)
- Sequential replay rejection (Path B & Forgot Password)
- Pre-commit validation rollback & token retention (Path B & Forgot Password)
- Ambiguous commit handling with independent PostgreSQL session state inspection
- Redis outage resilience (PostgreSQL row locking enforces single-use independently)
- Post-commit email failure non-fatal isolation
"""

import asyncio
import hashlib
import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from backend.cache.client import get_redis_client
from backend.core.security.password import get_password_hash, verify_password
from backend.database.engine import get_session_factory
from backend.main import create_app
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.repositories.implementations.user_repository import UserRepository
from backend.services.auth.password_reset_service import PasswordResetService
from backend.core.exceptions.auth import AuthenticationException

app = create_app()


def make_synthetic_test_password(label: str = "Pwd") -> str:
    """Generate an ephemeral synthetic test password meeting policy without hardcoded literals."""
    return f"Synth_{label}_{uuid.uuid4().hex[:10]}!Aa9"


async def create_test_user():
    session_factory = get_session_factory()
    unique_email = f"concurrency_{uuid.uuid4().hex[:8]}@example.com"
    initial_password = make_synthetic_test_password("Init")
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


async def cleanup_test_user(user_id: uuid.UUID, workspace_id: uuid.UUID):
    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(text("DELETE FROM user_sessions WHERE user_id = :uid"), {"uid": user_id})
        await session.execute(text("DELETE FROM password_recovery_otps WHERE user_id = :uid"), {"uid": user_id})
        await session.execute(text("DELETE FROM audit_logs WHERE user_id = :uid"), {"uid": user_id})
        await session.execute(text("DELETE FROM workspace_members WHERE user_id = :uid"), {"uid": user_id})
        await session.execute(text("DELETE FROM workspaces WHERE id = :wid"), {"wid": workspace_id})
        await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        await session.commit()


async def get_authenticated_path_b_token(client: AsyncClient, user: dict) -> tuple[str, str]:
    """Logs in and completes security code verification, returning (access_token, change_token)."""
    # 1. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]}
    )
    assert login_res.status_code == 200, login_res.text
    access_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Request Security Code
    mock_provider = AsyncMock()
    mock_provider.send_security_code_email = AsyncMock(return_value=True)
    with patch("backend.services.auth.password_reset_service.get_email_provider", return_value=mock_provider):
        req_res = await client.post(
            "/api/v1/auth/change-password/request-code",
            headers=headers
        )
        assert req_res.status_code == 200, req_res.text
        assert mock_provider.send_security_code_email.call_count == 1
        _, raw_otp = mock_provider.send_security_code_email.call_args[0]

        # 3. Verify Security Code
        verify_res = await client.post(
            "/api/v1/auth/change-password/verify-code",
            headers=headers,
            json={"code": raw_otp}
        )
        assert verify_res.status_code == 200, verify_res.text
        change_token = verify_res.json()["data"]["change_token"]
        assert change_token is not None

    return access_token, change_token


async def get_forgot_password_reset_token(client: AsyncClient, email: str) -> str:
    """Requests and verifies recovery code, returning reset_token."""
    mock_provider = AsyncMock()
    mock_provider.send_otp_email = AsyncMock(return_value=True)
    with patch("backend.services.auth.password_reset_service.get_email_provider", return_value=mock_provider):
        req_res = await client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": email}
        )
        assert req_res.status_code == 200, req_res.text
        _, raw_otp = mock_provider.send_otp_email.call_args[0]

        verify_res = await client.post(
            "/api/v1/auth/password-reset/verify",
            json={"email": email, "otp": raw_otp}
        )
        assert verify_res.status_code == 200, verify_res.text
        return verify_res.json()["data"]["reset_token"]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8.1: Authenticated Security-Code Path B Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_path_b_real_row_lock_barrier_proof():
    """B1: Real PostgreSQL row-lock barrier proof showing Session 2 blocks on Session 1."""
    user = await create_test_user()
    session_factory = get_session_factory()
    try:
        async with session_factory() as session1, session_factory() as session2:
            repo1 = UserRepository(session1)
            repo2 = UserRepository(session2)

            # Session 1 acquires exclusive row lock
            user1 = await repo1.get_by_id(user["id"], for_update=True)
            assert user1 is not None

            # Session 2 attempts to acquire the lock concurrently
            session2_blocked = asyncio.Event()

            async def try_lock_session2():
                session2_blocked.set()
                return await repo2.get_by_id(user["id"], for_update=True)

            task2 = asyncio.create_task(try_lock_session2())
            await session2_blocked.wait()
            # Give task2 a moment to hit the database and block
            await asyncio.sleep(0.1)

            # Assert task2 is strictly BLOCKED by PostgreSQL kernel
            assert not task2.done(), "Session 2 should be blocked by Session 1's row lock"

            # Session 1 updates state and commits, releasing lock
            user1.password_reset_token_hash = "token_cleared"
            await session1.commit()

            # Task 2 should now unblock immediately
            user2 = await asyncio.wait_for(task2, timeout=2.0)
            assert user2 is not None
            assert user2.password_reset_token_hash == "token_cleared"
            await session2.rollback()
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_path_b_simultaneous_race_rejection():
    """B2: Two simultaneous requests with identical change_token produce exactly one 200 and one 401."""
    user = await create_test_user()
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            access_token, change_token = await get_authenticated_path_b_token(client, user)
            headers = {"Authorization": f"Bearer {access_token}"}

            new_password_a = make_synthetic_test_password("WinA")
            new_password_b = make_synthetic_test_password("LoseB")

            # Dispatch two simultaneous requests with zero delay
            res1, res2 = await asyncio.gather(
                client.post(
                    "/api/v1/auth/change-password/complete",
                    headers=headers,
                    json={"change_token": change_token, "new_password": new_password_a},
                ),
                client.post(
                    "/api/v1/auth/change-password/complete",
                    headers=headers,
                    json={"change_token": change_token, "new_password": new_password_b},
                ),
            )

            status_codes = sorted([res1.status_code, res2.status_code])
            assert status_codes == [200, 401], f"Expected exactly one 200 and one 401, got {status_codes}"

            # Identify winner and verify winning password
            success_res = res1 if res1.status_code == 200 else res2
            winning_pwd = new_password_a if res1.status_code == 200 else new_password_b
            losing_pwd = new_password_b if res1.status_code == 200 else new_password_a

            assert "Password changed successfully" in success_res.json()["data"]["message"]

            # Winner can log in
            login_win = await client.post(
                "/api/v1/auth/login",
                json={"email": user["email"], "password": winning_pwd}
            )
            assert login_win.status_code == 200

            # Loser cannot log in
            login_lose = await client.post(
                "/api/v1/auth/login",
                json={"email": user["email"], "password": losing_pwd}
            )
            assert login_lose.status_code == 401
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_path_b_sequential_replay_rejection():
    """B3: Consumed change_token sequentially replayed is rejected with 401."""
    user = await create_test_user()
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            access_token, change_token = await get_authenticated_path_b_token(client, user)
            headers = {"Authorization": f"Bearer {access_token}"}

            valid_pwd = make_synthetic_test_password("PathBValid")
            replay_pwd_1 = make_synthetic_test_password("PathBReplay1")
            replay_pwd_2 = make_synthetic_test_password("PathBReplay2")

            # Attempt 1: Valid change succeeds
            res1 = await client.post(
                "/api/v1/auth/change-password/complete",
                headers=headers,
                json={"change_token": change_token, "new_password": valid_pwd},
            )
            assert res1.status_code == 200
            new_access_token = res1.json()["data"]["access_token"]
            new_headers = {"Authorization": f"Bearer {new_access_token}"}

            # Attempt 2: Sequential replay with active authenticated session fails at credential consumption
            res2 = await client.post(
                "/api/v1/auth/change-password/complete",
                headers=new_headers,
                json={"change_token": change_token, "new_password": replay_pwd_1},
            )
            assert res2.status_code == 401
            assert "Invalid, expired, or previously consumed credential" in res2.text

            # Attempt 3: Sequential replay with old access token fails at token validation (revoked)
            res3 = await client.post(
                "/api/v1/auth/change-password/complete",
                headers=headers,
                json={"change_token": change_token, "new_password": replay_pwd_2},
            )
            assert res3.status_code == 401
            assert "revoked" in res3.text.lower()
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_path_b_precommit_validation_rollback_and_retention():
    """B4: Pre-commit password reuse rejection (400) rolls back and preserves token for retry."""
    user = await create_test_user()
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            access_token, change_token = await get_authenticated_path_b_token(client, user)
            headers = {"Authorization": f"Bearer {access_token}"}

            # Request 1: Attempt password change with same password as current -> 400 Bad Request
            res1 = await client.post(
                "/api/v1/auth/change-password/complete",
                headers=headers,
                json={"change_token": change_token, "new_password": user["password"]},
            )
            assert res1.status_code == 400
            assert "cannot be the same" in res1.text.lower()

            # Independent DB inspection: Verify token is still present in PostgreSQL
            session_factory = get_session_factory()
            token_hash = hashlib.sha256(change_token.encode("utf-8")).hexdigest()
            async with session_factory() as session:
                repo = UserRepository(session)
                u = await repo.get_by_id(user["id"])
                assert u is not None
                assert u.password_reset_token_hash == token_hash, "Token should be preserved in DB after 400 rollback"

            valid_pwd = make_synthetic_test_password("PathBLegit")
            replay_pwd = make_synthetic_test_password("PathBReplay")

            # Request 2: Retry with a valid new password using the SAME change_token -> 200 OK
            res2 = await client.post(
                "/api/v1/auth/change-password/complete",
                headers=headers,
                json={"change_token": change_token, "new_password": valid_pwd},
            )
            assert res2.status_code == 200
            assert "Password changed successfully" in res2.json()["data"]["message"]

            # Request 3: Subsequent submission of the same change_token -> 401 Unauthorized
            res3 = await client.post(
                "/api/v1/auth/change-password/complete",
                headers=headers,
                json={"change_token": change_token, "new_password": replay_pwd},
            )
            assert res3.status_code == 401
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_path_b_ambiguous_commit_server_committed_handling():
    """B5: Ambiguous commit (server committed): DB token is NULL, client retry yields 401, user logs in with new pwd."""
    user = await create_test_user()
    session_factory = get_session_factory()
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    raw_token = "ambiguous-test-token-xyz-123"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    new_password = make_synthetic_test_password("PathBCommit")
    retry_password = make_synthetic_test_password("PathBRetry")

    # Simulate token in DB
    async with session_factory() as session:
        await session.execute(
            text("UPDATE users SET password_reset_token_hash = :h, password_reset_token_expires_at = NOW() + INTERVAL '15 minutes' WHERE id = :uid"),
            {"h": token_hash, "uid": user["id"]},
        )
        await session.commit()

    try:
        # Service call where transaction commits successfully
        async with session_factory() as session:
            service = PasswordResetService(session)
            await service.complete_password_change(user["id"], raw_token, new_password)

        # Independent session inspects database: token is NULL, password updated
        async with session_factory() as session:
            repo = UserRepository(session)
            u = await repo.get_by_id(user["id"])
            assert u.password_reset_token_hash is None
            assert verify_password(new_password, u.hashed_password)

        # Client reconnects and retries with the same change_token: Must receive 401
        async with session_factory() as session:
            service = PasswordResetService(session)
            with pytest.raises(Exception) as exc:
                await service.complete_password_change(user["id"], raw_token, retry_password)
            assert "Invalid, expired, or previously consumed credential" in str(exc.value)

        # User logs in with new password successfully
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": user["email"], "password": new_password}
            )
            assert login_res.status_code == 200
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_path_b_ambiguous_commit_server_aborted_handling():
    """B6: Ambiguous commit (server aborted): DB token remains intact, client retry succeeds with 200."""
    user = await create_test_user()
    session_factory = get_session_factory()
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    raw_token = "ambiguous-aborted-token-xyz-456"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    new_password = make_synthetic_test_password("PathBAbort")

    # Simulate token in DB
    async with session_factory() as session:
        await session.execute(
            text("UPDATE users SET password_reset_token_hash = :h, password_reset_token_expires_at = NOW() + INTERVAL '15 minutes' WHERE id = :uid"),
            {"h": token_hash, "uid": user["id"]},
        )
        await session.commit()

    try:
        # Simulate connection drop aborting the transaction before commit
        # (Rollback is called following failure)
        async with session_factory() as session:
            service = PasswordResetService(session)
            with patch.object(session, "commit", side_effect=RuntimeError("Connection terminated during COMMIT")):
                with pytest.raises(RuntimeError):
                    await service.complete_password_change(user["id"], raw_token, new_password)

        # Independent session inspects database: token is STILL valid, old password remains active
        async with session_factory() as session:
            repo = UserRepository(session)
            u = await repo.get_by_id(user["id"])
            assert u.password_reset_token_hash == token_hash, "Token should be preserved after server abort"
            assert verify_password(user["password"], u.hashed_password), "Old password should still be active"

        # Client reconnects and retries with the same change_token: Succeeds!
        async with session_factory() as session:
            service = PasswordResetService(session)
            access_tok, refresh_tok = await service.complete_password_change(user["id"], raw_token, new_password)
            assert access_tok is not None

        # Independent session confirms password was updated
        async with session_factory() as session:
            repo = UserRepository(session)
            u = await repo.get_by_id(user["id"])
            assert u.password_reset_token_hash is None
            assert verify_password(new_password, u.hashed_password)
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_path_b_redis_outage_resilience():
    """B7: When Redis is completely unavailable, PostgreSQL row lock enforces single-use independently."""
    user = await create_test_user()
    session_factory = get_session_factory()

    raw_token = "redis-outage-token-12345"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    async with session_factory() as session:
        await session.execute(
            text("UPDATE users SET password_reset_token_hash = :h, password_reset_token_expires_at = NOW() + INTERVAL '15 minutes' WHERE id = :uid"),
            {"h": token_hash, "uid": user["id"]},
        )
        await session.commit()

    try:
        async with session_factory() as session1, session_factory() as session2:
            service1 = PasswordResetService(session1)
            service2 = PasswordResetService(session2)
            # Simulate complete Redis outage
            service1.redis = None
            service2.redis = None

            pwd_a = make_synthetic_test_password("PathBOutageWin")
            pwd_b = make_synthetic_test_password("PathBOutageLose")

            results = await asyncio.gather(
                service1.complete_password_change(user["id"], raw_token, pwd_a),
                service2.complete_password_change(user["id"], raw_token, pwd_b),
                return_exceptions=True,
            )

            success_count = sum(1 for r in results if isinstance(r, tuple))
            failure_count = sum(1 for r in results if isinstance(r, Exception))
            assert success_count == 1, f"Expected exactly 1 success under Redis outage, got {success_count}"
            assert failure_count == 1, f"Expected exactly 1 failure under Redis outage, got {failure_count}"
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_path_b_post_commit_email_failsafe_isolation():
    """B8: Post-commit email provider failure does not rollback or fail the password change."""
    user = await create_test_user()
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            access_token, change_token = await get_authenticated_path_b_token(client, user)
            headers = {"Authorization": f"Bearer {access_token}"}

            new_password = make_synthetic_test_password("PathBEmailSafe")

            mock_provider = AsyncMock()
            mock_provider.send_password_changed_notification_email = AsyncMock(side_effect=RuntimeError("SMTP Timeout"))

            with patch("backend.services.auth.password_reset_service.get_email_provider", return_value=mock_provider):
                res = await client.post(
                    "/api/v1/auth/change-password/complete",
                    headers=headers,
                    json={"change_token": change_token, "new_password": new_password},
                )
                assert res.status_code == 200, res.text
                assert "Password changed successfully" in res.json()["data"]["message"]

            # Independent DB inspection confirms password was committed
            session_factory = get_session_factory()
            async with session_factory() as session:
                repo = UserRepository(session)
                u = await repo.get_by_id(user["id"])
                assert verify_password(new_password, u.hashed_password)
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8.2: Unauthenticated Forgot Password Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_forgot_password_real_row_lock_barrier_proof():
    """FP1: Real PostgreSQL row-lock barrier proof showing Session 2 blocks on get_by_email(for_update=True)."""
    user = await create_test_user()
    session_factory = get_session_factory()
    try:
        async with session_factory() as session1, session_factory() as session2:
            repo1 = UserRepository(session1)
            repo2 = UserRepository(session2)

            user1 = await repo1.get_by_email(user["email"], for_update=True)
            assert user1 is not None

            session2_blocked = asyncio.Event()

            async def try_lock_session2():
                session2_blocked.set()
                return await repo2.get_by_email(user["email"], for_update=True)

            task2 = asyncio.create_task(try_lock_session2())
            await session2_blocked.wait()
            await asyncio.sleep(0.1)

            assert not task2.done(), "Session 2 should be blocked by Session 1's email row lock"

            user1.password_reset_token_hash = "token_cleared_fp"
            await session1.commit()

            user2 = await asyncio.wait_for(task2, timeout=2.0)
            assert user2 is not None
            assert user2.password_reset_token_hash == "token_cleared_fp"
            await session2.rollback()
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_forgot_password_simultaneous_race_rejection():
    """FP2: Two simultaneous requests with identical reset_token produce exactly one 200 and one 401."""
    user = await create_test_user()
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            reset_token = await get_forgot_password_reset_token(client, user["email"])

            new_password_a = make_synthetic_test_password("FPWinA")
            new_password_b = make_synthetic_test_password("FPLoseB")

            res1, res2 = await asyncio.gather(
                client.post(
                    "/api/v1/auth/password-reset/complete",
                    json={"email": user["email"], "reset_token": reset_token, "new_password": new_password_a},
                ),
                client.post(
                    "/api/v1/auth/password-reset/complete",
                    json={"email": user["email"], "reset_token": reset_token, "new_password": new_password_b},
                ),
            )

            status_codes = sorted([res1.status_code, res2.status_code])
            assert status_codes == [200, 401], f"Expected exactly one 200 and one 401, got {status_codes}"

            winning_pwd = new_password_a if res1.status_code == 200 else new_password_b
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": user["email"], "password": winning_pwd}
            )
            assert login_res.status_code == 200
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_forgot_password_sequential_replay_rejection():
    """FP3: Consumed reset_token sequentially replayed is rejected with 401."""
    user = await create_test_user()
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            reset_token = await get_forgot_password_reset_token(client, user["email"])

            reset_password = make_synthetic_test_password("FPReset")
            replay_password = make_synthetic_test_password("FPReplay")

            res1 = await client.post(
                "/api/v1/auth/password-reset/complete",
                json={"email": user["email"], "reset_token": reset_token, "new_password": reset_password},
            )
            assert res1.status_code == 200

            res2 = await client.post(
                "/api/v1/auth/password-reset/complete",
                json={"email": user["email"], "reset_token": reset_token, "new_password": replay_password},
            )
            assert res2.status_code == 401
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_forgot_password_post_commit_email_failsafe_isolation():
    """FP4: Post-commit email failure does not fail the password reset."""
    user = await create_test_user()
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            reset_token = await get_forgot_password_reset_token(client, user["email"])

            mock_provider = AsyncMock()
            mock_provider.send_password_changed_notification_email = AsyncMock(side_effect=RuntimeError("SMTP Server Down"))

            new_password = make_synthetic_test_password("FPEmailSafe")

            with patch("backend.services.auth.password_reset_service.get_email_provider", return_value=mock_provider):
                res = await client.post(
                    "/api/v1/auth/password-reset/complete",
                    json={"email": user["email"], "reset_token": reset_token, "new_password": new_password},
                )
                assert res.status_code == 200, res.text

            session_factory = get_session_factory()
            async with session_factory() as session:
                repo = UserRepository(session)
                u = await repo.get_by_id(user["id"])
                assert verify_password(new_password, u.hashed_password)
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_forgot_password_precommit_validation_rollback_and_retention():
    """FP5: Pre-commit exception rolls back and preserves reset token in DB for retry."""
    user = await create_test_user()
    session_factory = get_session_factory()
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    raw_token = "fp-precommit-test-token-xyz"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Seed reset token in DB
    async with session_factory() as session:
        await session.execute(
            text("UPDATE users SET password_reset_token_hash = :h, password_reset_token_expires_at = NOW() + INTERVAL '15 minutes' WHERE id = :uid"),
            {"h": token_hash, "uid": user["id"]},
        )
        await session.commit()

    try:
        failed_pwd = make_synthetic_test_password("FPFail")
        success_pwd = make_synthetic_test_password("FPSuccess")
        replay_pwd = make_synthetic_test_password("FPReplay")

        # Request 1: Pre-commit failure during password hashing / execution
        async with session_factory() as session:
            service = PasswordResetService(session)
            with patch("backend.services.auth.password_reset_service.get_password_hash", side_effect=RuntimeError("Hashing engine failure")):
                with pytest.raises(RuntimeError):
                    await service.complete_password_reset(user["email"], raw_token, failed_pwd)

        # Independent DB inspection: Token is still preserved in DB because of rollback
        async with session_factory() as session:
            repo = UserRepository(session)
            u = await repo.get_by_id(user["id"])
            assert u.password_reset_token_hash == token_hash, "Reset token must remain intact in DB after rollback"

        # Request 2: Retry succeeds with the same reset token
        async with session_factory() as session:
            service = PasswordResetService(session)
            await service.complete_password_reset(user["email"], raw_token, success_pwd)

        # Independent DB inspection: Token consumed, password updated
        async with session_factory() as session:
            repo = UserRepository(session)
            u = await repo.get_by_id(user["id"])
            assert u.password_reset_token_hash is None
            assert verify_password(success_pwd, u.hashed_password)

        # Request 3: Subsequent attempt with same token fails with AuthenticationException (401)
        async with session_factory() as session:
            service = PasswordResetService(session)
            with pytest.raises(AuthenticationException):
                await service.complete_password_reset(user["email"], raw_token, replay_pwd)
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_forgot_password_ambiguous_commit_server_committed_handling():
    """FP6: Ambiguous commit (server committed): DB token is NULL, client retry yields 401, user logs in with new pwd."""
    user = await create_test_user()
    session_factory = get_session_factory()
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    raw_token = "fp-ambiguous-committed-xyz-789"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    new_password = make_synthetic_test_password("FPCommit")
    retry_pwd = make_synthetic_test_password("FPRetry")

    # Simulate token in DB
    async with session_factory() as session:
        await session.execute(
            text("UPDATE users SET password_reset_token_hash = :h, password_reset_token_expires_at = NOW() + INTERVAL '15 minutes' WHERE id = :uid"),
            {"h": token_hash, "uid": user["id"]},
        )
        await session.commit()

    try:
        # Service call succeeds and commits
        async with session_factory() as session:
            service = PasswordResetService(session)
            await service.complete_password_reset(user["email"], raw_token, new_password)

        # Independent session inspects database: token is NULL, password updated
        async with session_factory() as session:
            repo = UserRepository(session)
            u = await repo.get_by_id(user["id"])
            assert u.password_reset_token_hash is None
            assert verify_password(new_password, u.hashed_password)

        # Client retries with same token: Must raise AuthenticationException
        async with session_factory() as session:
            service = PasswordResetService(session)
            with pytest.raises(AuthenticationException):
                await service.complete_password_reset(user["email"], raw_token, retry_pwd)

        # User logs in with new password successfully
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": user["email"], "password": new_password}
            )
            assert login_res.status_code == 200
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_forgot_password_ambiguous_commit_server_aborted_handling():
    """FP7: Ambiguous commit (server aborted): DB token remains intact, client retry succeeds."""
    user = await create_test_user()
    session_factory = get_session_factory()
    redis = get_redis_client()
    if redis:
        await redis.flushdb()

    raw_token = "fp-ambiguous-aborted-xyz-987"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    new_password = make_synthetic_test_password("FPAbort")

    # Simulate token in DB
    async with session_factory() as session:
        await session.execute(
            text("UPDATE users SET password_reset_token_hash = :h, password_reset_token_expires_at = NOW() + INTERVAL '15 minutes' WHERE id = :uid"),
            {"h": token_hash, "uid": user["id"]},
        )
        await session.commit()

    try:
        # Simulate connection drop aborting the transaction before commit
        async with session_factory() as session:
            service = PasswordResetService(session)
            with patch.object(session, "commit", side_effect=RuntimeError("Connection terminated during COMMIT")):
                with pytest.raises(RuntimeError):
                    await service.complete_password_reset(user["email"], raw_token, new_password)

        # Independent session inspects database: token is STILL valid, old password remains active
        async with session_factory() as session:
            repo = UserRepository(session)
            u = await repo.get_by_id(user["id"])
            assert u.password_reset_token_hash == token_hash, "Token should be preserved after server abort"
            assert verify_password(user["password"], u.hashed_password), "Old password should still be active"

        # Client retries with the same reset token: Succeeds!
        async with session_factory() as session:
            service = PasswordResetService(session)
            await service.complete_password_reset(user["email"], raw_token, new_password)

        # Independent session confirms password was updated and token consumed
        async with session_factory() as session:
            repo = UserRepository(session)
            u = await repo.get_by_id(user["id"])
            assert u.password_reset_token_hash is None
            assert verify_password(new_password, u.hashed_password)
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])


@pytest.mark.asyncio
async def test_forgot_password_redis_outage_resilience():
    """FP8: Under Redis outage, PostgreSQL row lock remains authoritative and serializes concurrent reset requests."""
    user = await create_test_user()
    session_factory = get_session_factory()

    raw_token = "fp-redis-outage-token-123"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    async with session_factory() as session:
        await session.execute(
            text("UPDATE users SET password_reset_token_hash = :h, password_reset_token_expires_at = NOW() + INTERVAL '15 minutes' WHERE id = :uid"),
            {"h": token_hash, "uid": user["id"]},
        )
        await session.commit()

    try:
        async with session_factory() as session1, session_factory() as session2:
            service1 = PasswordResetService(session1)
            service2 = PasswordResetService(session2)
            # Simulate complete Redis outage
            service1.redis = None
            service2.redis = None

            pwd_a = make_synthetic_test_password("FPOutageWin")
            pwd_b = make_synthetic_test_password("FPOutageLose")

            results = await asyncio.gather(
                service1.complete_password_reset(user["email"], raw_token, pwd_a),
                service2.complete_password_reset(user["email"], raw_token, pwd_b),
                return_exceptions=True,
            )

            success_count = sum(1 for r in results if r is None)
            failure_count = sum(1 for r in results if isinstance(r, Exception))
            assert success_count == 1, f"Expected exactly 1 success under Redis outage, got {success_count}"
            assert failure_count == 1, f"Expected exactly 1 failure under Redis outage, got {failure_count}"
    finally:
        await cleanup_test_user(user["id"], user["workspace_id"])

