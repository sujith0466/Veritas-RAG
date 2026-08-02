"""Email Provider Abstractions."""

from abc import ABC, abstractmethod

from pydantic import EmailStr
import structlog

logger = structlog.get_logger(__name__)

class EmailProvider(ABC):
    """Base interface for all email dispatchers."""

    @abstractmethod
    async def send_verification_email(self, to_email: EmailStr, raw_token: str) -> bool:
        """Send a verification email with the given token."""
        pass

    @abstractmethod
    async def send_password_reset_email(self, to_email: EmailStr, raw_token: str) -> bool:
        """Send a password reset email with the given token."""
        pass

class SMTPEmailProvider(EmailProvider):
    """SMTP-based email provider (mock implementation for architecture readiness)."""

    async def send_verification_email(self, to_email: EmailStr, raw_token: str) -> bool:
        """Sends email via SMTP."""
        # TODO: Implement actual aiosmtplib logic when configured.
        logger.info(f"MOCK EMAIL DISPATCH: Sent verification token to {to_email}. Token: {raw_token}")
        return True

    async def send_password_reset_email(self, to_email: EmailStr, raw_token: str) -> bool:
        """Sends password reset email via SMTP."""
        logger.info(f"MOCK EMAIL DISPATCH: Sent password reset token to {to_email}. Token: {raw_token}")
        return True

def get_email_provider() -> EmailProvider:
    """Factory to retrieve the active email provider."""
    # In a real app, this reads from environment configs to return SMTP, SendGrid, etc.
    return SMTPEmailProvider()
