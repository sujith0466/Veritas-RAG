"""Password Reset Service.

Handles secure single-use token generation, expiry, validation, and password resetting.
Also supports Email OTP recovery workflows.
"""

import datetime
import hashlib
import secrets
import uuid
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.core.exceptions.auth import AuthenticationException
from backend.core.security.password import get_password_hash
from backend.models.entities.user import User
from backend.models.entities.user_session import UserSession
from backend.models.entities.password_otp import PasswordRecoveryOTP
from backend.repositories.implementations.user_repository import UserRepository
from backend.services.email.provider import get_email_provider
from backend.cache.client import get_redis_client

logger = structlog.get_logger(__name__)

class PasswordResetService:
    """Orchestrates secure password reset flows."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.redis = get_redis_client()

    async def _execute_password_reset(self, user: User, new_password: str) -> None:
        """Internal shared method to update password and revoke sessions."""
        user.hashed_password = get_password_hash(new_password)
        user.password_changed_at = datetime.datetime.now(datetime.UTC)
        
        # Invalidate sessions (F2.5 Requirement)
        stmt_revoke = (
            update(UserSession)
            .where(UserSession.user_id == user.id, UserSession.is_revoked.is_(False))
            .values(is_revoked=True, refresh_token_hash=None)
        )
        await self.session.execute(stmt_revoke)
        
        await self.session.commit()
        
        logger.info("Password reset completed", user_id=str(user.id))

    async def generate_and_send_reset_token(self, email: str) -> None:
        """Generates a secure token and dispatches the reset email."""
        email_normalized = email.lower().strip()
        user = await self.user_repo.get_by_email(email_normalized)
        
        # Always log that a request was made
        logger.info("Password reset requested", email_provided=True)
        
        if not user or not user.is_active:
            # We don't log the email if they don't exist to prevent leak, just a generic log
            logger.info("Invalid reset attempt", reason="user_not_found_or_inactive")
            return

        # Generate secure raw token
        raw_token = secrets.token_urlsafe(64)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        
        user.password_reset_token_hash = token_hash
        user.password_reset_token_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
        
        await self.session.commit()
        
        # Send the email
        email_provider = get_email_provider()
        await email_provider.send_password_reset_email(email_normalized, raw_token)

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        """Validates token and updates the user's password."""
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        
        stmt = select(User).where(
            User.password_reset_token_hash == token_hash,
            User.is_deleted.is_(False)
        )
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or not user.password_reset_token_hash:
            logger.warning("Invalid reset attempt", reason="token_not_found")
            raise AuthenticationException("Invalid or expired reset token")

        # Constant-time comparison
        if not secrets.compare_digest(token_hash, user.password_reset_token_hash):
            logger.warning("Invalid reset attempt", reason="hash_mismatch")
            raise AuthenticationException("Invalid or expired reset token")
            
        if not user.password_reset_token_expires_at:
            logger.warning("Invalid reset attempt", reason="token_missing_expiry")
            raise AuthenticationException("Invalid or expired reset token")
            
        if datetime.datetime.now(datetime.UTC) > user.password_reset_token_expires_at.replace(tzinfo=datetime.UTC):
            logger.warning("Invalid reset attempt", reason="token_expired")
            raise AuthenticationException("Invalid or expired reset token")

        # Clear token fields
        user.password_reset_token_hash = None
        user.password_reset_token_expires_at = None
        
        await self._execute_password_reset(user, new_password)

    # ─── F2.9 OTP Flow ─────────────────────────────────────────────────────────────

    async def request_otp(self, email: str) -> None:
        """Generates an OTP and dispatches it via email, subject to rate limits."""
        email_normalized = email.lower().strip()
        user = await self.user_repo.get_by_email(email_normalized)
        
        logger.info("OTP password reset requested", email_provided=True)
        
        if not user or not user.is_active:
            logger.info("Invalid OTP request attempt", reason="user_not_found_or_inactive")
            return

        user_id_str = str(user.id)

        if self.redis:
            # Cooldown check (60s)
            cooldown_key = f"otp_cooldown:{user_id_str}"
            if await self.redis.get(cooldown_key):
                logger.warning("OTP requested too frequently", user_id=user_id_str)
                # Fail silently to user, returning generic response at the API level
                return
            
            # Rate limit check (3 per 15 mins)
            rate_limit_key = f"otp_requests:{user_id_str}"
            request_count = await self.redis.get(rate_limit_key)
            if request_count and int(request_count) >= 3:
                logger.warning("OTP request limit exceeded", user_id=user_id_str)
                return

            # Apply limits
            await self.redis.setex(cooldown_key, 60, "1")
            
            # Since strict limits require pipelining, and our redis client may or may not support pipeline cleanly:
            await self.redis.incr(rate_limit_key)
            if not request_count:
                await self.redis.expire(rate_limit_key, 900) # 15 minutes
            
        # Invalidate existing active OTPs for this user
        stmt_invalidate = (
            update(PasswordRecoveryOTP)
            .where(
                PasswordRecoveryOTP.user_id == user.id,
                PasswordRecoveryOTP.is_invalidated.is_(False),
                PasswordRecoveryOTP.is_used.is_(False)
            )
            .values(is_invalidated=True)
        )
        await self.session.execute(stmt_invalidate)

        # Generate 6-digit numeric OTP
        raw_otp = "".join(secrets.choice("0123456789") for _ in range(6))
        otp_hash = hashlib.sha256(raw_otp.encode("utf-8")).hexdigest()
        
        otp_entry = PasswordRecoveryOTP(
            user_id=user.id,
            otp_hash=otp_hash,
            expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=10)
        )
        self.session.add(otp_entry)
        await self.session.commit()
        
        email_provider = get_email_provider()
        if hasattr(email_provider, "send_otp_email"):
            await email_provider.send_otp_email(email_normalized, raw_otp)
        else:
            logger.info("OTP Email sent (mocked)", email=email_normalized) 
            logger.info(f"Your RAGuard verification code is: {raw_otp}")

    async def _get_active_otp(self, user_id: uuid.UUID) -> PasswordRecoveryOTP | None:
        stmt = select(PasswordRecoveryOTP).where(
            PasswordRecoveryOTP.user_id == user_id,
            PasswordRecoveryOTP.is_used.is_(False),
            PasswordRecoveryOTP.is_invalidated.is_(False)
        ).order_by(PasswordRecoveryOTP.requested_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def verify_otp(self, email: str, raw_otp: str) -> None:
        """Verifies the OTP hash and records attempt."""
        email_normalized = email.lower().strip()
        user = await self.user_repo.get_by_email(email_normalized)
        
        if not user or not user.is_active:
            raise AuthenticationException("Invalid or expired OTP")

        otp_entry = await self._get_active_otp(user.id)
        
        if not otp_entry:
            raise AuthenticationException("Invalid or expired OTP")
            
        if datetime.datetime.now(datetime.UTC) > otp_entry.expires_at.replace(tzinfo=datetime.UTC):
            otp_entry.is_invalidated = True
            await self.session.commit()
            logger.warning("OTP expired", user_id=str(user.id))
            raise AuthenticationException("Invalid or expired OTP")

        otp_entry.attempts += 1
        
        if otp_entry.attempts > 5:
            otp_entry.is_invalidated = True
            await self.session.commit()
            logger.warning("Too many OTP attempts", user_id=str(user.id))
            raise AuthenticationException("Invalid or expired OTP")

        incoming_hash = hashlib.sha256(raw_otp.encode("utf-8")).hexdigest()
        
        if not secrets.compare_digest(incoming_hash, otp_entry.otp_hash):
            await self.session.commit()
            logger.warning("Invalid OTP attempt", user_id=str(user.id))
            raise AuthenticationException("Invalid or expired OTP")

        otp_entry.verified_at = datetime.datetime.now(datetime.UTC)
        await self.session.commit()
        
        logger.info("OTP verified successfully", user_id=str(user.id))
        
    async def reset_password_with_otp(self, email: str, raw_otp: str, new_password: str) -> None:
        """Final validation of OTP and updates the password."""
        email_normalized = email.lower().strip()
        user = await self.user_repo.get_by_email(email_normalized)
        
        if not user or not user.is_active:
            raise AuthenticationException("Invalid or expired OTP")

        otp_entry = await self._get_active_otp(user.id)
        if not otp_entry:
            raise AuthenticationException("Invalid or expired OTP")

        if datetime.datetime.now(datetime.UTC) > otp_entry.expires_at.replace(tzinfo=datetime.UTC):
            otp_entry.is_invalidated = True
            await self.session.commit()
            logger.warning("OTP expired during reset", user_id=str(user.id))
            raise AuthenticationException("Invalid or expired OTP")

        incoming_hash = hashlib.sha256(raw_otp.encode("utf-8")).hexdigest()
        if not secrets.compare_digest(incoming_hash, otp_entry.otp_hash):
            otp_entry.attempts += 1
            if otp_entry.attempts > 5:
                otp_entry.is_invalidated = True
            await self.session.commit()
            logger.warning("Invalid OTP attempt during reset", user_id=str(user.id))
            raise AuthenticationException("Invalid or expired OTP")

        # Success - update password
        otp_entry.is_used = True
        otp_entry.verified_at = datetime.datetime.now(datetime.UTC) # just in case verify endpoint was skipped
        
        await self._execute_password_reset(user, new_password)
        logger.info("OTP password reset completed", user_id=str(user.id))

    # ─── Authenticated Password Change ────────────────────────────────────────────

    async def change_password(self, user_id: uuid.UUID, current_password: str, new_password: str) -> None:
        """Change password for an authenticated user.

        Verifies the current password before updating. Revokes all active sessions
        and refresh token families, requiring a fresh login.

        Args:
            user_id: The authenticated user's UUID.
            current_password: The user's existing password for verification.
            new_password: The desired new password.

        Raises:
            AuthenticationException: If current password is wrong or user not found.
        """
        from backend.core.security.password import verify_password

        stmt = select(User).where(User.id == user_id, User.is_deleted.is_(False))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.hashed_password:
            logger.warning("Change password failed", reason="user_not_found_or_no_password", user_id=str(user_id))
            raise AuthenticationException("Current password is incorrect")

        if not verify_password(current_password, user.hashed_password):
            logger.warning("Change password failed", reason="incorrect_current_password", user_id=str(user_id))
            raise AuthenticationException("Current password is incorrect")

        await self._execute_password_reset(user, new_password)
        logger.info("Authenticated password change completed", user_id=str(user_id))

