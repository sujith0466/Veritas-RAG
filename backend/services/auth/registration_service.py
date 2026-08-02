"""Registration Service.

Handles user registration logic, password hashing, and token generation.
"""

import hashlib
import secrets

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.registration import RegistrationRequest
from backend.core.security.password import get_password_hash
from backend.repositories.implementations.user_repository import UserRepository
from backend.services.email.provider import get_email_provider

logger = structlog.get_logger(__name__)


class RegistrationService:
    """Service handling user registration flows."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def register_user(self, request: RegistrationRequest) -> None:
        """Register a new user.
        
        Args:
            request: Registration request containing email, password, etc.
            
        Note:
            This method absorbs email enumeration attempts by returning silently
            if a user already exists.
        """
        email_normalized = request.email.lower().strip()

        # 1. Check existing user
        exists = await self.user_repo.exists_by_email(email_normalized)
        if exists:
            # Prevent email enumeration by failing silently and successfully.
            # In a real-world scenario, we might want to optionally send an email
            # to the user stating "An attempt to register this email was made."
            logger.info("Registration attempt for existing email. Swallowing to prevent enumeration.", email=email_normalized)
            return

        # 2. Hash password
        hashed_password = get_password_hash(request.password)

        # 3. Generate raw verification token
        raw_token = secrets.token_urlsafe(32)

        # 4. Store SHA-256 hash only
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        # 5. Create user
        try:
            user = await self.user_repo.create(
                email=email_normalized,
                hashed_password=hashed_password,
                is_verified=False,
                verification_token_hash=token_hash,
                profile_data={"full_name": request.full_name} if request.full_name else {},
            )
            await self.session.commit()
            logger.info("User registered successfully", user_id=str(user.id))

            # (F2.2): Send verification email
            email_provider = get_email_provider()
            await email_provider.send_verification_email(email_normalized, raw_token)

        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to register user", error=str(e))
            raise
