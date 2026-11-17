"""Integration tests for ownership transfers background sweep tasks - Section 7, Batch 2.

Governed by Section 7 Batch 2 (V3.0) and ratified Project Owner Decisions:
- WP 7.6: Automatic Fallback, Expiration & Reminder Engine (TC-7.6-01 through TC-7.6-10)
  * Path A: Day 30 Unresponsive Former Owner Timeout -> State 12 (UNRESPONSIVE_TIMED_OUT)
  * Path B: Day 30 Automatic ADMIN Fallback -> State 11 (AUTOMATIC_FALLBACK_ADMIN)
  * Role decision reminders for Days 14, 25, 29 (dispatched exclusively to new OWNER)
  * Late STAY skipping elapsed reminders
  * Concurrency and Transactional Outbox atomicity
"""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import uuid
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.models.entities.notification import Notification
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
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
from backend.services.workspace_transfer_service import WorkspaceTransferService
from backend.tasks.ownership_transfers import (
    _async_sweep_automatic_fallbacks,
    _async_sweep_role_reminders,
    _async_sweep_unresponsive_transfers,
)

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://t3b_test_admin:t3b_test_password_2026!@127.0.0.1:5433/raguard_t3b_test",
    ),
)


@pytest.fixture
def engine():
    eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    yield eng


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def db_session(session_factory) -> AsyncSession:
    async with session_factory() as session:
        yield session


async def create_user(session: AsyncSession, email_prefix: str) -> User:
    uid = uuid.uuid4()
    u = User(
        id=uid,
        email=f"{email_prefix}_{uid.hex[:8]}@example.com",
        hashed_password="hashed_pw_test",
        display_name=f"User {uid.hex[:6]}",
        is_active=True,
        is_verified=True,
    )
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


async def create_workspace(session: AsyncSession, name: str) -> Workspace:
    wid = uuid.uuid4()
    ws = Workspace(
        id=wid,
        name=f"{name}_{wid.hex[:6]}",
        slug=f"ws-{wid.hex[:8]}",
        public_id=f"ws-{wid.hex[:8]}",
        storage_prefix=f"storage-{wid.hex[:8]}",
        qdrant_namespace=f"qdrant-{wid.hex[:8]}",
        status=WorkspaceStatus.ACTIVE.value,
        is_deleted=False,
    )
    session.add(ws)
    await session.commit()
    await session.refresh(ws)
    return ws


async def create_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: WorkspaceRole,
    status: MemberStatus = MemberStatus.ACTIVE,
    is_former_owner: bool = False,
    is_deleted: bool = False,
) -> WorkspaceMember:
    mid = uuid.uuid4()
    mem = WorkspaceMember(
        id=mid,
        workspace_id=workspace_id,
        user_id=user_id,
        role=role.value,
        status=status.value,
        is_former_owner=is_former_owner,
        is_deleted=is_deleted,
    )
    session.add(mem)
    await session.commit()
    await session.refresh(mem)
    return mem


async def create_accepted_transfer(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    former_owner_id: uuid.UUID,
    new_owner_id: uuid.UUID,
    former_choice: str = FormerOwnerChoice.PENDING.value,
    decision_status: str = DecisionStatus.PENDING.value,
    deadline_offset: timedelta = timedelta(days=30),
) -> WorkspaceOwnershipTransfer:
    now_res = await session.execute(select(func.clock_timestamp()))
    db_now = now_res.scalar_one()

    tid = uuid.uuid4()
    tr = WorkspaceOwnershipTransfer(
        id=tid,
        workspace_id=workspace_id,
        nominated_by_user_id=former_owner_id,
        nominee_user_id=new_owner_id,
        status=TransferStatus.ACCEPTED.value,
        created_at=db_now - timedelta(days=1),
        expires_at=db_now + timedelta(days=6),
        responded_at=db_now,
        former_owner_choice=former_choice,
        decision_status=decision_status,
        decision_deadline_at=db_now + deadline_offset,
    )
    session.add(tr)
    await session.commit()
    await session.refresh(tr)
    return tr


