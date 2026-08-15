"""Email Provider Abstractions."""

from abc import ABC, abstractmethod

import asyncio
from email.message import EmailMessage

from pydantic import EmailStr
import structlog
import aiosmtplib

from backend.core.config import get_settings

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
    """SMTP-based email provider using aiosmtplib."""

    def __init__(self) -> None:
        self.settings = get_settings().smtp
        if not self.settings.is_configured:
            logger.warning("SMTP is not fully configured. Emails will fail if dispatched.")

    async def _send_email(self, to_email: EmailStr, subject: str, body: str) -> bool:
        from backend.tasks.emails import send_email_task
        
        try:
            logger.info("Enqueueing email task", recipient=to_email, subject=subject)
            # Enqueue the Celery task
            send_email_task.delay(
                tenant_id_str=None, # Extracted from context in a real multi-tenant app, or None for Auth
                subject=subject,
                to_addresses=[to_email],
                html_content=body,
                text_content=body
            )
            return True
        except Exception as e:
            logger.error("Failed to enqueue email task", error=str(e), exc_info=True)
            return False

    async def send_verification_email(self, to_email: EmailStr, raw_token: str) -> bool:
        """Sends verification email via SMTP."""
        subject = "Verify your RAGuard account"
        body = f"Please verify your account by using this token:\n\n{raw_token}\n\nThank you."
        return await self._send_email(to_email, subject, body)

    async def send_password_reset_email(self, to_email: EmailStr, raw_token: str) -> bool:
        """Sends password reset email via SMTP."""
        subject = "Password Reset Request"
        body = f"You requested a password reset. Use this token:\n\n{raw_token}\n\nIf you did not request this, ignore this email."
        return await self._send_email(to_email, subject, body)

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
        subject = f"You have been invited to join {workspace_name}"
        inviter_text = f"{inviter_name} has" if inviter_name else "You have been"

        body = f"{inviter_text} invited to join the workspace '{workspace_name}' as a {role}.\n\n"
        if custom_message:
            body += f"Message: {custom_message}\n\n"

        acceptance_link = f"/api/v1/invitations/accept?token={raw_token}"
        body += f"To accept, use this link: {acceptance_link}\n\n"

        if expires_at:
            body += f"This invitation expires at {expires_at}."

        return await self._send_email(to_email, subject, body)
import json
import os
import time

class MockEmailProvider(EmailProvider):
    """File-based mock email provider for automated testing."""

    def __init__(self) -> None:
        self.mock_file = "C:\\Windows\\Temp\\mock_emails.json" if os.name == 'nt' else "/tmp/mock_emails.json"

    def _record_email(self, email_type: str, to_email: EmailStr, token: str, details: dict = None) -> bool:
        record = {
            "timestamp": time.time(),
            "type": email_type,
            "to": to_email,
            "token": token,
            "details": details or {}
        }

        try:
            records = []
            if os.path.exists(self.mock_file):
                with open(self.mock_file, 'r') as f:
                    try:
                        records = json.load(f)
                    except json.JSONDecodeError:
                        records = []

            records.append(record)

            with open(self.mock_file, 'w') as f:
                json.dump(records, f, indent=2)

            return True
        except Exception as e:
            logger.error(f"Failed to write mock email: {e}")
            return False

    async def send_verification_email(self, to_email: EmailStr, raw_token: str) -> bool:
        return self._record_email("verification", to_email, raw_token)

    async def send_password_reset_email(self, to_email: EmailStr, raw_token: str) -> bool:
        return self._record_email("password_reset", to_email, raw_token)

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
        details = {
            "workspace": workspace_name,
            "role": role,
            "inviter": inviter_name,
            "message": custom_message,
            "expires_at": expires_at
        }
        return self._record_email("invitation", to_email, raw_token, details)

def get_email_provider() -> EmailProvider:
    """Factory to retrieve the active email provider."""
    settings = get_settings()

    # In production, ALWAYS use SMTP provider regardless of configuration status.
    if settings.app.environment == "production":
        return SMTPEmailProvider()

    # In testing/development, if SMTP is not configured, fall back to mock.
    if settings.app.is_testing or settings.app.environment == "development":
        if not settings.smtp.is_configured:
            logger.warning("SMTP not configured in non-production environment. Using MockEmailProvider.")
            return MockEmailProvider()

    return SMTPEmailProvider()
