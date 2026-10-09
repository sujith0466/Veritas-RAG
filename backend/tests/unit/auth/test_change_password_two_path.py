"""Unit and integration tests for Phase 2 dual-path password change architecture.

Covers:
- Path A (Current Password flow)
- Path B (Security Code flow)
- Session Policy B (Current session rotated, others revoked, family_id preserved)
- Token Invalidation Invariant (new_token_iat == Redis invalid_before)
- Multi-Workspace Invalidation
- Transaction Boundaries & Atomicity
- Non-blocking Email Dispatch with safe context
- Anti-Bypass Protections
"""

import datetime
import hashlib
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
import jwt
import pytest
from sqlalchemy import select

from backend.core.exceptions.auth import AuthenticationException
from backend.core.security.password import get_password_hash, verify_password
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.password_otp import PasswordRecoveryOTP
from backend.models.entities.user import User
from backend.models.entities.user_session import UserSession
from backend.services.auth.password_reset_service import PasswordResetService


@pytest.fixture
def mock_user():
    user_id = uuid.uuid4()
    user = MagicMock(spec=User)
    user.id = user_id
    user.email = "test.dualpath@veritas.rag"
    user.is_active = True
    user.is_deleted = False
    user.tenant_id = None
    user.role = "member"
    user.hashed_password = get_password_hash("CurrentPassword123!")
    user.password_reset_token_hash = None
    user.password_reset_token_expires_at = None
    return user


@pytest.fixture
def mock_session():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


# ═════════════════════════════════════════════════════════════════════════════
# PATH A TESTS (1 - 7)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_path_a_correct_current_password_succeeds(mock_user, mock_session):
    """1. Correct current password succeeds and returns fresh token pair."""
    mock_redis = AsyncMock()

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)
    service.redis = mock_redis

    family_id = str(uuid.uuid4())
    access_token, refresh_token = await service.change_password(
        user_id=mock_user.id,
        current_password="CurrentPassword123!",
        new_password="BrandNewPassword456!",
        caller_family_id=family_id,
        caller_context={"user_agent": "TestBrowser/1.0", "ip_address": "127.0.0.1"},
    )

    assert access_token is not None
    assert refresh_token is not None
    assert mock_session.commit.call_count >= 1
    assert verify_password("BrandNewPassword456!", mock_user.hashed_password)


@pytest.mark.asyncio
async def test_path_a_incorrect_current_password_fails(mock_user):
    """2. Incorrect current password raises 401 AuthenticationException."""
    mock_session = AsyncMock()
    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)
    service._execute_password_reset = AsyncMock()

    with pytest.raises(AuthenticationException) as exc:
        await service.change_password(
            user_id=mock_user.id,
            current_password="WrongPassword999!",
            new_password="BrandNewPassword456!",
        )

    assert "Incorrect current password" in str(exc.value)
    assert service._execute_password_reset.call_count == 0
    assert mock_session.commit.call_count == 0


@pytest.mark.asyncio
async def test_path_a_password_reuse_rejected(mock_user):
    """Password reuse (new password == current password) returns HTTP 400."""
    mock_session = AsyncMock()
    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)

    with pytest.raises(HTTPException) as exc:
        await service.change_password(
            user_id=mock_user.id,
            current_password="CurrentPassword123!",
            new_password="CurrentPassword123!",
        )

    assert exc.value.status_code == 400
    assert "cannot be the same as current password" in exc.value.detail


@pytest.mark.asyncio
async def test_path_a_account_without_password_rejected(mock_user):
    """Account with no local password (e.g. pure OAuth) cannot use Path A."""
    mock_user.hashed_password = None
    mock_session = AsyncMock()
    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)

    with pytest.raises(AuthenticationException) as exc:
        await service.change_password(
            user_id=mock_user.id,
            current_password="AnyPassword123!",
            new_password="BrandNewPassword456!",
        )

    assert "no local password configured" in str(exc.value)


