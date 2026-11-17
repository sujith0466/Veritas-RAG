"""Celery background tasks for Workspace Ownership Transfers & Batch 2 Lifecycle.

Governed by Section 7 Batch 1 (REV5) and Batch 2 (V3.0).
Implements periodic sweep tasks with:
- Workspace-level FOR UPDATE SKIP LOCKED
- Isolated per-workspace transaction boundaries
- Fresh database clock per candidate workspace
- Idempotent state transitions and dual in-app notifications
- Path A: Unresponsive former owner timeout at Day 30 -> State 12
- Path B: Automatic ADMIN fallback at Day 30 -> State 11
- Scheduled role reminders dispatch on Days 14, 25, 29 (new OWNER only)
"""

import asyncio
from datetime import datetime
import uuid

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import distinct, func, select, update

from backend.database.engine import get_session_factory
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_former_owner_departure import FormerOwnerDepartureType
from backend.models.entities.workspace_member import (
    MemberStatus,
    WorkspaceMember,
    WorkspaceRole,
)
from backend.models.entities.workspace_ownership_transfer import (
    DecisionStatus,
    FormerOwnerChoice,
    ReminderStatus,
    ReminderType,
    TransferStatus,
    WorkspaceOwnershipRoleReminder,
    WorkspaceOwnershipTransfer,
)
from backend.services.workspace.former_owner_departure_service import (
    FormerOwnerDepartureService,
)
from backend.services.workspace_transfer_service import WorkspaceTransferService

logger = get_task_logger(__name__)


# ---------------------------------------------------------------------------
# Batch 1: Expired Nominations Sweep (7-day TTL)
# ---------------------------------------------------------------------------

@shared_task(
    name="backend.tasks.ownership_transfers.sweep_expired_ownership_transfers",
    queue="default",
)
def sweep_expired_ownership_transfers():
    """Periodic task running every 15 minutes to sweep and expire overdue transfers."""
    return asyncio.run(_async_sweep_expired_transfers())


async def _async_sweep_expired_transfers() -> dict:
    """Async evaluation of candidate workspaces and expiration processing."""
    session_factory = get_session_factory()
    service = WorkspaceTransferService()
    expired_count = 0
    skipped_count = 0
    error_count = 0

    async with session_factory() as session:
        # Candidate discovery using database clock
        now_res = await session.execute(select(func.clock_timestamp()))
        initial_now = now_res.scalar_one()

        cand_query = select(
            distinct(WorkspaceOwnershipTransfer.workspace_id)
        ).where(
            WorkspaceOwnershipTransfer.status == TransferStatus.PENDING.value,
            WorkspaceOwnershipTransfer.expires_at <= initial_now,
        ).limit(50)
        cand_res = await session.execute(cand_query)
        candidate_workspace_ids = list(cand_res.scalars().all())

    for ws_id in candidate_workspace_ids:
        async with session_factory() as session:
            try:
                # 1. Acquire L_W with SKIP LOCKED
                ws_query = select(Workspace).where(
                    Workspace.id == ws_id
                ).with_for_update(skip_locked=True)
                ws_res = await session.execute(ws_query)
                workspace = ws_res.scalar_one_or_none()

                if not workspace:
                    await session.rollback()
                    skipped_count += 1
                    continue

                # 2. Acquire L_TRANS under protected workspace lock
                trans_query = select(WorkspaceOwnershipTransfer).where(
                    WorkspaceOwnershipTransfer.workspace_id == ws_id,
                    WorkspaceOwnershipTransfer.status == TransferStatus.PENDING.value,
                ).with_for_update()
                trans_res = await session.execute(trans_query)
                pending_transfers = list(trans_res.scalars().all())

                # 3. Obtain fresh database clock under lock for this workspace
                ws_clock_res = await session.execute(select(func.clock_timestamp()))
                ws_now = ws_clock_res.scalar_one()

                # 4. Re-check PENDING status and expiration against fresh timestamp
                for transfer in pending_transfers:
                    if ws_now >= transfer.expires_at:
                        applied = await service._check_and_apply_expiration(
                            session, transfer, ws_now
                        )
                        if applied:
                            expired_count += 1

                await session.commit()
            except Exception as e:
                await session.rollback()
                error_count += 1
                logger.error(
                    "Failed to expire transfers for workspace",
                    extra={"workspace_id": str(ws_id), "error": str(e)},
                )

    return {
        "candidate_workspaces": len(candidate_workspace_ids),
        "expired_transfers": expired_count,
        "skipped_workspaces": skipped_count,
        "errors": error_count,
    }


