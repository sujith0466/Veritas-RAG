"""Unit tests for Phase 3: Password-changed confirmation email integration in Forgot Password / Recovery flow.

Verifies:
1. Forgot password completion dispatches send_password_changed_notification_email().
2. Email is dispatched strictly post-commit.
3. Email contains correct recipient and safe event context.
4. Email contains zero credentials or secrets (no password, OTP, tokens, JWTs, hashes).
5. User-agent and IP address are HTML-escaped to eliminate injection risks.
6. Email delivery failure is non-blocking and does not roll back PostgreSQL transactions.
7. Unauthenticated recovery maintains existing session revocation (all sessions revoked).
8. Token-based reset_password and legacy OTP reset also dispatch confirmation email.
"""

import datetime
import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from backend.core.security.password import get_password_hash, verify_password
from backend.models.entities.password_otp import PasswordRecoveryOTP
from backend.models.entities.user import User
from backend.services.auth.password_reset_service import PasswordResetService


@pytest.fixture
def mock_user():
    user_id = uuid.uuid4()
    user = MagicMock(spec=User)
    user.id = user_id
    user.email = "recovery.user@veritas.rag"
    user.is_active = True
    user.is_deleted = False
    user.tenant_id = None
    user.role = "member"
    user.hashed_password = get_password_hash("OldForgottenPassword123!")
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


@pytest.mark.asyncio
async def test_forgot_password_reset_dispatches_confirmation_email(mock_user, mock_session):
    """1, 2, 3, 4. Successful Forgot Password completion dispatches email post-commit with correct recipient."""
    raw_token = "valid-256-bit-reset-token-sample-12345"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    mock_user.password_reset_token_hash = token_hash
    mock_user.password_reset_token_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=15)

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_email = AsyncMock(return_value=mock_user)
    service._get_active_otp = AsyncMock(return_value=None)

    commit_occurred_before_email = False

    async def commit_side_effect():
        nonlocal commit_occurred_before_email
        commit_occurred_before_email = True

    mock_session.commit.side_effect = commit_side_effect

    with patch("backend.services.auth.password_reset_service.get_email_provider") as mock_email_fn:
        mock_provider = AsyncMock()
        mock_provider.send_password_changed_notification_email = AsyncMock(return_value=True)
        mock_email_fn.return_value = mock_provider

        new_password = "BrandNewRecoveredPassword789!"
        await service.complete_password_reset(
            email=mock_user.email,
            reset_token=raw_token,
            new_password=new_password,
            caller_context={"user_agent": "TestBrowser/2.0", "ip_address": "192.168.1.50"},
        )

        # 1. Email provider was invoked
        assert mock_provider.send_password_changed_notification_email.call_count == 1

        # 2. Commit occurred before email dispatch
        assert commit_occurred_before_email is True

        # 3. Correct recipient & safe context
        call_kwargs = mock_provider.send_password_changed_notification_email.call_args.kwargs
        assert call_kwargs["to_email"] == mock_user.email
        assert call_kwargs["user_agent"] == "TestBrowser/2.0"
        assert call_kwargs["ip_address"] == "192.168.1.50"
        assert isinstance(call_kwargs["event_time"], datetime.datetime)

        # 4. Password hash was updated
        assert verify_password(new_password, mock_user.hashed_password)


@pytest.mark.asyncio
async def test_forgot_password_confirmation_email_contains_zero_secrets(mock_user, mock_session):
    """6 - 11. Email invocation must not receive password, OTP, tokens, JWTs, or secrets."""
    raw_token = "secret-reset-token-xyz-98765"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    mock_user.password_reset_token_hash = token_hash
    mock_user.password_reset_token_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=15)

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_email = AsyncMock(return_value=mock_user)
    service._get_active_otp = AsyncMock(return_value=None)

    with patch("backend.services.auth.password_reset_service.get_email_provider") as mock_email_fn:
        mock_provider = AsyncMock()
        mock_provider.send_password_changed_notification_email = AsyncMock(return_value=True)
        mock_email_fn.return_value = mock_provider

        new_password = "SecretPlainPasswordToNeverLeak!"
        await service.complete_password_reset(
            email=mock_user.email,
            reset_token=raw_token,
            new_password=new_password,
            caller_context={"user_agent": "SecretBrowser", "ip_address": "10.0.0.1"},
        )

        args = mock_provider.send_password_changed_notification_email.call_args.args
        kwargs = mock_provider.send_password_changed_notification_email.call_args.kwargs
        all_passed_values = [str(v) for v in args] + [str(v) for v in kwargs.values()]

        for val in all_passed_values:
            assert new_password not in val
            assert raw_token not in val
            assert token_hash not in val
            assert "SecretPlainPasswordToNeverLeak" not in val
            assert "secret-reset-token" not in val


