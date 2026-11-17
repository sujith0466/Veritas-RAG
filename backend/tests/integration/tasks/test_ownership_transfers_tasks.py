"""Integration tests for ownership transfers background sweep tasks.

Section 7, Batch 1: Celery periodic sweep validation.
Verifies:
- Discovery of expired candidates via database clock.
- FOR UPDATE SKIP LOCKED concurrency semantics.
- Transition of expired transfers to EXPIRED and nominee to ACTIVE.
- Dual in-app notification creation.
- Idempotence and isolation across candidate workspaces.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import uuid
from fastapi import HTTPException
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import (
    MemberStatus,
    WorkspaceMember,
    WorkspaceRole,
)
from backend.models.entities.workspace_ownership_transfer import (
    TransferStatus,
    WorkspaceOwnershipTransfer,
)
from backend.models.entities.notification import Notification
from backend.services.workspace_transfer_service import WorkspaceTransferService
from backend.tasks.ownership_transfers import _async_sweep_expired_transfers

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
) -> WorkspaceMember:
    mid = uuid.uuid4()
    mem = WorkspaceMember(
        id=mid,
        workspace_id=workspace_id,
        user_id=user_id,
        role=role.value,
        status=status.value,
    )
    session.add(mem)
    await session.commit()
    await session.refresh(mem)
    return mem


async def create_transfer(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    owner_id: uuid.UUID,
    nominee_id: uuid.UUID,
    expires_at: datetime,
    status: str = TransferStatus.PENDING.value,
) -> WorkspaceOwnershipTransfer:
    tid = uuid.uuid4()
    now_res = await session.execute(select(func.clock_timestamp()))
    db_now = now_res.scalar_one()
    tr = WorkspaceOwnershipTransfer(
        id=tid,
        workspace_id=workspace_id,
        nominated_by_user_id=owner_id,
        nominee_user_id=nominee_id,
        status=status,
        created_at=db_now,
        expires_at=expires_at,
    )
    session.add(tr)
    await session.commit()
    await session.refresh(tr)
    return tr


@pytest.mark.asyncio
async def test_sweep_expired_transfers_success(session_factory, monkeypatch):
    """Test that overdue PENDING transfers are transitioned to EXPIRED, restoring nominee to ACTIVE."""
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        # Get DB clock
        now_res = await session.execute(select(func.clock_timestamp()))
        db_now = now_res.scalar_one()

        owner = await create_user(session, "sweep_owner")
        nominee = await create_user(session, "sweep_nominee")
        ws = await create_workspace(session, "sweep_ws")

        await create_member(session, ws.id, owner.id, WorkspaceRole.OWNER)
        nom_mem = await create_member(
            session, ws.id, nominee.id, WorkspaceRole.MEMBER, MemberStatus.ACTIVE
        )

        # Expired 1 hour ago according to DB clock
        past_expires = db_now - timedelta(hours=1)
        transfer = await create_transfer(
            session, ws.id, owner.id, nominee.id, expires_at=past_expires
        )

    # Run background sweep
    res = await _async_sweep_expired_transfers()
    assert res["expired_transfers"] >= 1
    assert res["errors"] == 0

    # Verify database state
    async with session_factory() as session:
        t_res = await session.execute(
            select(WorkspaceOwnershipTransfer).where(
                WorkspaceOwnershipTransfer.id == transfer.id
            )
        )
        t_updated = t_res.scalar_one()
        assert t_updated.status == TransferStatus.EXPIRED.value
        assert t_updated.expired_at is not None

        m_res = await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == ws.id,
                WorkspaceMember.user_id == nominee.id,
            )
        )
        m_updated = m_res.scalar_one()
        assert m_updated.status == MemberStatus.ACTIVE.value

        # Verify dual in-app notifications
        n_res = await session.execute(
            select(Notification).where(
                Notification.user_id.in_([owner.id, nominee.id])
            )
        )
        notifs = list(n_res.scalars().all())
        assert len(notifs) >= 2
        titles = [n.title for n in notifs]
        assert "Ownership Nomination Expired" in titles


@pytest.mark.asyncio
async def test_sweep_skips_concurrently_locked_workspace(session_factory, monkeypatch):
    """Test that workspaces locked by concurrent transactions are skipped via SKIP LOCKED."""
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        now_res = await session.execute(select(func.clock_timestamp()))
        db_now = now_res.scalar_one()

        owner = await create_user(session, "skip_owner")
        nominee = await create_user(session, "skip_nominee")
        ws = await create_workspace(session, "skip_ws")

        await create_member(session, ws.id, owner.id, WorkspaceRole.OWNER)
        await create_member(
            session, ws.id, nominee.id, WorkspaceRole.MEMBER, MemberStatus.ACTIVE
        )

        past_expires = db_now - timedelta(hours=2)
        transfer = await create_transfer(
            session, ws.id, owner.id, nominee.id, expires_at=past_expires
        )

    # Acquire explicit FOR UPDATE lock in a persistent session to simulate concurrent transaction
    lock_session = session_factory()
    await lock_session.__aenter__()
    try:
        lock_query = select(Workspace).where(Workspace.id == ws.id).with_for_update()
        lock_res = await lock_session.execute(lock_query)
        assert lock_res.scalar_one() is not None

        # Execute sweep in separate session while lock is held
        res = await _async_sweep_expired_transfers()
        assert res["skipped_workspaces"] >= 1

        # Transfer must remain PENDING because the workspace was locked
        async with session_factory() as verify_session:
            t_res = await verify_session.execute(
                select(WorkspaceOwnershipTransfer).where(
                    WorkspaceOwnershipTransfer.id == transfer.id
                )
            )
            t_unmodified = t_res.scalar_one()
            assert t_unmodified.status == TransferStatus.PENDING.value
    finally:
        await lock_session.rollback()
        await lock_session.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_sweep_non_expired_transfer_remains_pending(session_factory, monkeypatch):
    """Test that active transfers that have not yet expired are untouched."""
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        now_res = await session.execute(select(func.clock_timestamp()))
        db_now = now_res.scalar_one()

        owner = await create_user(session, "pending_owner")
        nominee = await create_user(session, "pending_nominee")
        ws = await create_workspace(session, "pending_ws")

        await create_member(session, ws.id, owner.id, WorkspaceRole.OWNER)
        await create_member(
            session, ws.id, nominee.id, WorkspaceRole.MEMBER, MemberStatus.ACTIVE
        )

        future_expires = db_now + timedelta(days=7)
        transfer = await create_transfer(
            session, ws.id, owner.id, nominee.id, expires_at=future_expires
        )

    res = await _async_sweep_expired_transfers()
    # It should not expire future transfers
    async with session_factory() as session:
        t_res = await session.execute(
            select(WorkspaceOwnershipTransfer).where(
                WorkspaceOwnershipTransfer.id == transfer.id
            )
        )
        t = t_res.scalar_one()
        assert t.status == TransferStatus.PENDING.value


@pytest.mark.asyncio
async def test_sweep_idempotence(session_factory, monkeypatch):
    """Test that running the sweep multiple times is fully idempotent."""
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        now_res = await session.execute(select(func.clock_timestamp()))
        db_now = now_res.scalar_one()

        owner = await create_user(session, "idem_owner")
        nominee = await create_user(session, "idem_nominee")
        ws = await create_workspace(session, "idem_ws")

        await create_member(session, ws.id, owner.id, WorkspaceRole.OWNER)
        await create_member(
            session, ws.id, nominee.id, WorkspaceRole.MEMBER, MemberStatus.ACTIVE
        )

        past_expires = db_now - timedelta(minutes=30)
        transfer = await create_transfer(
            session, ws.id, owner.id, nominee.id, expires_at=past_expires
        )

    # First run expires it
    res1 = await _async_sweep_expired_transfers()
    assert res1["expired_transfers"] >= 1

    # Second run does not re-expire it
    res2 = await _async_sweep_expired_transfers()
    assert res2["expired_transfers"] == 0
    async with session_factory() as session:
        t_res = await session.execute(
            select(WorkspaceOwnershipTransfer).where(
                WorkspaceOwnershipTransfer.id == transfer.id
            )
        )
        t = t_res.scalar_one()
        assert t.status == TransferStatus.EXPIRED.value


@pytest.mark.asyncio
async def test_tc_7_3_28_sweep_fresh_clock_timestamp_per_candidate(session_factory, monkeypatch):
    """TC-7.3-28: Multi-candidate sweep evaluates fresh clock_timestamp() per candidate under lock."""
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        now_res = await session.execute(select(func.clock_timestamp()))
        db_now = now_res.scalar_one()

        # Candidate 1: expired 10 minutes ago
        o1 = await create_user(session, "tc28_o1")
        n1 = await create_user(session, "tc28_n1")
        ws1 = await create_workspace(session, "tc28_ws1")
        await create_member(session, ws1.id, o1.id, WorkspaceRole.OWNER)
        await create_member(session, ws1.id, n1.id, WorkspaceRole.MEMBER, MemberStatus.ACTIVE)
        t1 = await create_transfer(session, ws1.id, o1.id, n1.id, expires_at=db_now - timedelta(minutes=10))

        # Candidate 2: expired 5 minutes ago
        o2 = await create_user(session, "tc28_o2")
        n2 = await create_user(session, "tc28_n2")
        ws2 = await create_workspace(session, "tc28_ws2")
        await create_member(session, ws2.id, o2.id, WorkspaceRole.OWNER)
        await create_member(session, ws2.id, n2.id, WorkspaceRole.MEMBER, MemberStatus.ACTIVE)
        t2 = await create_transfer(session, ws2.id, o2.id, n2.id, expires_at=db_now - timedelta(minutes=5))

    res = await _async_sweep_expired_transfers()
    assert res["expired_transfers"] >= 2

    # Verify both transfers expired cleanly in DB
    async with session_factory() as session:
        t1_db = (await session.execute(
            select(WorkspaceOwnershipTransfer).where(WorkspaceOwnershipTransfer.id == t1.id)
        )).scalar_one()
        t2_db = (await session.execute(
            select(WorkspaceOwnershipTransfer).where(WorkspaceOwnershipTransfer.id == t2.id)
        )).scalar_one()
        assert t1_db.status == TransferStatus.EXPIRED.value
        assert t2_db.status == TransferStatus.EXPIRED.value


@pytest.mark.asyncio
async def test_tc_7_e_03_concurrent_acceptance_and_expiration_sweep(session_factory, monkeypatch):
    """TC-7.E-03: Concurrent acceptance and expiration sweep with bounded timeout.
    Exactly one terminal state wins (ACCEPTED or EXPIRED) without deadlocks or corrupt intermediate states.
    """
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )
    service = WorkspaceTransferService()

    async with session_factory() as session:
        now_res = await session.execute(select(func.clock_timestamp()))
        db_now = now_res.scalar_one()

        owner = await create_user(session, "e03_owner")
        nominee = await create_user(session, "e03_nominee")
        ws = await create_workspace(session, "e03_ws")

        await create_member(session, ws.id, owner.id, WorkspaceRole.OWNER)
        await create_member(session, ws.id, nominee.id, WorkspaceRole.MEMBER, MemberStatus.ACTIVE)

        transfer = await create_transfer(
            session, ws.id, owner.id, nominee.id, expires_at=db_now - timedelta(seconds=1)
        )
        ws_id = ws.id
        transfer_id = transfer.id
        nominee_id = nominee.id

    async def do_accept():
        async with session_factory() as sess:
            try:
                res = await service.accept_transfer(sess, ws_id, transfer_id, nominee_id)
                return ("ACCEPTED", res)
            except HTTPException as e:
                return ("EXC", e)

    async def do_sweep():
        res = await _async_sweep_expired_transfers()
        return ("SWEEP", res)

    # Run concurrently with bounded timeout to prove zero deadlocks
    results = await asyncio.wait_for(asyncio.gather(do_accept(), do_sweep()), timeout=10.0)
    accept_outcome = results[0]

    async with session_factory() as session:
        t_res = await session.execute(
            select(WorkspaceOwnershipTransfer).where(WorkspaceOwnershipTransfer.id == transfer_id)
        )
        final_t = t_res.scalar_one()
        assert final_t.status in (TransferStatus.ACCEPTED.value, TransferStatus.EXPIRED.value)

        if final_t.status == TransferStatus.ACCEPTED.value:
            nom_m = (await session.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == ws_id,
                    WorkspaceMember.user_id == nominee_id
                )
            )).scalar_one()
            assert nom_m.role == WorkspaceRole.OWNER.value
            assert accept_outcome[0] == "ACCEPTED"
        else:
            assert final_t.status == TransferStatus.EXPIRED.value
            if accept_outcome[0] == "EXC":
                assert accept_outcome[1].status_code in (409, 410)
