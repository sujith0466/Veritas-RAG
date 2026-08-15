"""Celery tasks for email delivery."""

from celery import shared_task
from celery.utils.log import get_task_logger

import asyncio
import uuid
import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.database.session import SessionLocal
from backend.services.email.provider import SMTPEmailProvider, EmailMessage
from backend.models.entities.notification_delivery_log import NotificationDeliveryLog

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=60, # 1 minute base backoff
    autoretry_for=(Exception,),
    queue="default"
)
def send_email_task(self, tenant_id_str: str | None, subject: str, to_addresses: list[str], html_content: str, text_content: str = ""):
    """Delivers email asynchronously and records delivery state in DB."""
    tenant_id = uuid.UUID(tenant_id_str) if tenant_id_str else None
    
    # Synchronously run the async logic
    asyncio.run(_async_send_email(self, tenant_id, subject, to_addresses, html_content, text_content))


async def _async_send_email(task, tenant_id: uuid.UUID | None, subject: str, to_addresses: list[str], html_content: str, text_content: str):
    logger.info(f"Attempting email delivery to {to_addresses} for tenant {tenant_id}")
    
    # Pre-record pending state
    async with SessionLocal() as session:
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

    provider = SMTPEmailProvider()
    msg = EmailMessage(
        subject=subject,
        to_addresses=to_addresses,
        html_content=html_content,
        text_content=text_content
    )
    
    try:
        await provider.send_message(msg)
        status = "SUCCESS"
        error_msg = None
    except Exception as e:
        status = "FAILED_TRANSIENT"
        error_msg = str(e)
        
    # Update delivery log
    async with SessionLocal() as session:
        log_obj = await session.get(NotificationDeliveryLog, log.id)
        if log_obj:
            log_obj.status = status
            log_obj.error_message = error_msg
            if status == "FAILED_TRANSIENT":
                log_obj.next_retry_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=60 * (2 ** task.request.retries))
            await session.commit()
            
    if status == "FAILED_TRANSIENT":
        raise Exception(error_msg)