async def create_role_reminder(
    session: AsyncSession,
    transfer_id: uuid.UUID,
    workspace_id: uuid.UUID,
    recipient_user_id: uuid.UUID,
    reminder_type: ReminderType,
    scheduled_offset: timedelta,
    status: ReminderStatus = ReminderStatus.PENDING,
) -> WorkspaceOwnershipRoleReminder:
    now_res = await session.execute(select(func.clock_timestamp()))
    db_now = now_res.scalar_one()

    rid = uuid.uuid4()
    rem = WorkspaceOwnershipRoleReminder(
        id=rid,
        transfer_id=transfer_id,
        workspace_id=workspace_id,
        recipient_user_id=recipient_user_id,
        reminder_type=reminder_type.value,
        scheduled_for=db_now + scheduled_offset,
        status=status.value,
    )
    session.add(rem)
    await session.commit()
    await session.refresh(rem)
    return rem


# ==============================================================================
# WORK PACKAGE 7.6: AUTOMATIC FALLBACK, EXPIRATION & REMINDER ENGINE
# ==============================================================================

@pytest.mark.asyncio
async def test_tc_7_6_01_path_b_automatic_fallback_after_30_days(session_factory, monkeypatch):
    """TC-7.6-01: Path B: Automatic Fallback executed after 30 days -> State 11 (AUTOMATIC_FALLBACK_ADMIN)."""
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        former_owner = await create_user(session, "fb_former")
        new_owner = await create_user(session, "fb_new")
        ws = await create_workspace(session, "fb_ws")

        await create_member(session, ws.id, new_owner.id, WorkspaceRole.OWNER)
        former_mem = await create_member(
            session,
            ws.id,
            former_owner.id,
            WorkspaceRole.ADMIN,
            MemberStatus.TRANSFER_PENDING,
        )

        # State 7 with deadline in the past (e.g. 1 hour ago)
        transfer = await create_accepted_transfer(
            session,
            ws.id,
            former_owner.id,
            new_owner.id,
            former_choice=FormerOwnerChoice.STAY.value,
            decision_status=DecisionStatus.PENDING.value,
            deadline_offset=-timedelta(hours=1),
        )

        # Pre-seed a pending reminder
        await create_role_reminder(
            session,
            transfer.id,
            ws.id,
            new_owner.id,
            ReminderType.DAY_29,
            scheduled_offset=-timedelta(hours=2),
        )

    # Execute Path B sweep
    res = await _async_sweep_automatic_fallbacks()
    assert res["fallbacks_applied"] >= 1
    assert res["errors"] == 0

    # Verify state transitions
    async with session_factory() as session:
        t_res = await session.execute(
            select(WorkspaceOwnershipTransfer).where(
                WorkspaceOwnershipTransfer.id == transfer.id
            )
        )
        t_updated = t_res.scalar_one()
        assert t_updated.decision_status == DecisionStatus.FALLBACK_ADMIN.value
        assert t_updated.decided_at is not None

        # Verify former owner membership: promoted to ADMIN, ACTIVE, is_former_owner=True
        m_res = await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.id == former_mem.id
            )
        )
        m_updated = m_res.scalar_one()
        assert m_updated.role == WorkspaceRole.ADMIN.value
        assert m_updated.status == MemberStatus.ACTIVE.value
        assert m_updated.is_former_owner is True
        assert m_updated.is_deleted is False

        # Verify reminders cancelled
        rem_res = await session.execute(
            select(WorkspaceOwnershipRoleReminder).where(
                WorkspaceOwnershipRoleReminder.transfer_id == transfer.id
            )
        )
        for rem in rem_res.scalars().all():
            assert rem.status == ReminderStatus.CANCELLED.value

        # Verify dual notifications
        notif_res = await session.execute(
            select(Notification).where(
                Notification.tenant_id == ws.id,
                Notification.user_id.in_([former_owner.id, new_owner.id]),
            )
        )
        notifs = list(notif_res.scalars().all())
        assert len(notifs) >= 2
        titles = [n.title for n in notifs]
        assert any("Automatic Fallback" in t for t in titles)


