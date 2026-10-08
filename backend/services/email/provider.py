"""Email Provider Abstractions."""

from abc import ABC, abstractmethod
import asyncio
import datetime
from email.message import EmailMessage
import os
import tempfile

from pydantic import EmailStr
import structlog
import aiosmtplib

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)

class EmailConfigurationError(RuntimeError):
    """Raised when email settings (SMTP or FRONTEND_URL) are unconfigured or invalid."""
    pass


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

    @abstractmethod
    async def send_otp_email(self, to_email: EmailStr, raw_otp: str) -> bool:
        """Send a password recovery 6-digit OTP verification email."""
        pass

    @abstractmethod
    async def send_security_code_email(self, to_email: EmailStr, raw_code: str) -> bool:
        """Send an authenticated password change 6-digit security code email."""
        pass

    @abstractmethod
    async def send_password_changed_notification_email(
        self,
        to_email: EmailStr,
        event_time: datetime.datetime | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> bool:
        """Send a security advisory notification email confirming that the password has been changed."""
        pass


class SMTPEmailProvider(EmailProvider):
    """SMTP-based email provider using aiosmtplib."""

    def __init__(self) -> None:
        self.settings = get_settings().smtp
        if not self.settings.is_configured:
            logger.warning("SMTP is not fully configured. Emails will fail if dispatched.")

    async def send_message(self, message: EmailMessage) -> bool:
        """Dispatches an email message using real aiosmtplib. Fails closed if SMTP is unconfigured."""
        if not self.settings.is_configured:
            logger.error("SMTP provider invoked but SMTP is not configured in settings")
            raise EmailConfigurationError("SMTP settings are not configured. Cannot dispatch email.")

        password = self.settings.password.get_secret_value() if self.settings.password else None
        username = self.settings.user or None
        use_tls = (self.settings.tls_mode.lower() == "tls")
        start_tls = (self.settings.tls_mode.lower() == "starttls")

        await aiosmtplib.send(
            message,
            hostname=self.settings.host,
            port=self.settings.port,
            username=username,
            password=password,
            use_tls=use_tls,
            start_tls=start_tls,
            timeout=self.settings.timeout or 15.0,
        )
        return True

    async def _send_email(self, to_email: EmailStr, subject: str, body: str, html_body: str | None = None) -> bool:
        """Validates configuration and enqueues Celery task. Fails closed if SMTP unconfigured."""
        if not self.settings.is_configured:
            logger.error("Attempted to enqueue email with unconfigured SMTP", recipient=to_email)
            raise EmailConfigurationError("SMTP settings are not configured. Cannot enqueue email.")

        from backend.tasks.emails import send_email_task

        try:
            logger.info("Enqueueing email task", recipient=to_email, subject=subject)
            # Enqueue the Celery task
            send_email_task.delay(
                tenant_id_str=None, # Extracted from context in a real multi-tenant app, or None for Auth
                subject=subject,
                to_addresses=[to_email],
                html_content=html_body or body,
                text_content=body
            )
            return True
        except Exception as e:
            logger.error("Failed to enqueue email task", error=str(e), exc_info=True)
            raise

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

    async def send_otp_email(self, to_email: EmailStr, raw_otp: str) -> bool:
        """Sends a 6-digit password recovery verification code via SMTP."""
        subject = "Your Veritas-RAG Verification Code"
        text_body = (
            f"Hello,\n\n"
            f"We received a request to reset your Veritas-RAG password.\n"
            f"Your 6-digit verification code is:\n\n"
            f"[ {raw_otp} ]\n\n"
            f"This code will expire in 10 minutes.\n\n"
            f"If you did not request a password reset, please ignore this email. "
            f"Your password will remain unchanged.\n\n"
            f"The Veritas-RAG Security Team"
        )
        html_body = (
            f"<div style=\"font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;\">"
            f"<h2 style=\"color: #0f172a; margin-top: 0;\">Veritas-RAG Password Recovery</h2>"
            f"<p style=\"color: #475569; font-size: 14px;\">We received a request to reset your Veritas-RAG account password. Use the verification code below to proceed:</p>"
            f"<div style=\"text-align: center; margin: 28px 0; padding: 16px; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px;\">"
            f"<span style=\"font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; font-size: 32px; font-weight: 700; letter-spacing: 6px; color: #0284c7;\">{raw_otp}</span>"
            f"</div>"
            f"<p style=\"color: #64748b; font-size: 13px;\">This code is valid for <strong>10 minutes</strong> and can only be used once.</p>"
            f"<p style=\"color: #94a3b8; font-size: 12px; margin-top: 24px; border-top: 1px solid #f1f5f9; padding-top: 12px;\">If you did not request a password reset, please ignore this email. Your password will remain unchanged.</p>"
            f"</div>"
        )
        return await self._send_email(to_email, subject, text_body, html_body=html_body)

    async def send_security_code_email(self, to_email: EmailStr, raw_code: str) -> bool:
        """Sends a 6-digit password change security code via SMTP."""
        subject = "Your Veritas-RAG Security Code"
        text_body = (
            f"Hello,\n\n"
            f"We received a request to change your Veritas-RAG account password from Security Settings.\n"
            f"Your 6-digit security verification code is:\n\n"
            f"[ {raw_code} ]\n\n"
            f"This code will expire in 10 minutes.\n\n"
            f"If you did not initiate this change, your account may be compromised. "
            f"Please contact your workspace administrator immediately.\n\n"
            f"The Veritas-RAG Security Team"
        )
        html_body = (
            f"<div style=\"font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;\">"
            f"<h2 style=\"color: #0f172a; margin-top: 0;\">Veritas-RAG Password Change</h2>"
            f"<p style=\"color: #475569; font-size: 14px;\">We received a request to change your Veritas-RAG account password. Use the security verification code below to authorize this change:</p>"
            f"<div style=\"text-align: center; margin: 28px 0; padding: 16px; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px;\">"
            f"<span style=\"font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; font-size: 32px; font-weight: 700; letter-spacing: 6px; color: #0284c7;\">{raw_code}</span>"
            f"</div>"
            f"<p style=\"color: #64748b; font-size: 13px;\">This code is valid for <strong>10 minutes</strong> and can only be used once.</p>"
            f"<p style=\"color: #ef4444; font-size: 12px; margin-top: 24px; border-top: 1px solid #f1f5f9; padding-top: 12px;\">If you did not initiate this change, please contact your workspace administrator immediately.</p>"
            f"</div>"
        )
        return await self._send_email(to_email, subject, text_body, html_body=html_body)

    async def send_password_changed_notification_email(
        self,
        to_email: EmailStr,
        event_time: datetime.datetime | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> bool:
        """Sends a security advisory notification email confirming password change via SMTP."""
        now = event_time or datetime.datetime.now(datetime.UTC)
        formatted_time = now.strftime("%Y-%m-%d %H:%M:%S UTC")

        context_lines = []
        context_html_items = []
        if ip_address:
            context_lines.append(f"IP Address: {ip_address}")
            context_html_items.append(f"<li><strong>IP Address:</strong> {ip_address}</li>")
        if user_agent:
            context_lines.append(f"Device / Browser: {user_agent}")
            context_html_items.append(f"<li><strong>Device / Browser:</strong> {user_agent}</li>")

        context_text = ""
        if context_lines:
            context_text = "Security details for this event:\n" + "\n".join(context_lines) + "\n\n"

        context_html = ""
        if context_html_items:
            context_html = (
                '<div style="margin: 16px 0; padding: 12px 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;">'
                '<p style="color: #475569; font-size: 13px; font-weight: 600; margin: 0 0 8px 0;">Security details:</p>'
                '<ul style="color: #64748b; font-size: 13px; margin: 0; padding-left: 20px;">'
                + "".join(context_html_items)
                + '</ul></div>'
            )

        subject = "Security Alert: Your Veritas-RAG Password Has Been Changed"
        text_body = (
            f"Hello,\n\n"
            f"This is a security alert to confirm that the password for your Veritas-RAG account ({to_email}) "
            f"was successfully changed on {formatted_time}.\n\n"
            f"{context_text}"
            f"If you made this change, no further action is required. Your account credentials have been updated securely.\n\n"
            f"IMPORTANT: If you did NOT change your password, your account may be compromised. "
            f"Please contact your workspace administrator immediately or initiate an account recovery.\n\n"
            f"The Veritas-RAG Security Team"
        )
        html_body = (
            f'<div style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">'
            f'<h2 style="color: #0f172a; margin-top: 0;">Security Alert: Password Changed</h2>'
            f'<p style="color: #475569; font-size: 14px; line-height: 1.5;">This email confirms that the password for your Veritas-RAG account (<strong>{to_email}</strong>) was successfully changed on <strong>{formatted_time}</strong>.</p>'
            f'{context_html}'
            f'<div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 12px 16px; margin: 20px 0;">'
            f'<p style="color: #166534; font-size: 13px; margin: 0; font-weight: 500;">If you made this change, no further action is required.</p>'
            f'</div>'
            f'<div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 12px 16px; margin: 20px 0;">'
            f'<p style="color: #991b1b; font-size: 13px; margin: 0; font-weight: 600;">If you did NOT change your password:</p>'
            f'<p style="color: #b91c1c; font-size: 12px; margin: 4px 0 0 0; line-height: 1.4;">Your account may be compromised. Please contact your workspace administrator immediately or initiate an account recovery.</p>'
            f'</div>'
            f'<p style="color: #94a3b8; font-size: 12px; margin-top: 24px; border-top: 1px solid #f1f5f9; padding-top: 12px;">This is an automated security notification from Veritas-RAG. Please do not reply to this email.</p>'
            f'</div>'
        )
        return await self._send_email(to_email, subject, text_body, html_body=html_body)

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
        """Sends workspace invitation email via SMTP with validated absolute acceptance link."""
        frontend_url = get_settings().frontend_url
        if not frontend_url or not frontend_url.startswith(("http://", "https://")):
            logger.error("Invalid or missing FRONTEND_URL in settings", frontend_url=frontend_url)
            raise EmailConfigurationError("FRONTEND_URL is not configured or invalid. Cannot generate invitation link.")

        subject = f"You have been invited to join {workspace_name}"
        inviter_text = f"{inviter_name} has" if inviter_name else "You have been"

        body = f"{inviter_text} invited to join the workspace '{workspace_name}' as a {role}.\n\n"
        if custom_message:
            body += f"Message: {custom_message}\n\n"

        base_url = frontend_url.rstrip("/")
        acceptance_link = f"{base_url}/invitations/accept?token={raw_token}"
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
        self.mock_file = os.path.join(tempfile.gettempdir(), "mock_emails.json")

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

    async def send_otp_email(self, to_email: EmailStr, raw_otp: str) -> bool:
        return self._record_email("password_recovery_otp", to_email, raw_otp)

    async def send_security_code_email(self, to_email: EmailStr, raw_code: str) -> bool:
        return self._record_email("change_password_security_code", to_email, raw_code)

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

    async def send_password_changed_notification_email(
        self,
        to_email: EmailStr,
        event_time: datetime.datetime | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> bool:
        now = event_time or datetime.datetime.now(datetime.UTC)
        formatted_time = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        details = {
            "event_time": formatted_time,
            "subject": "Security Alert: Your Veritas-RAG Password Has Been Changed",
        }
        if ip_address:
            details["ip_address"] = ip_address
        if user_agent:
            details["user_agent"] = user_agent
        return self._record_email("password_changed_notification", to_email, "", details)


class ConsoleEmailProvider(EmailProvider):
    """Console/stdout-based email provider for local development."""

    def __init__(self) -> None:
        pass

    async def send_verification_email(self, to_email: EmailStr, raw_token: str) -> bool:
        logger.info("Console email: verification", to=to_email)
        return True

    async def send_password_reset_email(self, to_email: EmailStr, raw_token: str) -> bool:
        logger.info("Console email: password reset", to=to_email)
        return True

    async def send_otp_email(self, to_email: EmailStr, raw_otp: str) -> bool:
        logger.info("Console email: recovery OTP", to=to_email)
        return True

    async def send_security_code_email(self, to_email: EmailStr, raw_code: str) -> bool:
        logger.info("Console email: security code", to=to_email)
        return True

    async def send_password_changed_notification_email(
        self,
        to_email: EmailStr,
        event_time: datetime.datetime | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> bool:
        now = event_time or datetime.datetime.now(datetime.UTC)
        logger.info("Console email: password changed notification", to=to_email, event_time=str(now))
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
        logger.info("Console email: invitation", to=to_email, workspace=workspace_name, role=role)
        return True

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
