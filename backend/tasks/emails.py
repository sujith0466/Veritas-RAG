"""Celery tasks for email delivery."""

from celery import shared_task
from celery.utils.log import get_task_logger

import asyncio
import uuid
import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from email.message import EmailMessage

from backend.core.config import get_settings
from backend.database.engine import get_session_factory
from backend.services.email.provider import SMTPEmailProvider, EmailConfigurationError
from backend.models.entities.notification_delivery_log import NotificationDeliveryLog

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=60, # 1 minute base backoff
    queue="default"
)
def send_email_task(self, tenant_id_str: str | None, subject: str, to_addresses: list[str], html_content: str, text_content: str = ""):
    """Delivers email asynchronously and records delivery state in DB with deterministic single retry."""
    tenant_id = uuid.UUID(tenant_id_str) if tenant_id_str else None

    # Synchronously run the async logic with isolated loop per task
    return asyncio.run(_async_send_email(self, tenant_id, subject, to_addresses, html_content, text_content))


def _build_mime_message(from_addr: str, to_addrs: list[str] | str, subject: str, html_content: str, text_content: str = "") -> EmailMessage:
    """Constructs RFC 2822 compliant multipart/alternative MIME message."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs) if isinstance(to_addrs, list) else to_addrs
    msg.set_content(text_content or "")
    if html_content:
        msg.add_alternative(html_content, subtype="html")
    return msg


async def _async_send_email(task, tenant_id: uuid.UUID | None, subject: str, to_addresses: list[str], html_content: str, text_content: str):
    logger.info(f"Attempting email delivery to {to_addresses} for tenant {tenant_id}")

    # Pre-record pending state
    async with get_session_factory()() as session:
        log = NotificationDeliveryLog(
            tenant_id=tenant_id,
            type="EMAIL",
            target=", ".join(to_addresses),
            payload_snapshot={"subject": subject},
            status="PENDING",
            attempt_count=task.request.retries + 1,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)

    settings = get_settings()
    from_addr = settings.smtp.from_email or "noreply@raguard.ai"
    msg = _build_mime_message(from_addr, to_addresses, subject, html_content, text_content)

    provider = SMTPEmailProvider()
    transient_exc: Exception | None = None
    countdown: int = 60 * (2 ** task.request.retries)

    try:
        await provider.send_message(msg)
        status = "SUCCESS"
        error_msg = None
    except EmailConfigurationError as ce:
        status = "FAILED_PERMANENT"
        error_msg = str(ce)
        logger.error(f"Permanent email configuration failure for {to_addresses}: {ce}")
    except Exception as te:
        status = "FAILED_TRANSIENT"
        error_msg = str(te)
        transient_exc = te
        logger.warning(f"Transient email failure for {to_addresses} (attempt {task.request.retries + 1}): {te}")

    # Update delivery log
    async with get_session_factory()() as session:
        log_obj = await session.get(NotificationDeliveryLog, log.id)
        if log_obj:
            log_obj.status = status
            log_obj.error_message = error_msg
            if status == "FAILED_TRANSIENT":
                log_obj.next_retry_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=countdown)
            await session.commit()

    if status == "FAILED_TRANSIENT" and transient_exc:
        raise task.retry(exc=transient_exc, countdown=countdown, max_retries=5)