@pytest.mark.asyncio
async def test_tc_7_6_02_path_b_fallback_does_not_trigger_before_30_days(session_factory, monkeypatch):
    """TC-7.6-02: Path B: Fallback does not trigger before 30 days (e.g. Day 29)."""
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        former_owner = await create_user(session, "notyet_former")
        new_owner = await create_user(session, "notyet_new")
        ws = await create_workspace(session, "notyet_ws")

        await create_member(session, ws.id, new_owner.id, WorkspaceRole.OWNER)
        former_mem = await create_member(
            session,
            ws.id,
            former_owner.id,
            WorkspaceRole.ADMIN,
            MemberStatus.TRANSFER_PENDING,
        )

        # Deadline still in future (1 day left)
        transfer = await create_accepted_transfer(
            session,
            ws.id,
            former_owner.id,
            new_owner.id,
            former_choice=FormerOwnerChoice.STAY.value,
            decision_status=DecisionStatus.PENDING.value,
            deadline_offset=timedelta(days=1),
        )

    res = await _async_sweep_automatic_fallbacks()

    async with session_factory() as session:
        t_res = await session.execute(
            select(WorkspaceOwnershipTransfer).where(
                WorkspaceOwnershipTransfer.id == transfer.id
            )
        )
        t_check = t_res.scalar_one()
        assert t_check.decision_status == DecisionStatus.PENDING.value

        m_res = await session.execute(
            select(WorkspaceMember).where(WorkspaceMember.id == former_mem.id)
        )
        m_check = m_res.scalar_one()
        assert m_check.status == MemberStatus.TRANSFER_PENDING.value
        assert m_check.is_former_owner is False


@pytest.mark.asyncio
async def test_tc_7_6_03_04_05_reminders_dispatched_to_new_owner_only(session_factory, monkeypatch):
    """TC-7.6-03, 04, 05: Role reminders (Days 14, 25, 29) dispatched to new OWNER only."""
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        former_owner = await create_user(session, "rem_former")
        new_owner = await create_user(session, "rem_new")
        ws = await create_workspace(session, "rem_ws")

        await create_member(session, ws.id, new_owner.id, WorkspaceRole.OWNER)
        await create_member(
            session, ws.id, former_owner.id, WorkspaceRole.ADMIN, MemberStatus.TRANSFER_PENDING
        )

        transfer = await create_accepted_transfer(
            session,
            ws.id,
            former_owner.id,
            new_owner.id,
            former_choice=FormerOwnerChoice.STAY.value,
            decision_status=DecisionStatus.PENDING.value,
            deadline_offset=timedelta(days=16),
        )

        # Day 14 reminder due for dispatch
        rem14 = await create_role_reminder(
            session,
            transfer.id,
            ws.id,
            new_owner.id,
            ReminderType.DAY_14,
            scheduled_offset=-timedelta(hours=1),
        )

    # Execute reminder sweep
    res = await _async_sweep_role_reminders()
    assert res["sent"] >= 1
    assert res["errors"] == 0

    # Verify reminder status is SENT and only new owner received notification
    async with session_factory() as session:
        r_res = await session.execute(
            select(WorkspaceOwnershipRoleReminder).where(
                WorkspaceOwnershipRoleReminder.id == rem14.id
            )
        )
        r_updated = r_res.scalar_one()
        assert r_updated.status == ReminderStatus.SENT.value
        assert r_updated.sent_at is not None

        # Verify notification sent to new owner
        notif_owner = await session.execute(
            select(Notification).where(
                Notification.tenant_id == ws.id,
                Notification.user_id == new_owner.id,
            )
        )
        owner_notifs = list(notif_owner.scalars().all())
        assert len(owner_notifs) >= 1
        assert "Action Required: Decide Former Owner Role" in owner_notifs[0].title

        # Verify ZERO reminders sent to former owner
        notif_former = await session.execute(
            select(Notification).where(
                Notification.tenant_id == ws.id,
                Notification.user_id == former_owner.id,
            )
        )
        former_notifs = list(notif_former.scalars().all())
        assert len(former_notifs) == 0