# ---------------------------------------------------------------------------
# Batch 2: Path A Unresponsive Former Owner Timeout Sweep (Day 30 -> State 12)
# ---------------------------------------------------------------------------

@shared_task(
    name="backend.tasks.ownership_transfers.sweep_unresponsive_former_owners",
    queue="default",
)
def sweep_unresponsive_former_owners():
    """Periodic task running every 15 minutes to sweep and timeout unresponsive former owners."""
    return asyncio.run(_async_sweep_unresponsive_transfers())


async def _async_sweep_unresponsive_transfers() -> dict:
    """Async evaluation of transfers in State 5 past the 30-day deadline."""
    session_factory = get_session_factory()
    service = WorkspaceTransferService()
    timed_out_count = 0
    skipped_count = 0
    error_count = 0

    async with session_factory() as session:
        now_res = await session.execute(select(func.clock_timestamp()))
        initial_now = now_res.scalar_one()

        cand_query = select(
            distinct(WorkspaceOwnershipTransfer.workspace_id)
        ).where(
            WorkspaceOwnershipTransfer.status == TransferStatus.ACCEPTED.value,
            WorkspaceOwnershipTransfer.former_owner_choice == FormerOwnerChoice.PENDING.value,
            WorkspaceOwnershipTransfer.decision_deadline_at <= initial_now,
        ).limit(50)
        cand_res = await session.execute(cand_query)
        candidate_workspace_ids = list(cand_res.scalars().all())

    for ws_id in candidate_workspace_ids:
        async with session_factory() as session:
            try:
                # 1. Acquire L_W with SKIP LOCKED
                ws_query = select(Workspace).where(
                    Workspace.id == ws_id
                ).with_for_update(skip_locked=True)
                ws_res = await session.execute(ws_query)
                workspace = ws_res.scalar_one_or_none()

                if not workspace:
                    await session.rollback()
                    skipped_count += 1
                    continue

                # 2. Acquire L_TRANS
                trans_query = select(WorkspaceOwnershipTransfer).where(
                    WorkspaceOwnershipTransfer.workspace_id == ws_id,
                    WorkspaceOwnershipTransfer.status == TransferStatus.ACCEPTED.value,
                    WorkspaceOwnershipTransfer.former_owner_choice == FormerOwnerChoice.PENDING.value,
                ).with_for_update()
                trans_res = await session.execute(trans_query)
                candidates = list(trans_res.scalars().all())

                ws_clock_res = await session.execute(select(func.clock_timestamp()))
                ws_now = ws_clock_res.scalar_one()

                for transfer in candidates:
                    if transfer.decision_deadline_at and ws_now >= transfer.decision_deadline_at:
                        # 3. Lock former member
                        mem_res = await session.execute(
                            select(WorkspaceMember)
                            .where(
                                WorkspaceMember.workspace_id == ws_id,
                                WorkspaceMember.user_id == transfer.nominated_by_user_id,
                                WorkspaceMember.is_deleted == False,
                            )
                            .with_for_update()
                        )
                        former_member = mem_res.scalar_one_or_none()

                        # State 12: UNRESPONSIVE_TIMED_OUT (POD-SEC7-B2-01 Option A)
                        transfer.decision_status = DecisionStatus.TIMED_OUT.value
                        transfer.decided_at = ws_now

                        if former_member:
                            former_member.is_deleted = True
                            former_member.updated_at = ws_now

                        # Cancel pending reminders
                        await session.execute(
                            update(WorkspaceOwnershipRoleReminder)
                            .where(
                                WorkspaceOwnershipRoleReminder.transfer_id == transfer.id,
                                WorkspaceOwnershipRoleReminder.status == ReminderStatus.PENDING.value,
                            )
                            .values(status=ReminderStatus.CANCELLED.value)
                        )

                        # Record immutable departure history (WP 7.10)
                        await FormerOwnerDepartureService.record_departure(
                            session=session,
                            workspace_id=ws_id,
                            former_owner_id=transfer.nominated_by_user_id,
                            transfer_id=transfer.id,
                            departure_type=FormerOwnerDepartureType.TIMEOUT_AUTO_REMOVED,
                            confirmed_by_user_id=transfer.nominee_user_id,
                            former_role="OWNER",
                            retained_role=None,
                            departure_notes="Automatic 30-day timeout removal",
                            confirmed_at=ws_now,
                        )

                        # Dual in-app notifications
                        await service._record_in_app_notification(
                            session,
                            ws_id,
                            transfer.nominee_user_id,
                            "Former Owner Choice Expired",
                            f"The former owner of '{workspace.name}' did not choose STAY or LEAVE within 30 days and has been removed.",
                        )
                        await service._record_in_app_notification(
                            session,
                            ws_id,
                            transfer.nominated_by_user_id,
                            "Workspace Access Expired",
                            f"Your choice window to remain in '{workspace.name}' has expired after 30 days. You have been removed from the workspace.",
                        )
                        timed_out_count += 1

                await session.commit()
            except Exception as e:
                await session.rollback()
                error_count += 1
                logger.error(
                    "Failed to process unresponsive former owner timeouts for workspace",
                    extra={"workspace_id": str(ws_id), "error": str(e)},
                )

    return {
        "candidate_workspaces": len(candidate_workspace_ids),
        "timed_out_transfers": timed_out_count,
        "skipped_workspaces": skipped_count,
        "errors": error_count,
    }