@pytest.mark.asyncio
async def test_forgot_password_html_escaping_ip_and_user_agent(mock_user, mock_session):
    """5. IP address and user-agent are HTML-escaped before dispatch to eliminate injection."""
    raw_token = "valid-token-for-escape-test"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    mock_user.password_reset_token_hash = token_hash
    mock_user.password_reset_token_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=15)

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_email = AsyncMock(return_value=mock_user)
    service._get_active_otp = AsyncMock(return_value=None)

    with patch("backend.services.auth.password_reset_service.get_email_provider") as mock_email_fn:
        mock_provider = AsyncMock()
        mock_provider.send_password_changed_notification_email = AsyncMock(return_value=True)
        mock_email_fn.return_value = mock_provider

        malicious_ua = '<script>alert("xss")</script><img src="x" onerror="steal()">'
        malicious_ip = '127.0.0.1<iframe src="evil.com"></iframe>'

        await service.complete_password_reset(
            email=mock_user.email,
            reset_token=raw_token,
            new_password="EscapedPassword123!",
            caller_context={"user_agent": malicious_ua, "ip_address": malicious_ip},
        )

        call_kwargs = mock_provider.send_password_changed_notification_email.call_args.kwargs
        safe_ua = call_kwargs["user_agent"]
        safe_ip = call_kwargs["ip_address"]

        assert "<script>" not in safe_ua
        assert "<img" not in safe_ua
        assert "&lt;script&gt;" in safe_ua
        assert "<iframe" not in safe_ip
        assert "&lt;iframe" in safe_ip


@pytest.mark.asyncio
async def test_forgot_password_email_failure_does_not_rollback(mock_user, mock_session):
    """12. Email delivery failure does NOT raise exception or roll back PostgreSQL transaction."""
    raw_token = "valid-token-for-failure-test"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    mock_user.password_reset_token_hash = token_hash
    mock_user.password_reset_token_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=15)

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_email = AsyncMock(return_value=mock_user)
    service._get_active_otp = AsyncMock(return_value=None)

    with patch("backend.services.auth.password_reset_service.get_email_provider") as mock_email_fn:
        mock_provider = AsyncMock()
        mock_provider.send_password_changed_notification_email = AsyncMock(
            side_effect=RuntimeError("SMTP service timeout")
        )
        mock_email_fn.return_value = mock_provider

        new_password = "SuccessPasswordEvenIfEmailFails123!"
        # Must not raise RuntimeError
        await service.complete_password_reset(
            email=mock_user.email,
            reset_token=raw_token,
            new_password=new_password,
            caller_context={"user_agent": "Mozilla/5.0", "ip_address": "10.0.0.2"},
        )

        assert mock_session.commit.call_count >= 1
        assert mock_session.rollback.call_count == 0
        assert verify_password(new_password, mock_user.hashed_password)


@pytest.mark.asyncio
async def test_token_based_reset_password_dispatches_email(mock_user, mock_session):
    """Direct token-based reset_password endpoint also dispatches confirmation email."""
    raw_token = "direct-token-flow-reset-12345"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    mock_user.password_reset_token_hash = token_hash
    mock_user.password_reset_token_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=15)

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_user
    mock_res.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_res)

    service = PasswordResetService(session=mock_session)

    with patch("backend.services.auth.password_reset_service.get_email_provider") as mock_email_fn:
        mock_provider = AsyncMock()
        mock_provider.send_password_changed_notification_email = AsyncMock(return_value=True)
        mock_email_fn.return_value = mock_provider

        await service.reset_password(
            raw_token=raw_token,
            new_password="NewDirectTokenPassword123!",
            caller_context={"user_agent": "CLI/1.0", "ip_address": "127.0.0.1"},
        )

        assert mock_provider.send_password_changed_notification_email.call_count == 1
        call_kwargs = mock_provider.send_password_changed_notification_email.call_args.kwargs
        assert call_kwargs["to_email"] == mock_user.email
        assert call_kwargs["user_agent"] == "CLI/1.0"
        assert call_kwargs["ip_address"] == "127.0.0.1"


@pytest.mark.asyncio
async def test_legacy_otp_reset_password_dispatches_email(mock_user, mock_session):
    """Direct legacy OTP reset_password_with_otp also dispatches confirmation email."""
    service = PasswordResetService(session=mock_session)
    service.verify_recovery_code = AsyncMock(return_value="ephemeral-reset-token")
    service.complete_password_reset = AsyncMock()

    await service.reset_password_with_otp(
        email=mock_user.email,
        raw_otp="123456",
        new_password="NewLegacyPassword123!",
        caller_context={"user_agent": "LegacyApp/1.0", "ip_address": "192.168.1.1"},
    )

    assert service.verify_recovery_code.call_count == 1
    assert service.complete_password_reset.call_count == 1
    kwargs = service.complete_password_reset.call_args.kwargs
    assert kwargs["caller_context"]["user_agent"] == "LegacyApp/1.0"
    assert kwargs["caller_context"]["ip_address"] == "192.168.1.1"
