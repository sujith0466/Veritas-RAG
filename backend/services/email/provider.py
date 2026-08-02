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

    @abstractmethod
    async def send_invitation_email(
        self,
        to_email: EmailStr,
        raw_token: str,
        workspace_name: str,
        role: str,
        inviter_name: str | None = None,
        custom_message: str | None = None,
        expires_at: str | None = None,
    ) -> bool:
        """Send a workspace invitation email with versioned acceptance link."""
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

    async def send_invitation_email(
        self,
        to_email: EmailStr,
        raw_token: str,
        workspace_name: str,
        role: str,
        inviter_name: str | None = None,
        custom_message: str | None = None,
        expires_at: str | None = None,
    ) -> bool:
        """Sends workspace invitation email via SMTP."""
        acceptance_link = f"/api/v1/invitations/accept?token={raw_token}"
        logger.info(
            f"MOCK EMAIL DISPATCH: Sent workspace invitation to {to_email} for workspace '{workspace_name}' "
            f"as role '{role}'. Link: {acceptance_link}"
        )
        return True

def get_email_provider() -> EmailProvider:
    """Factory to retrieve the active email provider."""
    # In a real app, this reads from environment configs to return SMTP, SendGrid, etc.
    return SMTPEmailProvider()