# ---------------------------------------------------------------------------
# Batch 2: Path B Automatic ADMIN Fallback Sweep (Day 30 -> State 11)
# ---------------------------------------------------------------------------

@shared_task(
    name="backend.tasks.ownership_transfers.sweep_automatic_role_fallbacks",
    queue="default",
)
def sweep_automatic_role_fallbacks():
    """Periodic task running every 15 minutes to apply automatic ADMIN fallback for STAY transfers."""
    return asyncio.run(_async_sweep_automatic_fallbacks())


async def _async_sweep_automatic_fallbacks() -> dict:
    """Async evaluation of transfers in State 7 past the 30-day deadline."""
    session_factory = get_session_factory()
    service = WorkspaceTransferService()
    fallback_count = 0
    skipped_count = 0
    error_count = 0

    async with session_factory() as session:
        now_res = await session.execute(select(func.clock_timestamp()))
        initial_now = now_res.scalar_one()

        cand_query = select(
            distinct(WorkspaceOwnershipTransfer.workspace_id)
        ).where(
            WorkspaceOwnershipTransfer.status == TransferStatus.ACCEPTED.value,
            WorkspaceOwnershipTransfer.former_owner_choice == FormerOwnerChoice.STAY.value,
            WorkspaceOwnershipTransfer.decision_status == DecisionStatus.PENDING.value,
            WorkspaceOwnershipTransfer.decision_deadline_at <= initial_now,
        ).limit(50)
        cand_res = await session.execute(cand_query)
        candidate_workspace_ids = list(cand_res.scalars().all())

    for ws_id in candidate_workspace_ids:
        async with session_factory() as session:
            try:
                # 1. Acquire L_W with SKIP LOCKED
                ws_query = select(Workspace).where(
                    Workspace.id == ws_id
                ).with_for_update(skip_locked=True)
                ws_res = await session.execute(ws_query)
                workspace = ws_res.scalar_one_or_none()

                if not workspace:
                    await session.rollback()
                    skipped_count += 1
                    continue

                # 2. Acquire L_TRANS
                trans_query = select(WorkspaceOwnershipTransfer).where(
                    WorkspaceOwnershipTransfer.workspace_id == ws_id,
                    WorkspaceOwnershipTransfer.status == TransferStatus.ACCEPTED.value,
                    WorkspaceOwnershipTransfer.former_owner_choice == FormerOwnerChoice.STAY.value,
                    WorkspaceOwnershipTransfer.decision_status == DecisionStatus.PENDING.value,
                ).with_for_update()
                trans_res = await session.execute(trans_query)
                candidates = list(trans_res.scalars().all())

                ws_clock_res = await session.execute(select(func.clock_timestamp()))
                ws_now = ws_clock_res.scalar_one()

                for transfer in candidates:
                    if transfer.decision_deadline_at and ws_now >= transfer.decision_deadline_at:
                        # 3. Lock former member
                        mem_res = await session.execute(
                            select(WorkspaceMember)
                            .where(
                                WorkspaceMember.workspace_id == ws_id,
                                WorkspaceMember.user_id == transfer.nominated_by_user_id,
                                WorkspaceMember.is_deleted == False,
                            )
                            .with_for_update()
                        )
                        former_member = mem_res.scalar_one_or_none()

                        # State 11: AUTOMATIC_FALLBACK_ADMIN (Q7 / PO-D32-02)
                        transfer.decision_status = DecisionStatus.FALLBACK_ADMIN.value
                        transfer.decided_at = ws_now

                        if former_member:
                            former_member.role = WorkspaceRole.ADMIN.value
                            former_member.status = MemberStatus.ACTIVE.value
                            former_member.is_former_owner = True
                            former_member.updated_at = ws_now

                        # Cancel pending reminders
                        await session.execute(
                            update(WorkspaceOwnershipRoleReminder)
                            .where(
                                WorkspaceOwnershipRoleReminder.transfer_id == transfer.id,
                                WorkspaceOwnershipRoleReminder.status == ReminderStatus.PENDING.value,
                            )
                            .values(status=ReminderStatus.CANCELLED.value)
                        )

                        # Record immutable departure history (WP 7.10)
                        await FormerOwnerDepartureService.record_departure(
                            session=session,
                            workspace_id=ws_id,
                            former_owner_id=transfer.nominated_by_user_id,
                            transfer_id=transfer.id,
                            departure_type=FormerOwnerDepartureType.NEW_OWNER_RETAINED,
                            confirmed_by_user_id=transfer.nominee_user_id,
                            former_role="OWNER",
                            retained_role=WorkspaceRole.ADMIN.value,
                            departure_notes="Automatic 30-day fallback to ADMIN",
                            confirmed_at=ws_now,
                        )

                        # Dual in-app notifications
                        await service._record_in_app_notification(
                            session,
                            ws_id,
                            transfer.nominated_by_user_id,
                            "Role Assigned: ADMIN (Automatic Fallback)",
                            f"You have been granted the ADMIN role in '{workspace.name}' because no role decision was made within 30 days.",
                        )
                        await service._record_in_app_notification(
                            session,
                            ws_id,
                            transfer.nominee_user_id,
                            "Former Owner Granted ADMIN (Automatic Fallback)",
                            f"The 30-day decision period expired for '{workspace.name}'. The former owner has been automatically assigned the ADMIN role.",
                        )
                        fallback_count += 1

                await session.commit()
            except Exception as e:
                await session.rollback()
                error_count += 1
                logger.error(
                    "Failed to process automatic fallbacks for workspace",
                    extra={"workspace_id": str(ws_id), "error": str(e)},
                )

    return {
        "candidate_workspaces": len(candidate_workspace_ids),
        "fallbacks_applied": fallback_count,
        "skipped_workspaces": skipped_count,
        "errors": error_count,
    }