@pytest.mark.asyncio
async def test_tc_7_6_06_reminders_skipped_if_choice_pending(session_factory, monkeypatch):
    """TC-7.6-06: Reminders skipped if former owner has not yet chosen STAY (State 5)."""
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        former_owner = await create_user(session, "skip_f")
        new_owner = await create_user(session, "skip_n")
        ws = await create_workspace(session, "skip_w")

        await create_member(session, ws.id, new_owner.id, WorkspaceRole.OWNER)
        await create_member(
            session, ws.id, former_owner.id, WorkspaceRole.ADMIN, MemberStatus.TRANSFER_PENDING
        )

        # Transfer in State 5 (former_owner_choice is PENDING)
        transfer = await create_accepted_transfer(
            session,
            ws.id,
            former_owner.id,
            new_owner.id,
            former_choice=FormerOwnerChoice.PENDING.value,
            decision_status=DecisionStatus.PENDING.value,
            deadline_offset=timedelta(days=16),
        )

        rem = await create_role_reminder(
            session,
            transfer.id,
            ws.id,
            new_owner.id,
            ReminderType.DAY_14,
            scheduled_offset=-timedelta(hours=1),
        )

    res = await _async_sweep_role_reminders()
    assert res["skipped"] >= 1

    async with session_factory() as session:
        r_res = await session.execute(
            select(WorkspaceOwnershipRoleReminder).where(
                WorkspaceOwnershipRoleReminder.id == rem.id
            )
        )
        r_check = r_res.scalar_one()
        assert r_check.status == ReminderStatus.SKIPPED.value


@pytest.mark.asyncio
async def test_tc_7_6_06b_late_stay_skips_elapsed_reminders(session_factory):
    """TC-7.6-06B: When former owner chooses STAY on Day 18, Day 14 reminder is SKIPPED and Days 25 & 29 remain active."""
    service = WorkspaceTransferService()

    async with session_factory() as session:
        now_res = await session.execute(select(func.clock_timestamp()))
        db_now = now_res.scalar_one()

        former_owner = await create_user(session, "late_f")
        new_owner = await create_user(session, "late_n")
        ws = await create_workspace(session, "late_w")

        await create_member(session, ws.id, new_owner.id, WorkspaceRole.OWNER)
        await create_member(
            session, ws.id, former_owner.id, WorkspaceRole.ADMIN, MemberStatus.TRANSFER_PENDING
        )

        transfer = await create_accepted_transfer(
            session,
            ws.id,
            former_owner.id,
            new_owner.id,
            former_choice=FormerOwnerChoice.PENDING.value,
            decision_status=DecisionStatus.PENDING.value,
            deadline_offset=timedelta(days=12),
        )

        # Day 14 scheduled in past (4 days ago)
        rem14 = await create_role_reminder(
            session,
            transfer.id,
            ws.id,
            new_owner.id,
            ReminderType.DAY_14,
            scheduled_offset=-timedelta(days=4),
        )
        # Day 25 scheduled in future (7 days from now)
        rem25 = await create_role_reminder(
            session,
            transfer.id,
            ws.id,
            new_owner.id,
            ReminderType.DAY_25,
            scheduled_offset=timedelta(days=7),
        )

        # Former owner chooses STAY now
        await service.record_former_owner_choice(
            session, ws.id, transfer.id, former_owner.id, choice="STAY"
        )
        await session.commit()

    async with session_factory() as session:
        r14 = (await session.execute(
            select(WorkspaceOwnershipRoleReminder).where(WorkspaceOwnershipRoleReminder.id == rem14.id)
        )).scalar_one()
        r25 = (await session.execute(
            select(WorkspaceOwnershipRoleReminder).where(WorkspaceOwnershipRoleReminder.id == rem25.id)
        )).scalar_one()

        assert r14.status == ReminderStatus.SKIPPED.value
        assert r25.status == ReminderStatus.PENDING.value


