"""Password Reset Service.

Handles secure single-use token generation, expiry, validation, and password resetting.
Also supports Email OTP recovery workflows with two-phase verification.
"""

import asyncio
import datetime
import hashlib
import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.cache.client import get_redis_client
from backend.core.exceptions.auth import AuthenticationException
from backend.core.security.password import get_password_hash
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.password_otp import PasswordRecoveryOTP
from backend.models.entities.user import User
from backend.models.entities.user_session import UserSession
from backend.models.entities.workspace_member import WorkspaceMember
from backend.repositories.implementations.user_repository import UserRepository
from backend.services.email.provider import get_email_provider

logger = structlog.get_logger(__name__)


def _mask_email(email: str) -> str:
    """Mask email for privacy-preserving audit logs and error messages (e.g. u***@veritas.rag)."""
    if not email or "@" not in email:
        return "***"
    local_part, domain = email.split("@", 1)
    if len(local_part) <= 1:
        masked_local = f"{local_part}***"
    else:
        masked_local = f"{local_part[0]}***"
    return f"{masked_local}@{domain}"


class PasswordResetService:
    """Orchestrates secure password reset flows."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.redis = get_redis_client()

    async def _execute_password_reset(
        self, user: User, new_password: str, action: str = "password_reset.completed"
    ) -> None:
        """Internal shared method to update password, revoke sessions, and invalidate workspace access tokens."""
        user.hashed_password = get_password_hash(new_password)
        user.password_changed_at = datetime.datetime.now(datetime.UTC)

        # 1. Invalidate sessions in PostgreSQL (F2.5 Requirement)
        stmt_revoke = (
            update(UserSession)
            .where(UserSession.user_id == user.id, UserSession.is_revoked.is_(False))
            .values(is_revoked=True)
        )
        await self.session.execute(stmt_revoke)

        # 2. Query user's active workspaces
        stmt_members = select(WorkspaceMember.workspace_id).where(
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.is_deleted.is_(False),
        )
        res = await self.session.execute(stmt_members)
        workspace_ids = res.scalars().all()

        # 3. Insert audit log
        tenant_uuid = None
        if user.tenant_id:
            try:
                tenant_uuid = uuid.UUID(str(user.tenant_id))
            except (ValueError, TypeError):
                tenant_uuid = None

        audit = AuditLog(
            tenant_id=tenant_uuid,
            action=action,
            user_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
            details={"revoked_workspaces_count": len(workspace_ids)},
            status="success",
        )
        self.session.add(audit)
        await self.session.commit()

        # 4. Invalidate workspace access tokens in Redis
        try:
            from backend.core.security.jwt import get_jwt_service

            jwt_service = get_jwt_service()
            for ws_id in workspace_ids:
                await jwt_service.revoke_user_workspace_tokens(str(user.id), str(ws_id))
        except Exception as exc:
            logger.warning("Failed to revoke workspace tokens in Redis", user_id=str(user.id), error=str(exc))

        logger.info("Password reset and session revocation executed", user_id=str(user.id))

    async def generate_and_send_reset_token(self, email: str) -> None:
        """Generates a secure token and dispatches the reset email."""
        email_normalized = email.lower().strip()
        user = await self.user_repo.get_by_email(email_normalized)

        # Always log that a request was made
        logger.info("Password reset requested", email_provided=True)

        if not user or not user.is_active or user.is_deleted:
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
            User.is_deleted.is_(False),
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

    async def request_recovery_code(self, email: str) -> None:
        """Generates a 6-digit numeric OTP and dispatches it via email.

        Enforces cooldown and velocity rate limits on the SHA-256 hash of the normalized email
        BEFORE checking database existence to eliminate account enumeration oracles.
        Applies equivalent dummy processing for non-existent or inactive accounts to mitigate
        timing side channels.
        """
        email_normalized = email.lower().strip()
        email_hash = hashlib.sha256(email_normalized.encode("utf-8")).hexdigest()

        # Enforce rate limits on email_hash (Oracle Elimination)
        if self.redis:
            cooldown_key = f"auth:recovery:cooldown:{email_hash}"
            if await self.redis.get(cooldown_key):
                logger.warning("Recovery code requested too frequently", email_hash=email_hash)
                raise HTTPException(
                    status_code=429,
                    detail="Please wait before requesting another verification code.",
                )

            velocity_key = f"auth:recovery:requests:{email_hash}"
            req_count = await self.redis.get(velocity_key)
            if req_count and int(req_count) >= 3:
                logger.warning("Recovery code velocity limit exceeded", email_hash=email_hash)
                raise HTTPException(
                    status_code=429,
                    detail="Too many recovery requests. Please try again later.",
                )

            await self.redis.set(cooldown_key, "1", ex=60)
            await self.redis.incr(velocity_key)
            if not req_count:
                await self.redis.expire(velocity_key, 900)

        user = await self.user_repo.get_by_email(email_normalized)

        if not user or not user.is_active or user.is_deleted:
            # Equivalent dummy processing to prevent timing side channels
            _ = "".join(secrets.choice("0123456789") for _ in range(6))
            _ = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
            await self.session.execute(select(1))
            await asyncio.sleep(0.02)
            logger.info(
                "Password recovery requested for non-existent or inactive account",
                email_hash=email_hash,
            )
            return

        # Invalidate existing active OTPs for this user
        stmt_invalidate = (
            update(PasswordRecoveryOTP)
            .where(
                PasswordRecoveryOTP.user_id == user.id,
                PasswordRecoveryOTP.is_invalidated.is_(False),
                PasswordRecoveryOTP.is_used.is_(False),
            )
            .values(is_invalidated=True)
        )
        await self.session.execute(stmt_invalidate)

        # Generate 6-digit numeric OTP (CSPRNG)
        raw_otp = "".join(secrets.choice("0123456789") for _ in range(6))
        otp_hash = hashlib.sha256(raw_otp.encode("utf-8")).hexdigest()

        now = datetime.datetime.now(datetime.UTC)
        otp_entry = PasswordRecoveryOTP(
            user_id=user.id,
            otp_hash=otp_hash,
            channel="EMAIL",
            requested_at=now,
            expires_at=now + datetime.timedelta(minutes=10),
            attempts=0,
            is_used=False,
            is_invalidated=False,
        )
        self.session.add(otp_entry)

        # Record AuditLog
        tenant_uuid = None
        if user.tenant_id:
            try:
                tenant_uuid = uuid.UUID(str(user.tenant_id))
            except (ValueError, TypeError):
                tenant_uuid = None

        audit = AuditLog(
            tenant_id=tenant_uuid,
            action="password_reset.requested",
            user_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
            details={"masked_email": _mask_email(email_normalized), "channel": "EMAIL"},
            status="success",
        )
        self.session.add(audit)
        await self.session.commit()

        email_provider = get_email_provider()
        await email_provider.send_otp_email(email_normalized, raw_otp)
        logger.info("Password recovery code dispatched", user_id=str(user.id))

    async def request_otp(self, email: str) -> None:
        """Backward-compatible alias for request_recovery_code."""
        await self.request_recovery_code(email)

    async def _get_active_otp(self, user_id: uuid.UUID) -> PasswordRecoveryOTP | None:
        stmt = (
            select(PasswordRecoveryOTP)
            .where(
                PasswordRecoveryOTP.user_id == user_id,
                PasswordRecoveryOTP.is_used.is_(False),
                PasswordRecoveryOTP.is_invalidated.is_(False),
            )
            .order_by(PasswordRecoveryOTP.requested_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def verify_recovery_code(self, email: str, raw_otp: str) -> str:
        """Verifies the 6-digit OTP and generates an ephemeral 256-bit CSPRNG reset token.

        Returns:
            The raw 256-bit URL-safe reset token valid for 15 minutes.
        """
        email_normalized = email.lower().strip()
        user = await self.user_repo.get_by_email(email_normalized)

        if not user or not user.is_active or user.is_deleted:
            raise AuthenticationException("Invalid or expired verification code")

        otp_entry = await self._get_active_otp(user.id)
        if not otp_entry:
            raise AuthenticationException("Invalid or expired verification code")

        now = datetime.datetime.now(datetime.UTC)
        if now > otp_entry.expires_at.replace(tzinfo=datetime.UTC):
            otp_entry.is_invalidated = True
            self.session.add(
                AuditLog(
                    user_id=user.id,
                    action="password_reset.verification_failed",
                    resource_type="user",
                    resource_id=str(user.id),
                    details={"reason": "expired", "attempts": otp_entry.attempts},
                    status="failure",
                )
            )
            await self.session.commit()
            logger.warning("OTP expired", user_id=str(user.id))
            raise AuthenticationException("Invalid or expired verification code")

        otp_entry.attempts += 1

        if otp_entry.attempts > 5:
            otp_entry.is_invalidated = True
            self.session.add(
                AuditLog(
                    user_id=user.id,
                    action="password_reset.verification_failed",
                    resource_type="user",
                    resource_id=str(user.id),
                    details={"reason": "max_attempts_exceeded", "attempts": otp_entry.attempts},
                    status="failure",
                )
            )
            await self.session.commit()
            logger.warning("Too many OTP attempts", user_id=str(user.id))
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Code has been invalidated.",
            )

        incoming_hash = hashlib.sha256(raw_otp.encode("utf-8")).hexdigest()
        if not secrets.compare_digest(incoming_hash, otp_entry.otp_hash):
            self.session.add(
                AuditLog(
                    user_id=user.id,
                    action="password_reset.verification_failed",
                    resource_type="user",
                    resource_id=str(user.id),
                    details={"reason": "hash_mismatch", "attempts": otp_entry.attempts},
                    status="failure",
                )
            )
            await self.session.commit()
            logger.warning("Invalid OTP attempt", user_id=str(user.id))
            raise AuthenticationException("Invalid or expired verification code")

        # Code is valid
        otp_entry.verified_at = now

        # Generate ephemeral 256-bit CSPRNG reset token
        raw_reset_token = secrets.token_urlsafe(32)
        reset_token_hash = hashlib.sha256(raw_reset_token.encode("utf-8")).hexdigest()

        user.password_reset_token_hash = reset_token_hash
        user.password_reset_token_expires_at = now + datetime.timedelta(minutes=15)

        self.session.add(
            AuditLog(
                user_id=user.id,
                action="password_reset.verified",
                resource_type="user",
                resource_id=str(user.id),
                details={"channel": "EMAIL"},
                status="success",
            )
        )
        await self.session.commit()

        logger.info("OTP verified and reset token issued", user_id=str(user.id))
        return raw_reset_token

    async def verify_otp(self, email: str, raw_otp: str) -> None:
        """Backward-compatible alias for verify_recovery_code."""
        await self.verify_recovery_code(email, raw_otp)

    async def complete_password_reset(
        self, email: str, reset_token: str, new_password: str
    ) -> None:
        """Validates the 256-bit CSPRNG reset token and completes password reset."""
        email_normalized = email.lower().strip()
        user = await self.user_repo.get_by_email(email_normalized)

        if not user or not user.is_active or user.is_deleted:
            raise AuthenticationException("Invalid, expired, or previously consumed reset credential")

        if not user.password_reset_token_hash or not user.password_reset_token_expires_at:
            raise AuthenticationException("Invalid, expired, or previously consumed reset credential")

        now = datetime.datetime.now(datetime.UTC)
        if now > user.password_reset_token_expires_at.replace(tzinfo=datetime.UTC):
            user.password_reset_token_hash = None
            user.password_reset_token_expires_at = None
            await self.session.commit()
            raise AuthenticationException("Invalid, expired, or previously consumed reset credential")

        incoming_token_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()
        if not secrets.compare_digest(incoming_token_hash, user.password_reset_token_hash):
            raise AuthenticationException("Invalid, expired, or previously consumed reset credential")

        # Clear token fields
        user.password_reset_token_hash = None
        user.password_reset_token_expires_at = None

        # Mark OTP as used if present
        otp_entry = await self._get_active_otp(user.id)
        if otp_entry:
            otp_entry.is_used = True

        await self._execute_password_reset(user, new_password, action="password_reset.completed")
        logger.info("Password reset completed successfully via reset token", user_id=str(user.id))

    async def reset_password_with_otp(
        self, email: str, raw_otp: str, new_password: str
    ) -> None:
        """Legacy direct OTP reset method. Verifies OTP, obtains reset token, and completes reset."""
        reset_token = await self.verify_recovery_code(email, raw_otp)
        await self.complete_password_reset(email, reset_token, new_password)

    # ─── Authenticated Password Change ────────────────────────────────────────────

    async def change_password(
        self, user_id: uuid.UUID, current_password: str, new_password: str
    ) -> None:
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
            logger.warning(
                "Change password failed",
                reason="user_not_found_or_no_password",
                user_id=str(user_id),
            )
            raise AuthenticationException("Current password is incorrect")

        if not verify_password(current_password, user.hashed_password):
            logger.warning(
                "Change password failed",
                reason="incorrect_current_password",
                user_id=str(user_id),
            )
            raise AuthenticationException("Current password is incorrect")

        await self._execute_password_reset(user, new_password, action="password.changed")
        logger.info("Authenticated password change completed", user_id=str(user_id))

    # ─── Authenticated Security-Code Password Change (F2.10) ──────────────────────

    async def request_security_code(self, user_id: uuid.UUID) -> None:
        """Generates a 6-digit numeric security code and dispatches it to the user's email.

        Enforces cooldown (60s) and velocity limits (max 3 per 15 min) in Redis on user_id.
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active or user.is_deleted:
            raise AuthenticationException("User account is inactive or not found")

        # Rate limiting in Redis
        if self.redis:
            cooldown_key = f"auth:change_pwd:cooldown:{user.id}"
            if await self.redis.get(cooldown_key):
                logger.warning("Security code requested too frequently", user_id=str(user.id))
                raise HTTPException(
                    status_code=429,
                    detail="Please wait before requesting another security code.",
                )

            velocity_key = f"auth:change_pwd:requests:{user.id}"
            req_count = await self.redis.get(velocity_key)
            if req_count and int(req_count) >= 3:
                logger.warning("Security code velocity limit exceeded", user_id=str(user.id))
                raise HTTPException(
                    status_code=429,
                    detail="Too many security code requests. Please try again later.",
                )

            await self.redis.set(cooldown_key, "1", ex=60)
            await self.redis.incr(velocity_key)
            if not req_count:
                await self.redis.expire(velocity_key, 900)

        # Invalidate existing active OTPs for this user with channel AUTH_CHANGE_PASSWORD
        stmt_invalidate = (
            update(PasswordRecoveryOTP)
            .where(
                PasswordRecoveryOTP.user_id == user.id,
                PasswordRecoveryOTP.channel == "AUTH_CHANGE_PASSWORD",
                PasswordRecoveryOTP.is_invalidated.is_(False),
                PasswordRecoveryOTP.is_used.is_(False),
            )
            .values(is_invalidated=True)
        )
        await self.session.execute(stmt_invalidate)

        # Generate 6-digit CSPRNG code
        raw_code = "".join(secrets.choice("0123456789") for _ in range(6))
        code_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()

        now = datetime.datetime.now(datetime.UTC)
        otp_entry = PasswordRecoveryOTP(
            user_id=user.id,
            otp_hash=code_hash,
            channel="AUTH_CHANGE_PASSWORD",
            requested_at=now,
            expires_at=now + datetime.timedelta(minutes=10),
            attempts=0,
            is_used=False,
            is_invalidated=False,
        )
        self.session.add(otp_entry)

        # Record AuditLog
        tenant_uuid = None
        if user.tenant_id:
            try:
                tenant_uuid = uuid.UUID(str(user.tenant_id))
            except (ValueError, TypeError):
                tenant_uuid = None

        audit = AuditLog(
            tenant_id=tenant_uuid,
            action="security_code.requested",
            user_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
            details={"masked_email": _mask_email(user.email), "channel": "EMAIL"},
            status="success",
        )
        self.session.add(audit)
        await self.session.commit()

        email_provider = get_email_provider()
        await email_provider.send_security_code_email(user.email, raw_code)
        logger.info("Password change security code dispatched", user_id=str(user.id))

    async def verify_security_code(self, user_id: uuid.UUID, raw_code: str) -> str:
        """Verifies the 6-digit security code and issues a single-use change token.

        Returns:
            The raw 256-bit URL-safe change_token valid for 15 minutes.
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active or user.is_deleted:
            raise AuthenticationException("User account is inactive or not found")

        stmt = (
            select(PasswordRecoveryOTP)
            .where(
                PasswordRecoveryOTP.user_id == user.id,
                PasswordRecoveryOTP.channel == "AUTH_CHANGE_PASSWORD",
                PasswordRecoveryOTP.is_used.is_(False),
                PasswordRecoveryOTP.is_invalidated.is_(False),
            )
            .order_by(PasswordRecoveryOTP.requested_at.desc())
        )
        res = await self.session.execute(stmt)
        otp_entry = res.scalars().first()

        if not otp_entry:
            raise AuthenticationException("Invalid or expired security code")

        now = datetime.datetime.now(datetime.UTC)
        if now > otp_entry.expires_at.replace(tzinfo=datetime.UTC):
            otp_entry.is_invalidated = True
            self.session.add(
                AuditLog(
                    user_id=user.id,
                    action="security_code.verification_failed",
                    resource_type="user",
                    resource_id=str(user.id),
                    details={"reason": "expired", "attempts": otp_entry.attempts},
                    status="failure",
                )
            )
            await self.session.commit()
            logger.warning("Security code expired", user_id=str(user.id))
            raise AuthenticationException("Invalid or expired security code")

        otp_entry.attempts += 1

        if otp_entry.attempts > 5:
            otp_entry.is_invalidated = True
            self.session.add(
                AuditLog(
                    user_id=user.id,
                    action="security_code.verification_failed",
                    resource_type="user",
                    resource_id=str(user.id),
                    details={"reason": "max_attempts_exceeded", "attempts": otp_entry.attempts},
                    status="failure",
                )
            )
            await self.session.commit()
            logger.warning("Too many security code attempts", user_id=str(user.id))
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Code has been invalidated.",
            )

        incoming_hash = hashlib.sha256(raw_code.encode("utf-8")).hexdigest()
        if not secrets.compare_digest(incoming_hash, otp_entry.otp_hash):
            self.session.add(
                AuditLog(
                    user_id=user.id,
                    action="security_code.verification_failed",
                    resource_type="user",
                    resource_id=str(user.id),
                    details={"reason": "hash_mismatch", "attempts": otp_entry.attempts},
                    status="failure",
                )
            )
            await self.session.commit()
            logger.warning("Invalid security code attempt", user_id=str(user.id))
            raise AuthenticationException("Invalid or expired security code")

        # Code valid
        otp_entry.verified_at = now
        otp_entry.is_used = True

        raw_change_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_change_token.encode("utf-8")).hexdigest()

        # Store in Redis with 15-minute TTL
        if self.redis:
            await self.redis.set(f"auth:change_pwd_token:{token_hash}", str(user.id), ex=900)

        # Also store in DB for resilient lookup
        user.password_reset_token_hash = token_hash
        user.password_reset_token_expires_at = now + datetime.timedelta(minutes=15)

        self.session.add(
            AuditLog(
                user_id=user.id,
                action="security_code.verified",
                resource_type="user",
                resource_id=str(user.id),
                details={"channel": "EMAIL"},
                status="success",
            )
        )
        await self.session.commit()

        logger.info("Security code verified and change token issued", user_id=str(user.id))
        return raw_change_token

    async def complete_password_change(
        self, user_id: uuid.UUID, change_token: str, new_password: str
    ) -> None:
        """Validates change_token and updates password for authenticated user."""
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active or user.is_deleted:
            raise AuthenticationException("Invalid, expired, or previously consumed credential")

        token_hash = hashlib.sha256(change_token.encode("utf-8")).hexdigest()

        token_valid = False
        if self.redis:
            redis_key = f"auth:change_pwd_token:{token_hash}"
            stored_user_id = await self.redis.get(redis_key)
            if stored_user_id and stored_user_id == str(user.id):
                token_valid = True
                await self.redis.delete(redis_key)

        if not token_valid:
            if (
                user.password_reset_token_hash
                and secrets.compare_digest(token_hash, user.password_reset_token_hash)
                and user.password_reset_token_expires_at
                and datetime.datetime.now(datetime.UTC) <= user.password_reset_token_expires_at.replace(tzinfo=datetime.UTC)
            ):
                token_valid = True

        if not token_valid:
            raise AuthenticationException("Invalid, expired, or previously consumed credential")

        # Clear token fields in DB
        user.password_reset_token_hash = None
        user.password_reset_token_expires_at = None

        await self._execute_password_reset(user, new_password, action="password.changed")
        logger.info("Password change completed successfully via change token", user_id=str(user.id))
