import datetime
import hashlib
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.entities.audit_log import AuditLog
from backend.models.entities.password_otp import PasswordRecoveryOTP
from backend.models.entities.user import User
from backend.services.auth.password_reset_service import PasswordResetService
from backend.core.exceptions.auth import AuthenticationException
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_request_security_code_success():
    """Verify requesting security code creates OTP record and dispatches email."""
    user_id = uuid.uuid4()
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.email = "test.security@veritas.rag"
    mock_user.is_active = True
    mock_user.is_deleted = False
    mock_user.tenant_id = None

    mock_session = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.incr = AsyncMock()
    mock_redis.expire = AsyncMock()

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)
    service.redis = mock_redis

    with patch("backend.services.auth.password_reset_service.get_email_provider") as mock_email_fn:
        mock_provider = MagicMock()
        mock_provider.send_security_code_email = AsyncMock(return_value=True)
        mock_email_fn.return_value = mock_provider

        await service.request_security_code(user_id)

        assert mock_provider.send_security_code_email.call_count == 1
        call_email, raw_code = mock_provider.send_security_code_email.call_args[0]
        assert call_email == "test.security@veritas.rag"
        assert len(raw_code) == 6
        assert raw_code.isdigit()

        # Session commit called
        assert mock_session.commit.call_count >= 1


@pytest.mark.asyncio
async def test_request_security_code_cooldown():
    """Verify rate limit cooldown prevents rapid code requests."""
    user_id = uuid.uuid4()
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.is_active = True
    mock_user.is_deleted = False

    mock_session = AsyncMock()
    mock_redis = AsyncMock()
    # Cooldown active
    mock_redis.get = AsyncMock(side_effect=lambda key: "1" if "cooldown" in key else None)

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)
    service.redis = mock_redis

    with pytest.raises(HTTPException) as exc:
        await service.request_security_code(user_id)
    assert exc.value.status_code == 429
    assert "Please wait before requesting another security code" in exc.value.detail


@pytest.mark.asyncio
async def test_verify_security_code_valid_returns_change_token():
    """Verify correct security code produces 256-bit URL-safe change_token."""
    user_id = uuid.uuid4()
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.is_active = True
    mock_user.is_deleted = False

    raw_code = "654321"
    code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()

    mock_otp = MagicMock(spec=PasswordRecoveryOTP)
    mock_otp.user_id = user_id
    mock_otp.channel = "AUTH_CHANGE_PASSWORD"
    mock_otp.otp_hash = code_hash
    mock_otp.expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=10)
    mock_otp.attempts = 0
    mock_otp.is_used = False
    mock_otp.is_invalidated = False

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_otp)))
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock()

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)
    service.redis = mock_redis

    change_token = await service.verify_security_code(user_id, raw_code)

    assert isinstance(change_token, str)
    assert len(change_token) >= 32
    assert mock_otp.is_used is True
    assert mock_otp.verified_at is not None
    assert mock_redis.set.call_count == 1


@pytest.mark.asyncio
async def test_verify_security_code_max_attempts_invalidates():
    """Verify that > 5 invalid attempts invalidates the code and returns 429."""
    user_id = uuid.uuid4()
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.is_active = True
    mock_user.is_deleted = False

    code_hash = hashlib.sha256(b"000000").hexdigest()

    mock_otp = MagicMock(spec=PasswordRecoveryOTP)
    mock_otp.user_id = user_id
    mock_otp.channel = "AUTH_CHANGE_PASSWORD"
    mock_otp.otp_hash = code_hash
    mock_otp.expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=10)
    mock_otp.attempts = 5  # Next attempt makes it 6 -> max attempts
    mock_otp.is_used = False
    mock_otp.is_invalidated = False

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_otp)))
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)
    service.redis = None

    with pytest.raises(HTTPException) as exc:
        await service.verify_security_code(user_id, "999999")

    assert exc.value.status_code == 429
    assert mock_otp.is_invalidated is True


@pytest.mark.asyncio
async def test_complete_password_change_success():
    """Verify completing password change with valid change_token updates password and revokes sessions."""
    user_id = uuid.uuid4()
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.is_active = True
    mock_user.is_deleted = False
    mock_user.tenant_id = None

    raw_token = "valid-ephemeral-change-token-12345"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    mock_session = AsyncMock()
    mock_redis = AsyncMock()
    # Redis has token pointing to user_id
    mock_redis.get = AsyncMock(return_value=str(user_id))
    mock_redis.delete = AsyncMock()

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)
    service.redis = mock_redis
    service._execute_password_reset = AsyncMock()

    await service.complete_password_change(user_id, raw_token, "BrandNewPassword123!")

    assert service._execute_password_reset.call_count == 1
    assert mock_redis.delete.call_count == 1


@pytest.mark.asyncio
async def test_complete_password_change_invalid_token_fails():
    """Verify invalid change_token raises AuthenticationException."""
    user_id = uuid.uuid4()
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.is_active = True
    mock_user.is_deleted = False
    mock_user.password_reset_token_hash = None
    mock_user.password_reset_token_expires_at = None

    mock_session = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)
    service.redis = mock_redis

    with pytest.raises(AuthenticationException):
        await service.complete_password_change(user_id, "invalid-token", "NewPassword123!")


@pytest.mark.asyncio
async def test_legacy_change_password_method_permanently_disabled():
    """Verify legacy change_password method raises AuthenticationException and performs no mutation."""
    user_id = uuid.uuid4()
    mock_session = AsyncMock()
    service = PasswordResetService(session=mock_session)
    service._execute_password_reset = AsyncMock()

    with pytest.raises(AuthenticationException) as exc:
        await service.change_password(user_id, "OldPassword123!", "NewPassword456!")

    assert "deprecated and disabled" in str(exc.value)
    assert service._execute_password_reset.call_count == 0
    assert mock_session.commit.call_count == 0


@pytest.mark.asyncio
async def test_verify_security_code_single_use():
    """Verify previously used security code cannot be re-verified."""
    user_id = uuid.uuid4()
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.is_active = True
    mock_user.is_deleted = False

    raw_code = "112233"
    code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()

    # OTP already used
    mock_otp = MagicMock(spec=PasswordRecoveryOTP)
    mock_otp.user_id = user_id
    mock_otp.channel = "AUTH_CHANGE_PASSWORD"
    mock_otp.otp_hash = code_hash
    mock_otp.expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=10)
    mock_otp.attempts = 0
    mock_otp.is_used = True
    mock_otp.is_invalidated = False

    mock_session = AsyncMock()
    # Query filters out is_used=True, returning None
    mock_result = MagicMock()
    mock_result.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user)

    with pytest.raises(AuthenticationException) as exc:
        await service.verify_security_code(user_id, raw_code)

    assert "Invalid or expired security code" in str(exc.value)


@pytest.mark.asyncio
async def test_security_code_unrelated_user_isolation():
    """Verify security code issued for User A cannot be verified for User B."""
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    mock_user_b = MagicMock(spec=User)
    mock_user_b.id = user_b
    mock_user_b.is_active = True
    mock_user_b.is_deleted = False

    mock_session = AsyncMock()
    # Query for User B finds no OTP record
    mock_result = MagicMock()
    mock_result.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = PasswordResetService(session=mock_session)
    service.user_repo = MagicMock()
    service.user_repo.get_by_id = AsyncMock(return_value=mock_user_b)

    with pytest.raises(AuthenticationException) as exc:
        await service.verify_security_code(user_b, "123456")

    assert "Invalid or expired security code" in str(exc.value)