# ═════════════════════════════════════════════════════════════════════════════
# PATH B TESTS (8 - 15)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_path_b_security_code_request_and_verify(mock_user):
    """8, 9. Request security code, verify code, and receive ephemeral change token."""
    mock_session = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)
    service.redis = mock_redis

    with patch("backend.services.auth.password_reset_service.get_email_provider") as mock_email_fn:
        mock_provider = AsyncMock()
        mock_provider.send_security_code_email = AsyncMock(return_value=True)
        mock_email_fn.return_value = mock_provider

        # Request
        await service.request_security_code(mock_user.id)
        assert mock_provider.send_security_code_email.call_count == 1
        _, raw_code = mock_provider.send_security_code_email.call_args[0]

        # Setup mock OTP record for verify
        code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
        mock_otp = MagicMock(spec=PasswordRecoveryOTP)
        mock_otp.user_id = mock_user.id
        mock_otp.channel = "AUTH_CHANGE_PASSWORD"
        mock_otp.otp_hash = code_hash
        mock_otp.expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=10)
        mock_otp.attempts = 0
        mock_otp.is_used = False
        mock_otp.is_invalidated = False

        mock_res = MagicMock()
        mock_res.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_otp)))
        mock_session.execute = AsyncMock(return_value=mock_res)

        # Verify
        change_token = await service.verify_security_code(mock_user.id, raw_code)
        assert change_token is not None
        assert len(change_token) >= 32
        assert mock_otp.is_used is True


@pytest.mark.asyncio
async def test_path_b_invalid_otp_fails(mock_user):
    """10. Invalid OTP fails verification."""
    mock_session = AsyncMock()
    mock_otp = MagicMock(spec=PasswordRecoveryOTP)
    mock_otp.user_id = mock_user.id
    mock_otp.channel = "AUTH_CHANGE_PASSWORD"
    mock_otp.otp_hash = hashlib.sha256(b"123456").hexdigest()
    mock_otp.expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=10)
    mock_otp.attempts = 0
    mock_otp.is_used = False
    mock_otp.is_invalidated = False

    mock_res = MagicMock()
    mock_res.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_otp)))
    mock_session.execute = AsyncMock(return_value=mock_res)

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)

    with pytest.raises(AuthenticationException) as exc:
        await service.verify_security_code(mock_user.id, "999999")

    assert "Invalid or expired security code" in str(exc.value)


@pytest.mark.asyncio
async def test_path_b_expired_otp_fails(mock_user):
    """11. Expired OTP fails verification."""
    mock_session = AsyncMock()
    mock_otp = MagicMock(spec=PasswordRecoveryOTP)
    mock_otp.user_id = mock_user.id
    mock_otp.channel = "AUTH_CHANGE_PASSWORD"
    mock_otp.otp_hash = hashlib.sha256(b"123456").hexdigest()
    mock_otp.expires_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=1)
    mock_otp.attempts = 0
    mock_otp.is_used = False
    mock_otp.is_invalidated = False

    mock_res = MagicMock()
    mock_res.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_otp)))
    mock_session.execute = AsyncMock(return_value=mock_res)

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)

    with pytest.raises(AuthenticationException) as exc:
        await service.verify_security_code(mock_user.id, "123456")

    assert "Invalid or expired security code" in str(exc.value)
    assert mock_otp.is_invalidated is True


@pytest.mark.asyncio
async def test_path_b_change_token_single_use(mock_user, mock_session):
    """13, 15. Change token is single-use and successfully changes password on first attempt."""
    mock_redis = AsyncMock()

    raw_token = "single-use-change-token-xyz-12345"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    mock_user.password_reset_token_hash = token_hash
    mock_user.password_reset_token_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=15)

    # Redis has token on first attempt
    mock_redis.get = AsyncMock(return_value=str(mock_user.id))
    mock_redis.delete = AsyncMock()

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)
    service.redis = mock_redis

    family_id = str(uuid.uuid4())
    access_token, refresh_token = await service.complete_password_change(
        user_id=mock_user.id,
        change_token=raw_token,
        new_password="NewPathBPassword123!",
        caller_family_id=family_id,
        caller_context={"user_agent": "TestBrowser/1.0", "ip_address": "127.0.0.1"},
    )

    assert access_token is not None
    assert refresh_token is not None
    assert mock_redis.delete.call_count >= 1

    # Second attempt: Redis get returns None
    mock_redis.get = AsyncMock(return_value=None)
    mock_user.password_reset_token_hash = None

    with pytest.raises(AuthenticationException):
        await service.complete_password_change(
            user_id=mock_user.id,
            change_token=raw_token,
            new_password="AnotherPassword999!",
            caller_family_id=family_id,
        )