@pytest.mark.asyncio
async def test_tc_7_6_07_reminders_cancelled_upon_decision(session_factory):
    """TC-7.6-07: All pending reminders cancelled upon explicit role decision."""
    service = WorkspaceTransferService()

    async with session_factory() as session:
        former_owner = await create_user(session, "canc_f")
        new_owner = await create_user(session, "canc_n")
        ws = await create_workspace(session, "canc_w")

        await create_member(session, ws.id, new_owner.id, WorkspaceRole.OWNER)
        await create_member(
            session, ws.id, former_owner.id, WorkspaceRole.ADMIN, MemberStatus.TRANSFER_PENDING
        )

        transfer = await create_accepted_transfer(
            session,
            ws.id,
            former_owner.id,
            new_owner.id,
            former_choice=FormerOwnerChoice.STAY.value,
            decision_status=DecisionStatus.PENDING.value,
            deadline_offset=timedelta(days=20),
        )

        rem = await create_role_reminder(
            session,
            transfer.id,
            ws.id,
            new_owner.id,
            ReminderType.DAY_25,
            scheduled_offset=timedelta(days=5),
        )

        # New owner makes decision (e.g. MEMBER)
        await service.decide_former_owner_role(
            session, ws.id, transfer.id, new_owner.id, decision="MEMBER"
        )
        await session.commit()

    async with session_factory() as session:
        r_check = (await session.execute(
            select(WorkspaceOwnershipRoleReminder).where(WorkspaceOwnershipRoleReminder.id == rem.id)
        )).scalar_one()
        assert r_check.status == ReminderStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_tc_7_6_08_path_a_unresponsive_former_owner_timeout(session_factory, monkeypatch):
    """TC-7.6-08: Path A: Unresponsive former owner at Day 30 timeout -> State 12 (UNRESPONSIVE_TIMED_OUT)."""
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        former_owner = await create_user(session, "to_former")
        new_owner = await create_user(session, "to_new")
        ws = await create_workspace(session, "to_ws")

        await create_member(session, ws.id, new_owner.id, WorkspaceRole.OWNER)
        former_mem = await create_member(
            session,
            ws.id,
            former_owner.id,
            WorkspaceRole.ADMIN,
            MemberStatus.TRANSFER_PENDING,
        )

        # State 5 (former_owner_choice=PENDING) past Day 30 deadline
        transfer = await create_accepted_transfer(
            session,
            ws.id,
            former_owner.id,
            new_owner.id,
            former_choice=FormerOwnerChoice.PENDING.value,
            decision_status=DecisionStatus.PENDING.value,
            deadline_offset=-timedelta(hours=2),
        )

    # Execute Path A sweep
    res = await _async_sweep_unresponsive_transfers()
    assert res["timed_out_transfers"] >= 1
    assert res["errors"] == 0

    # Verify State 12: UNRESPONSIVE_TIMED_OUT, membership deactivated, zero admin fallback
    async with session_factory() as session:
        t_res = await session.execute(
            select(WorkspaceOwnershipTransfer).where(
                WorkspaceOwnershipTransfer.id == transfer.id
            )
        )
        t_updated = t_res.scalar_one()
        assert t_updated.decision_status == DecisionStatus.TIMED_OUT.value
        assert t_updated.decided_at is not None

        # Verify former owner membership is deleted / deactivated and NOT promoted to ADMIN
        m_res = await session.execute(
            select(WorkspaceMember).where(WorkspaceMember.id == former_mem.id)
        )
        m_updated = m_res.scalar_one()
        assert m_updated.is_deleted is True
        assert m_updated.is_former_owner is False

        # Dual in-app notifications
        notifs = list((await session.execute(
            select(Notification).where(
                Notification.tenant_id == ws.id,
                Notification.user_id.in_([former_owner.id, new_owner.id]),
            )
        )).scalars().all())
        assert len(notifs) >= 2
        titles = [n.title for n in notifs]
        assert any("Former Owner Choice Expired" in t for t in titles)
        assert any("Workspace Access Expired" in t for t in titles)