# ---------------------------------------------------------------------------
# Batch 2: Role Decision Reminders Sweep (Days 14, 25, 29)
# ---------------------------------------------------------------------------

@shared_task(
    name="backend.tasks.ownership_transfers.sweep_role_decision_reminders",
    queue="default",
)
def sweep_role_decision_reminders():
    """Periodic task running hourly to dispatch role decision reminders to the new owner."""
    return asyncio.run(_async_sweep_role_reminders())


async def _async_sweep_role_reminders() -> dict:
    """Async evaluation and transactional outbox dispatch for due role reminders."""
    session_factory = get_session_factory()
    service = WorkspaceTransferService()
    sent_count = 0
    skipped_count = 0
    error_count = 0

    async with session_factory() as session:
        ws_clock_res = await session.execute(select(func.clock_timestamp()))
        now = ws_clock_res.scalar_one()

        # Query pending reminders due for dispatch with row lock
        rem_query = select(WorkspaceOwnershipRoleReminder).where(
            WorkspaceOwnershipRoleReminder.status == ReminderStatus.PENDING.value,
            WorkspaceOwnershipRoleReminder.scheduled_for <= now,
        ).with_for_update(skip_locked=True).limit(100)
        rem_res = await session.execute(rem_query)
        due_reminders = list(rem_res.scalars().all())

        for reminder in due_reminders:
            try:
                # Load parent transfer
                trans_res = await session.execute(
                    select(WorkspaceOwnershipTransfer).where(
                        WorkspaceOwnershipTransfer.id == reminder.transfer_id
                    )
                )
                transfer = trans_res.scalar_one_or_none()

                if not transfer:
                    reminder.status = ReminderStatus.CANCELLED.value
                    continue

                # Reminders are dispatched ONLY if transfer is in State 7 (STAY chosen, decision pending)
                if (
                    transfer.status == TransferStatus.ACCEPTED.value
                    and transfer.former_owner_choice == FormerOwnerChoice.STAY.value
                    and transfer.decision_status == DecisionStatus.PENDING.value
                ):
                    # Fetch workspace name for notification text
                    ws_res = await session.execute(
                        select(Workspace.name).where(Workspace.id == reminder.workspace_id)
                    )
                    ws_name = ws_res.scalar_one_or_none() or "your workspace"

                    days_left = 30
                    if reminder.reminder_type == ReminderType.DAY_14.value:
                        days_left = 16
                    elif reminder.reminder_type == ReminderType.DAY_25.value:
                        days_left = 5
                    elif reminder.reminder_type == ReminderType.DAY_29.value:
                        days_left = 1

                    await service._record_in_app_notification(
                        session,
                        reminder.workspace_id,
                        reminder.recipient_user_id,
                        f"Action Required: Decide Former Owner Role ({days_left} days left)",
                        f"Please decide a role (ADMIN, MEMBER, or REMOVE) for the former owner of '{ws_name}'. {days_left} calendar days remain before automatic ADMIN fallback.",
                    )

                    reminder.status = ReminderStatus.SENT.value
                    reminder.sent_at = now
                    sent_count += 1

                elif transfer.former_owner_choice == FormerOwnerChoice.PENDING.value:
                    # Former owner has not chosen STAY yet; skip this reminder
                    reminder.status = ReminderStatus.SKIPPED.value
                    skipped_count += 1
                else:
                    # Transfer resolved or former owner left; cancel reminder
                    reminder.status = ReminderStatus.CANCELLED.value

            except Exception as e:
                error_count += 1
                logger.error(
                    "Failed to process role reminder",
                    extra={"reminder_id": str(reminder.id), "error": str(e)},
                )

        await session.commit()

    return {
        "due_reminders": len(due_reminders),
        "sent": sent_count,
        "skipped": skipped_count,
        "errors": error_count,
    }
