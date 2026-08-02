"""Email Verification Service."""

import datetime
import hashlib
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions.auth import AuthenticationException
from backend.repositories.implementations.user_repository import UserRepository


class EmailVerificationService:
    """Handles email verification token generation, hashing, and validation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def generate_and_store_token(self, email: str) -> str:
        """Generates a raw token, stores its hash, and returns the raw token."""
        user = await self.user_repo.get_by_email(email)
        if not user:
            # We return a dummy token to prevent enumeration during resend flows.
            return secrets.token_urlsafe(32)

        if user.is_verified:
            # Already verified
            return ""

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        user.verification_token_hash = token_hash
        user.verification_token_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=24)

        await self.session.commit()
        return raw_token

    async def verify_token(self, email: str, raw_token: str) -> bool:
        """Validates the raw token against the stored hash and marks user verified."""
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise AuthenticationException("Invalid verification request")

        if user.is_verified:
            raise AuthenticationException("User is already verified")

        if not user.verification_token_hash or not user.verification_token_expires_at:
            raise AuthenticationException("No pending verification")

        if datetime.datetime.now(datetime.UTC) > user.verification_token_expires_at:
            raise AuthenticationException("Verification token has expired")

        provided_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        if secrets.compare_digest(provided_hash, user.verification_token_hash):
            # Success flow
            user.is_verified = True
            user.verified_at = datetime.datetime.now(datetime.UTC)
            user.verification_token_hash = None
            user.verification_token_expires_at = None
            await self.session.commit()
            return True

        raise AuthenticationException("Invalid verification token")
