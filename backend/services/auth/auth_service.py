"""Authentication Service.

Handles local login validation, bcrypt verification, and JWT issuance.
"""

import datetime
import hashlib

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.core.exceptions.auth import AuthenticationException
from backend.core.security.jwt import get_jwt_service
from backend.core.security.password import verify_password
from backend.models.entities.user_session import UserSession
from backend.repositories.implementations.user_repository import UserRepository

logger = structlog.get_logger(__name__)


class AuthService:
    """Orchestrates native login authentication and token issuance."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.jwt_service = get_jwt_service()

    async def login(self, email: str, plain_password: str, user_agent: str | None = None, ip_address: str | None = None, device: str | None = None) -> tuple[str, str]:
        """Authenticate user and issue new session tokens.

        Returns:
            A tuple of (access_token, raw_refresh_token).

        Raises:
            AuthenticationException: If credentials fail or account is inactive/unverified.
        """
        email_normalized = email.lower().strip()
        user = await self.user_repo.get_by_email(email_normalized)

        # Generic failure message for all paths to prevent enumeration
        generic_error = "Invalid email or password"

        if not user:
            # We must hash a dummy password to mitigate timing attacks against non-existent users
            verify_password(plain_password, "$2b$12$L9.C0k9L8g/V9V.Jg0Uq2OTL.Yw4O1n2X3V4Z5A6B7C8D9E0F1G2H")
            logger.info("Login attempt for non-existent user", email=email_normalized)
            raise AuthenticationException(generic_error)

        if not user.hashed_password:
            # Legacy users without passwords cannot log in via this flow
            logger.info("Login attempt for user without local password", user_id=str(user.id))
            raise AuthenticationException(generic_error)

        if not verify_password(plain_password, user.hashed_password):
            logger.info("Invalid password attempt", user_id=str(user.id))
            raise AuthenticationException(generic_error)

        if not user.is_active:
            logger.warning("Login attempt on disabled account", user_id=str(user.id))
            raise AuthenticationException("Account is disabled. Please contact support.")

        if not user.is_verified:
            logger.warning("Login attempt on unverified account", user_id=str(user.id))
            raise AuthenticationException("Please verify your email address before logging in.")

        # Authentication successful. Issue tokens.
        access_token, raw_refresh_token, family_id = await self.jwt_service.issue_tokens(user)

        # Hash the refresh token for storage
        refresh_token_hash = hashlib.sha256(raw_refresh_token.encode("utf-8")).hexdigest()

        # Create session
        expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7)
        session_entry = UserSession(
            user_id=user.id,
            refresh_token_hash=refresh_token_hash,
            family_id=family_id,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
            device=device,
            last_used_at=datetime.datetime.now(datetime.UTC),
        )

        user.last_login_at = datetime.datetime.now(datetime.UTC)

        self.session.add(session_entry)
        await self.session.commit()

        logger.info("User logged in successfully", user_id=str(user.id), family_id=family_id)

        return access_token, raw_refresh_token

    async def logout(self, jti: str, exp: int, user_id: int,
                     raw_refresh_token: str | None = None,
                     family_id: str | None = None) -> None:
        """Revokes the current access token and invalidates ALL refresh sessions for the user.

        AUTH-012: Logout always revokes all active UserSession records for the user,
        preventing refresh token replay after logout regardless of which refresh token
        cookie the client carries at logout time (e.g., when a separate refresh session
        exists that the logout request doesn't carry as a cookie).
        """
        from sqlalchemy import update

        # Add JTI to Redis blocklist (F2.4)
        await self.jwt_service.revoke_token(jti, exp)

        # AUTH-012: Revoke ALL active sessions for this user on logout.
        # This is the correct production contract: logging out invalidates any refresh
        # token issued to this user, regardless of session routing or cookie scope.
        stmt = (
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.is_revoked.is_(False),
            )
            .values(is_revoked=True)
        )
        await self.session.execute(stmt)
        await self.session.commit()

        logger.info("User logged out successfully — all sessions revoked",
                    user_id=str(user_id), family_id=str(family_id))


    async def rotate_refresh_token(self, raw_refresh_token: str, user_agent: str | None = None, ip_address: str | None = None, device: str | None = None) -> tuple[str, str]:
        """Rotates a refresh token for an active session.

        Returns:
            A tuple of (new_access_token, new_raw_refresh_token).

        Raises:
            AuthenticationException: If token is invalid, expired, revoked, or family is compromised.
        """
        from sqlalchemy import select, update

        from backend.models.entities.user import User

        incoming_hash = hashlib.sha256(raw_refresh_token.encode("utf-8")).hexdigest()

        # Find the session
        stmt = select(UserSession).where(UserSession.refresh_token_hash == incoming_hash)
        result = await self.session.execute(stmt)
        session_entry = result.scalar_one_or_none()

        if not session_entry:
            logger.warning("Attempted to rotate non-existent refresh token")
            raise AuthenticationException("Invalid session")

        # Reuse Detection
        if session_entry.is_revoked or session_entry.rotated_at:
            logger.critical("Compromised token family detected (Reuse)", family_id=session_entry.family_id, user_id=str(session_entry.user_id))
            # Revoke entire family
            revoke_stmt = (
                update(UserSession)
                .where(UserSession.family_id == session_entry.family_id)
                .values(is_revoked=True)
            )
            await self.session.execute(revoke_stmt)
            await self.session.commit()
            raise AuthenticationException("Session terminated for security reasons. Please log in again.")

        if session_entry.expires_at < datetime.datetime.now(datetime.UTC):
            logger.info("Attempted to rotate expired refresh token", family_id=session_entry.family_id)
            raise AuthenticationException("Session expired")

        # Fetch user
        user = await self.session.get(User, session_entry.user_id)
        if not user or not user.is_active:
            raise AuthenticationException("Account disabled")

        # Generate new tokens
        access_token, new_raw_refresh, _ = await self.jwt_service.issue_tokens(user)
        # Note: We keep the same family_id from the original session
        new_hash = hashlib.sha256(new_raw_refresh.encode("utf-8")).hexdigest()

        # Update current session entry
        session_entry.rotated_at = datetime.datetime.now(datetime.UTC)
        session_entry.is_revoked = True # The old token itself is now revoked

        # Create new session entry for the rotated token
        new_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7)
        new_session_entry = UserSession(
            user_id=user.id,
            refresh_token_hash=new_hash,
            family_id=session_entry.family_id,
            expires_at=new_expires_at,
            user_agent=user_agent or session_entry.user_agent,
            ip_address=ip_address or session_entry.ip_address,
            device=device or session_entry.device,
            last_used_at=datetime.datetime.now(datetime.UTC)
        )

        self.session.add(new_session_entry)
        await self.session.commit()

        logger.info("Refresh token rotated successfully", user_id=str(user.id), family_id=session_entry.family_id)
        return access_token, new_raw_refresh

    async def handle_oidc_login(
        self,
        email: str,
        provider: str,
        provider_user_id: str,
        metadata: dict,
        user_agent: str | None = None,
        ip_address: str | None = None,
        device: str | None = None
    ) -> tuple[str, str]:
        """Handles OIDC callback authentication.

        If user exists, links provider. If not, creates user and links provider.
        Then issues tokens.
        """
        from sqlalchemy import select

        from backend.models.entities.sso_identity import SSOIdentity
        from backend.models.entities.user import User

        email_normalized = email.lower().strip()
        user = await self.user_repo.get_by_email(email_normalized)

        if not user:
            # Create user (without password since it's SSO)
            user = User(
                email=email_normalized,
                is_verified=True, # Trust OIDC email verification
                verified_at=datetime.datetime.now(datetime.UTC),
                role="viewer",
                is_active=True
            )
            self.session.add(user)
            await self.session.flush() # get user.id

        elif not user.is_active:
            raise AuthenticationException("Account is disabled. Please contact support.")

        # Check if SSOIdentity already exists
        stmt = select(SSOIdentity).where(SSOIdentity.provider == provider, SSOIdentity.provider_user_id == provider_user_id)
        result = await self.session.execute(stmt)
        identity = result.scalar_one_or_none()

        if not identity:
            identity = SSOIdentity(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                sso_metadata=metadata,
                linked_at=datetime.datetime.now(datetime.UTC)
            )
            self.session.add(identity)

        user.last_login_at = datetime.datetime.now(datetime.UTC)

        # Issue tokens
        access_token, raw_refresh_token, family_id = await self.jwt_service.issue_tokens(user)
        refresh_token_hash = hashlib.sha256(raw_refresh_token.encode("utf-8")).hexdigest()

        expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7)
        session_entry = UserSession(
            user_id=user.id,
            refresh_token_hash=refresh_token_hash,
            family_id=family_id,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
            device=device,
            last_used_at=datetime.datetime.now(datetime.UTC)
        )
        self.session.add(session_entry)
        await self.session.commit()

        logger.info("OIDC login successful", user_id=str(user.id), provider=provider)
        return access_token, raw_refresh_token