@pytest.mark.asyncio
async def test_tc_7_6_09_celery_concurrency_skip_locked(session_factory, monkeypatch):
    """TC-7.6-09: Concurrent sweep tasks with SKIP LOCKED process candidates without duplicate processing."""
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        former_owner = await create_user(session, "concur_f")
        new_owner = await create_user(session, "concur_n")
        ws = await create_workspace(session, "concur_ws")

        await create_member(session, ws.id, new_owner.id, WorkspaceRole.OWNER)
        await create_member(
            session, ws.id, former_owner.id, WorkspaceRole.ADMIN, MemberStatus.TRANSFER_PENDING
        )

        transfer = await create_accepted_transfer(
            session,
            ws.id,
            former_owner.id,
            new_owner.id,
            former_choice=FormerOwnerChoice.STAY.value,
            decision_status=DecisionStatus.PENDING.value,
            deadline_offset=timedelta(days=10),
        )

        rem = await create_role_reminder(
            session,
            transfer.id,
            ws.id,
            new_owner.id,
            ReminderType.DAY_14,
            scheduled_offset=-timedelta(hours=1),
        )

    # Run two sweeps concurrently
    results = await asyncio.gather(
        _async_sweep_role_reminders(),
        _async_sweep_role_reminders(),
    )
    total_sent = results[0]["sent"] + results[1]["sent"]
    assert total_sent == 1  # Exactly one worker sent the reminder

    async with session_factory() as session:
        notifs = list((await session.execute(
            select(Notification).where(
                Notification.tenant_id == ws.id,
                Notification.user_id == new_owner.id,
            )
        )).scalars().all())
        assert len(notifs) == 1  # Exactly one notification created


@pytest.mark.asyncio
async def test_tc_7_6_10_transactional_outbox_atomic_guarantee(session_factory, monkeypatch):
    """TC-7.6-10: In-app notification creation and reminder status transition are committed atomically."""
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        former_owner = await create_user(session, "atom_f")
        new_owner = await create_user(session, "atom_n")
        ws = await create_workspace(session, "atom_ws")

        await create_member(session, ws.id, new_owner.id, WorkspaceRole.OWNER)
        await create_member(
            session, ws.id, former_owner.id, WorkspaceRole.ADMIN, MemberStatus.TRANSFER_PENDING
        )

        transfer = await create_accepted_transfer(
            session,
            ws.id,
            former_owner.id,
            new_owner.id,
            former_choice=FormerOwnerChoice.STAY.value,
            decision_status=DecisionStatus.PENDING.value,
            deadline_offset=timedelta(days=10),
        )

        rem = await create_role_reminder(
            session,
            transfer.id,
            ws.id,
            new_owner.id,
            ReminderType.DAY_14,
            scheduled_offset=-timedelta(hours=1),
        )

    # Induce an exception right during notification recording
    orig_record_notification = WorkspaceTransferService._record_in_app_notification

    async def faulty_record_notification(*args, **kwargs):
        raise RuntimeError("Simulated transient DB failure during notification insertion")

    monkeypatch.setattr(
        WorkspaceTransferService,
        "_record_in_app_notification",
        faulty_record_notification,
    )

    res = await _async_sweep_role_reminders()
    assert res["errors"] >= 1

    # Verify that the reminder was NOT committed as SENT (rolled back)
    async with session_factory() as session:
        r_check = (await session.execute(
            select(WorkspaceOwnershipRoleReminder).where(WorkspaceOwnershipRoleReminder.id == rem.id)
        )).scalar_one()
        assert r_check.status == ReminderStatus.PENDING.value
