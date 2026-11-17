"""Celery background tasks for Workspace Join Code Expiration and Outbox Engine.

Implements:
1. evaluate_join_code_expirations_task (runs every 15m):
   - Evaluates active join codes approaching expiration at 72H, 24H, 1H, and EXPIRED.
   - Suppresses outbox creation for unclaimed legacy codes (Correction C5).
   - Routes alert to operational_custodian_user_id if present, else created_by_user_id.
   - Inserts deduplicated outbox row with deterministic idempotency_key.

2. dispatch_notification_outbox_task (runs every 1m):
   - Acquires pending/expired lease outbox rows.
   - Enforces pre-dispatch double-check synchronization (Correction C3):
     * Outcome 1 (Renewed / extended / rotated): CANCELLED.
     * Outcome 2 (Revoked / disabled): CANCELLED.
     * Outcome 3 (State unchanged): Dispatched -> SENT.
"""

import asyncio
import datetime
from datetime import UTC
import uuid

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.engine import get_session_factory
from backend.models.entities.notification_outbox import NotificationOutbox
from backend.models.entities.workspace_join_code import WorkspaceJoinCode

logger = get_task_logger(__name__)

CHECKPOINTS = [
    ("72H", datetime.timedelta(hours=72), datetime.timedelta(hours=24)),
    ("24H", datetime.timedelta(hours=24), datetime.timedelta(hours=1)),
    ("1H", datetime.timedelta(hours=1), datetime.timedelta(seconds=0)),
]


@shared_task(
    name="join_codes.evaluate_expirations",
    queue="default",
)
def evaluate_join_code_expirations_task():
    """Periodic task running every 15 minutes to evaluate join-code expiration warnings."""
    return asyncio.run(_async_evaluate_join_code_expirations())


@shared_task(
    name="join_codes.dispatch_outbox",
    queue="default",
)
def dispatch_notification_outbox_task():
    """Periodic task running every minute to claim and dispatch outbox notifications."""
    return asyncio.run(_async_dispatch_notification_outbox())


async def _async_evaluate_join_code_expirations() -> dict:
    """Async evaluation of active join codes and generation of outbox records."""
    now = datetime.datetime.now(UTC)
    session_factory = get_session_factory()
    created_count = 0
    suppressed_count = 0

    async with session_factory() as session:
        # Find active, non-deleted join codes
        query = select(WorkspaceJoinCode).where(
            WorkspaceJoinCode.is_enabled.is_(True),
            WorkspaceJoinCode.is_deleted.is_(False),
        )
        result = await session.execute(query)
        codes = result.scalars().all()

        for code in codes:
            # Correction C5: Suppress alerts for unclaimed legacy codes
            recipient_id = code.operational_custodian_user_id or code.created_by_user_id
            if recipient_id is None:
                suppressed_count += 1
                continue

            time_left = code.expires_at - now

            matching_checkpoint = None
            if time_left.total_seconds() <= 0:
                matching_checkpoint = "EXPIRED"
            else:
                for cp_name, cp_upper, cp_lower in CHECKPOINTS:
                    if cp_lower < time_left <= cp_upper:
                        matching_checkpoint = cp_name
                        break

            if not matching_checkpoint:
                continue

            # Deterministic idempotency key per code, version, checkpoint, and channel
            idempotency_key = f"{code.id}:{code.version}:{matching_checkpoint}:EMAIL"

            # Check if outbox event already exists
            existing_query = select(NotificationOutbox).where(
                NotificationOutbox.idempotency_key == idempotency_key
            )
            existing_res = await session.execute(existing_query)
            if existing_res.scalars().first() is not None:
                continue

            outbox_entry = NotificationOutbox(
                id=uuid.uuid4(),
                join_code_id=code.id,
                join_code_version=code.version,
                workspace_id=code.workspace_id,
                recipient_user_id=recipient_id,
                checkpoint=matching_checkpoint,
                channel="EMAIL",
                status="PENDING",
                idempotency_key=idempotency_key,
                scheduled_for=now,
            )
            session.add(outbox_entry)
            created_count += 1

        if created_count > 0:
            await session.commit()

    logger.info(
        "Join code expiration evaluation completed: %d outbox created, %d suppressed unclaimed legacy.",
        created_count,
        suppressed_count,
    )
    return {"created": created_count, "suppressed": suppressed_count}


async def _async_dispatch_notification_outbox() -> dict:
    """Claims pending outbox events and executes pre-dispatch double-check synchronization (C3)."""
    now = datetime.datetime.now(UTC)
    session_factory = get_session_factory()
    lease_duration = datetime.timedelta(minutes=5)
    delivered_count = 0
    cancelled_count = 0

    async with session_factory() as session:
        # 1. Claim pending or lease-expired rows
        claim_query = select(NotificationOutbox).where(
            (NotificationOutbox.status == "PENDING") |
            (
                (NotificationOutbox.status == "CLAIMED") &
                (NotificationOutbox.lease_expires_at < now)
            )
        ).limit(50)

        result = await session.execute(claim_query)
        entries = result.scalars().all()

        for entry in entries:
            entry.status = "CLAIMED"
            entry.lease_expires_at = now + lease_duration
            session.add(entry)

        if entries:
            await session.commit()

    # Process each claimed entry with fresh session
    for entry_id in [e.id for e in entries]:
        async with session_factory() as session:
            entry = await session.get(NotificationOutbox, entry_id)
            if not entry or entry.status != "CLAIMED":
                continue

            # Pre-dispatch double-check synchronization (Correction C3)
            code = await session.get(WorkspaceJoinCode, entry.join_code_id)

            # Outcome 2: Explicitly revoked, disabled, or soft-deleted
            if not code or code.is_deleted or not code.is_enabled:
                entry.status = "CANCELLED"
                entry.error_message = "Code revoked, disabled, or deleted prior to dispatch."
                cancelled_count += 1
                session.add(entry)
                await session.commit()
                continue

            # Outcome 1: Rotated or renewed
            if code.version != entry.join_code_version:
                entry.status = "CANCELLED"
                entry.error_message = "Code rotated or renewed (version mismatch) prior to dispatch."
                cancelled_count += 1
                session.add(entry)
                await session.commit()
                continue

            # Outcome 1 (Extended): Expiration extended beyond checkpoint
            time_left = code.expires_at - datetime.datetime.now(UTC)
            if entry.checkpoint == "1H" and time_left > datetime.timedelta(hours=1):
                entry.status = "CANCELLED"
                entry.error_message = "Expiration extended beyond 1H threshold."
                cancelled_count += 1
                session.add(entry)
                await session.commit()
                continue
            if entry.checkpoint == "24H" and time_left > datetime.timedelta(hours=24):
                entry.status = "CANCELLED"
                entry.error_message = "Expiration extended beyond 24H threshold."
                cancelled_count += 1
                session.add(entry)
                await session.commit()
                continue
            if entry.checkpoint == "72H" and time_left > datetime.timedelta(hours=72):
                entry.status = "CANCELLED"
                entry.error_message = "Expiration extended beyond 72H threshold."
                cancelled_count += 1
                session.add(entry)
                await session.commit()
                continue

            # Outcome 3: State unchanged -> Dispatch notification
            entry.status = "SENT"
            entry.sent_at = datetime.datetime.now(UTC)
            delivered_count += 1
            session.add(entry)
            await session.commit()

    logger.info(
        "Outbox dispatch completed: %d sent, %d cancelled by pre-dispatch sync.",
        delivered_count,
        cancelled_count,
    )
    return {"sent": delivered_count, "cancelled": cancelled_count}