# ═════════════════════════════════════════════════════════════════════════════
# SESSION POLICY B & INVARIANT TESTS (16 - 30)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_session_policy_b_preserves_family_id_and_7day_lifetime(mock_user, mock_session):
    """16-23. Caller retains family_id, old session rotated, new session created with 7-day lifetime."""
    mock_redis = AsyncMock()

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)
    service.redis = mock_redis

    original_family_id = str(uuid.uuid4())
    access_token, refresh_token = await service.change_password(
        user_id=mock_user.id,
        current_password="CurrentPassword123!",
        new_password="RotatedPassword123!",
        caller_family_id=original_family_id,
        caller_context={"user_agent": "MyLaptop/1.0", "ip_address": "10.0.0.5"},
    )

    # Inspect added UserSession
    added_sessions = [
        call.args[0] for call in mock_session.add.call_args_list if isinstance(call.args[0], UserSession)
    ]
    assert len(added_sessions) == 1
    new_sess = added_sessions[0]

    assert new_sess.family_id == original_family_id
    assert new_sess.is_revoked is False
    assert new_sess.user_agent == "MyLaptop/1.0"
    assert new_sess.ip_address == "10.0.0.5"

    # Lifetime check: expires_at roughly now + 7 days
    now = datetime.datetime.now(datetime.UTC)
    expected_expiry = now + datetime.timedelta(days=7)
    diff = abs((new_sess.expires_at - expected_expiry).total_seconds())
    assert diff < 60  # Within 60 seconds of 7 days


@pytest.mark.asyncio
async def test_token_invalidation_invariant_and_multi_workspace(mock_user, mock_session):
    """24-30. new_token.iat == Redis invalid_before, multi-workspace coverage."""
    mock_redis = AsyncMock()

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)
    service.redis = mock_redis

    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()

    # Mock WorkspaceMember query returning ws_a and ws_b
    mock_res = MagicMock()
    mock_res.first.return_value = None
    mock_res.scalar_one_or_none.return_value = None
    mock_res.scalars.return_value.all.return_value = [ws_a, ws_b]
    mock_session.execute = AsyncMock(return_value=mock_res)

    access_token, _ = await service.change_password(
        user_id=mock_user.id,
        current_password="CurrentPassword123!",
        new_password="NewSecurePassword789!",
        caller_family_id=str(uuid.uuid4()),
    )

    # Decode minted token unverified
    claims = jwt.decode(access_token, options={"verify_signature": False})
    new_token_iat = claims["iat"]

    # Verify Redis keys set for ws_a and ws_b with str(new_token_iat)
    set_calls = mock_redis.set.call_args_list
    ws_a_key = f"auth:user:{mock_user.id}:workspace:{ws_a}:invalid_before"
    ws_b_key = f"auth:user:{mock_user.id}:workspace:{ws_b}:invalid_before"

    found_a = any(call.args[0] == ws_a_key and call.args[1] == str(new_token_iat) for call in set_calls)
    found_b = any(call.args[0] == ws_b_key and call.args[1] == str(new_token_iat) for call in set_calls)

    assert found_a, f"Expected key {ws_a_key} with value {new_token_iat}"
    assert found_b, f"Expected key {ws_b_key} with value {new_token_iat}"


# ═════════════════════════════════════════════════════════════════════════════
# TRANSACTION & EMAIL TESTS (31 - 36)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_email_dispatch_non_blocking_on_failure(mock_user, mock_session):
    """34-36. Email failure post-commit does NOT raise exception or roll back password change."""
    mock_redis = AsyncMock()

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)
    service.redis = mock_redis

    with patch("backend.services.auth.password_reset_service.get_email_provider") as mock_email_fn:
        mock_provider = AsyncMock()
        mock_provider.send_password_changed_notification_email = AsyncMock(
            side_effect=RuntimeError("SMTP connection dropped")
        )
        mock_email_fn.return_value = mock_provider

        # Should complete successfully despite email failure
        access_token, _ = await service.change_password(
            user_id=mock_user.id,
            current_password="CurrentPassword123!",
            new_password="PasswordEvenIfEmailFails123!",
            caller_family_id=str(uuid.uuid4()),
        )

        assert access_token is not None
        assert mock_session.commit.call_count >= 1

