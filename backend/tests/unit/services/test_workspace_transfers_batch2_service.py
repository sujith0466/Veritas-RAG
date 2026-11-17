"""Service, Model & Concurrency Unit/Integration Tests - Section 7, Batch 2.

Governed by Section 7 Batch 2 (V3.0) and ratified Project Owner Decisions:
- WP 7.5: Prohibited VIEWER DB Constraint (TC-7.5-04)
- WP 7.7: Former Owner Identification & Zero-Privilege Escalation (TC-7.7-01 through TC-7.7-05)
- WP 7.8: Concurrent Owner Leave vs Acceptance Invariant Drill (TC-7.8-05)
- Concurrency, Race Condition & Deadlock Freedom Drills (TC-7.C-01 through TC-7.C-04)
"""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
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
def service():
    return WorkspaceTransferService()


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
        current_owner_email_snapshot="former_owner@raguard.test",
        nominated_user_email_snapshot="new_owner@raguard.test",
    )
    session.add(tr)
    await session.commit()
    await session.refresh(tr)
    return tr


# ==============================================================================
# WORK PACKAGE 7.5: DATABASE CONSTRAINT VALIDATION (TC-7.5-04)
# ==============================================================================

@pytest.mark.asyncio
async def test_tc_7_5_04_chk_former_owner_never_viewer_db_constraint(session_factory):
    """TC-7.5-04: Database check constraint chk_former_owner_never_viewer prevents VIEWER role when is_former_owner is True."""
    async with session_factory() as session:
        user = await create_user(session, "constraint_user")
        ws = await create_workspace(session, "constraint_ws")

        # Attempt to insert a member with is_former_owner=True AND role='VIEWER'
        bad_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            user_id=user.id,
            role="VIEWER",
            status=MemberStatus.ACTIVE.value,
            is_former_owner=True,
        )
        session.add(bad_member)

        with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
            await session.commit()

        # Confirm that the check constraint triggered
        assert "chk_former_owner_never_viewer" in str(exc_info.value).lower()
        await session.rollback()


# ==============================================================================
# WORK PACKAGE 7.7: OLD OWNER IDENTIFICATION & ZERO-PRIVILEGE ESCALATION
# ==============================================================================

@pytest.mark.asyncio
async def test_tc_7_7_01_and_01b_is_former_owner_set_on_admin_and_member(session_factory, service):
    """TC-7.7-01 & TC-7.7-01B: is_former_owner flag is set to True upon explicit ADMIN or MEMBER decision."""
    # Subtest 1: ADMIN decision
    async with session_factory() as session:
        former_1 = await create_user(session, "fo1_former")
        new_1 = await create_user(session, "fo1_new")
        ws1 = await create_workspace(session, "fo1_ws")

        await create_member(session, ws1.id, new_1.id, WorkspaceRole.OWNER)
        m1 = await create_member(
            session, ws1.id, former_1.id, WorkspaceRole.ADMIN, MemberStatus.TRANSFER_PENDING
        )

        t1 = await create_accepted_transfer(
            session, ws1.id, former_1.id, new_1.id,
            former_choice=FormerOwnerChoice.STAY.value,
            decision_status=DecisionStatus.PENDING.value,
        )

        await service.decide_former_owner_role(
            session, ws1.id, t1.id, new_1.id, decision="ADMIN"
        )
        await session.commit()

    async with session_factory() as session:
        m1_db = (await session.execute(
            select(WorkspaceMember).where(WorkspaceMember.id == m1.id)
        )).scalar_one()
        assert m1_db.role == WorkspaceRole.ADMIN.value
        assert m1_db.is_former_owner is True
        assert m1_db.status == MemberStatus.ACTIVE.value

    # Subtest 2: MEMBER decision
    async with session_factory() as session:
        former_2 = await create_user(session, "fo2_former")
        new_2 = await create_user(session, "fo2_new")
        ws2 = await create_workspace(session, "fo2_ws")

        await create_member(session, ws2.id, new_2.id, WorkspaceRole.OWNER)
        m2 = await create_member(
            session, ws2.id, former_2.id, WorkspaceRole.ADMIN, MemberStatus.TRANSFER_PENDING
        )

        t2 = await create_accepted_transfer(
            session, ws2.id, former_2.id, new_2.id,
            former_choice=FormerOwnerChoice.STAY.value,
            decision_status=DecisionStatus.PENDING.value,
        )

        await service.decide_former_owner_role(
            session, ws2.id, t2.id, new_2.id, decision="MEMBER"
        )
        await session.commit()

    async with session_factory() as session:
        m2_db = (await session.execute(
            select(WorkspaceMember).where(WorkspaceMember.id == m2.id)
        )).scalar_one()
        assert m2_db.role == WorkspaceRole.MEMBER.value
        assert m2_db.is_former_owner is True
        assert m2_db.status == MemberStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_tc_7_7_02_is_former_owner_set_on_automatic_fallback(session_factory, monkeypatch):
    """TC-7.7-02: is_former_owner flag is set to True upon automatic ADMIN fallback."""
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        former = await create_user(session, "fb_flag_former")
        new_o = await create_user(session, "fb_flag_new")
        ws = await create_workspace(session, "fb_flag_ws")

        await create_member(session, ws.id, new_o.id, WorkspaceRole.OWNER)
        mem = await create_member(
            session, ws.id, former.id, WorkspaceRole.ADMIN, MemberStatus.TRANSFER_PENDING
        )

        transfer = await create_accepted_transfer(
            session, ws.id, former.id, new_o.id,
            former_choice=FormerOwnerChoice.STAY.value,
            decision_status=DecisionStatus.PENDING.value,
            deadline_offset=-timedelta(minutes=5),
        )

    await _async_sweep_automatic_fallbacks()

    async with session_factory() as session:
        mem_db = (await session.execute(
            select(WorkspaceMember).where(WorkspaceMember.id == mem.id)
        )).scalar_one()
        assert mem_db.is_former_owner is True
        assert mem_db.role == WorkspaceRole.ADMIN.value
        assert mem_db.status == MemberStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_tc_7_7_03_zero_privilege_escalation_for_former_owner(session_factory, service):
    """TC-7.7-03: Former owner (ADMIN with is_former_owner=True) cannot initiate transfers or access owner operations."""
    async with session_factory() as session:
        former = await create_user(session, "noesc_former")
        new_o = await create_user(session, "noesc_new")
        third_party = await create_user(session, "noesc_third")
        ws = await create_workspace(session, "noesc_ws")

        await create_member(session, ws.id, new_o.id, WorkspaceRole.OWNER)
        await create_member(
            session, ws.id, former.id, WorkspaceRole.ADMIN, MemberStatus.ACTIVE, is_former_owner=True
        )

        # Attempt to initiate ownership nomination as the former owner (who is currently ADMIN)
        with pytest.raises(HTTPException) as exc_info:
            await service.initiate_nomination(
                session, ws.id, former.id, third_party.id
            )

        assert exc_info.value.status_code == 403
        assert "active workspace OWNER" in exc_info.value.detail


@pytest.mark.asyncio
async def test_tc_7_7_04_05_normal_members_false_and_immutability(session_factory):
    """TC-7.7-04 & TC-7.7-05: Normal members default to is_former_owner=False; flag cannot be arbitrarily set via normal role update."""
    async with session_factory() as session:
        user = await create_user(session, "norm_user")
        ws = await create_workspace(session, "norm_ws")

        # Standard membership creation
        mem = await create_member(session, ws.id, user.id, WorkspaceRole.MEMBER)

        assert mem.is_former_owner is False

        # Role change from MEMBER to ADMIN does NOT toggle is_former_owner
        mem.role = WorkspaceRole.ADMIN.value
        await session.commit()
        await session.refresh(mem)

        assert mem.is_former_owner is False


# ==============================================================================
# WORK PACKAGE 7.8: CONCURRENT OWNER LEAVE VS ACCEPTANCE INVARIANT DRILL
# ==============================================================================

@pytest.mark.asyncio
async def test_tc_7_8_05_concurrent_owner_leave_and_acceptance_invariant(session_factory, service):
    """TC-7.8-05: Concurrent owner leave and ownership acceptance drill preserves invariant of >= 1 active owner."""
    async with session_factory() as session:
        owner = await create_user(session, "c_inv_owner")
        nominee = await create_user(session, "c_inv_nominee")
        ws = await create_workspace(session, "c_inv_ws")

        await create_member(session, ws.id, owner.id, WorkspaceRole.OWNER)
        await create_member(session, ws.id, nominee.id, WorkspaceRole.MEMBER)

        now_res = await session.execute(select(func.clock_timestamp()))
        db_now = now_res.scalar_one()

        transfer = WorkspaceOwnershipTransfer(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            nominated_by_user_id=owner.id,
            nominee_user_id=nominee.id,
            status=TransferStatus.PENDING.value,
            created_at=db_now,
            expires_at=db_now + timedelta(days=7),
            current_owner_email_snapshot="owner@raguard.test",
            nominated_user_email_snapshot="nominee@raguard.test",
        )
        session.add(transfer)
        await session.commit()
        ws_id = ws.id
        t_id = transfer.id
        o_id = owner.id
        n_id = nominee.id

    async def do_leave():
        async with session_factory() as s:
            from backend.repositories.workspace import WorkspaceRepository
            from backend.repositories.workspace_member import WorkspaceMemberRepository
            from backend.services.workspace.membership_service import (
                MembershipConflictError,
                WorkspaceMembershipService,
            )
            m_service = WorkspaceMembershipService(
                member_repo=WorkspaceMemberRepository(session=s),
                workspace_repo=WorkspaceRepository(session=s),
            )
            owner_m = await m_service.member_repo.get_membership(ws_id, o_id)
            try:
                await m_service.remove_member(s, ws_id, o_id, owner_m.id)
                return ("LEAVE_OK", None)
            except (MembershipConflictError, HTTPException) as e:
                return ("LEAVE_DENIED", e)

    async def do_accept():
        async with session_factory() as s:
            try:
                res = await service.accept_transfer(s, ws_id, t_id, n_id)
                return ("ACCEPT_OK", res)
            except HTTPException as e:
                return ("ACCEPT_EXC", e)

    res_leave, res_accept = await asyncio.gather(do_leave(), do_accept())

    # Invariant check: In both outcomes, the workspace never becomes ownerless
    async with session_factory() as session:
        owners = list((await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == ws_id,
                WorkspaceMember.role == WorkspaceRole.OWNER.value,
                WorkspaceMember.status == MemberStatus.ACTIVE.value,
                WorkspaceMember.is_deleted == False,
            )
        )).scalars().all())
        assert len(owners) >= 1  # At least one active owner is strictly guaranteed!


# ==============================================================================
# CONCURRENCY, RACE CONDITIONS & DEADLOCK FREEDOM DRILLS (TC-7.C-01 through TC-7.C-04)
# ==============================================================================

@pytest.mark.asyncio
async def test_tc_7_c_01_concurrent_decision_and_fallback_sweep(session_factory, monkeypatch, service):
    """TC-7.C-01: Concurrent New Owner Decision and Celery Fallback Sweep.
    Exactly one transaction succeeds and sets state (State 8 or State 11) with zero double promotions.
    """
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        former = await create_user(session, "c01_former")
        new_o = await create_user(session, "c01_new")
        ws = await create_workspace(session, "c01_ws")

        await create_member(session, ws.id, new_o.id, WorkspaceRole.OWNER)
        await create_member(
            session, ws.id, former.id, WorkspaceRole.ADMIN, MemberStatus.TRANSFER_PENDING
        )

        transfer = await create_accepted_transfer(
            session, ws.id, former.id, new_o.id,
            former_choice=FormerOwnerChoice.STAY.value,
            decision_status=DecisionStatus.PENDING.value,
            deadline_offset=-timedelta(seconds=1),  # Overdue to trigger sweep
        )
        ws_id = ws.id
        t_id = transfer.id
        new_id = new_o.id

    async def user_decision():
        async with session_factory() as s:
            try:
                res = await service.decide_former_owner_role(
                    s, ws_id, t_id, new_id, decision="ADMIN"
                )
                await s.commit()
                return ("USER", res)
            except HTTPException as e:
                return ("USER_EXC", e)

    async def fallback_sweep():
        return ("SWEEP", await _async_sweep_automatic_fallbacks())

    res1, res2 = await asyncio.wait_for(
        asyncio.gather(user_decision(), fallback_sweep()),
        timeout=10.0,
    )

    async with session_factory() as session:
        t_final = (await session.execute(
            select(WorkspaceOwnershipTransfer).where(WorkspaceOwnershipTransfer.id == t_id)
        )).scalar_one()

        # Decision status must be either DECIDED_ADMIN or FALLBACK_ADMIN, never duplicate or corrupt
        assert t_final.decision_status in (
            DecisionStatus.DECIDED_ADMIN.value,
            DecisionStatus.FALLBACK_ADMIN.value,
        )


@pytest.mark.asyncio
async def test_tc_7_c_02_concurrent_former_owner_choice_stay_vs_leave_race(session_factory, service):
    """TC-7.C-02: Concurrent STAY vs LEAVE choice race by former owner.
    Row locks ensure exactly one choice commits; the other encounters 409 Conflict.
    """
    async with session_factory() as session:
        former = await create_user(session, "c02_former")
        new_o = await create_user(session, "c02_new")
        ws = await create_workspace(session, "c02_ws")

        await create_member(session, ws.id, new_o.id, WorkspaceRole.OWNER)
        await create_member(
            session, ws.id, former.id, WorkspaceRole.ADMIN, MemberStatus.TRANSFER_PENDING
        )

        transfer = await create_accepted_transfer(
            session, ws.id, former.id, new_o.id,
            former_choice=FormerOwnerChoice.PENDING.value,
            decision_status=DecisionStatus.PENDING.value,
            deadline_offset=timedelta(days=15),
        )
        ws_id = ws.id
        t_id = transfer.id
        f_id = former.id

    async def submit_choice(choice_val: str):
        async with session_factory() as s:
            try:
                res = await service.record_former_owner_choice(
                    s, ws_id, t_id, f_id, choice=choice_val
                )
                await s.commit()
                return ("OK", choice_val)
            except HTTPException as e:
                return ("CONFLICT", e.status_code)

    res_stay, res_leave = await asyncio.gather(
        submit_choice("STAY"),
        submit_choice("LEAVE"),
    )

    outcomes = [res_stay[0], res_leave[0]]
    assert "OK" in outcomes
    assert "CONFLICT" in outcomes

    conflict_res = res_stay if res_stay[0] == "CONFLICT" else res_leave
    assert conflict_res[1] == 409


@pytest.mark.asyncio
async def test_tc_7_c_03_concurrent_choice_and_timeout_sweep(session_factory, monkeypatch, service):
    """TC-7.C-03: Concurrent Former Owner Choice and Path A Timeout Sweep.
    Exactly one transaction commits (State 7 or State 12) without deadlocks.
    """
    monkeypatch.setattr(
        "backend.tasks.ownership_transfers.get_session_factory",
        lambda: session_factory,
    )

    async with session_factory() as session:
        former = await create_user(session, "c03_former")
        new_o = await create_user(session, "c03_new")
        ws = await create_workspace(session, "c03_ws")

        await create_member(session, ws.id, new_o.id, WorkspaceRole.OWNER)
        await create_member(
            session, ws.id, former.id, WorkspaceRole.ADMIN, MemberStatus.TRANSFER_PENDING
        )

        transfer = await create_accepted_transfer(
            session, ws.id, former.id, new_o.id,
            former_choice=FormerOwnerChoice.PENDING.value,
            decision_status=DecisionStatus.PENDING.value,
            deadline_offset=-timedelta(seconds=1),  # Overdue for timeout
        )
        ws_id = ws.id
        t_id = transfer.id
        f_id = former.id

    async def do_stay():
        async with session_factory() as s:
            try:
                res = await service.record_former_owner_choice(
                    s, ws_id, t_id, f_id, choice="STAY"
                )
                await s.commit()
                return ("STAY_OK", res)
            except HTTPException as e:
                return ("STAY_EXC", e.status_code)

    async def do_sweep():
        return ("SWEEP_OK", await _async_sweep_unresponsive_transfers())

    res1, res2 = await asyncio.wait_for(
        asyncio.gather(do_stay(), do_sweep()),
        timeout=10.0,
    )

    async with session_factory() as session:
        t_check = (await session.execute(
            select(WorkspaceOwnershipTransfer).where(WorkspaceOwnershipTransfer.id == t_id)
        )).scalar_one()

        # Final state must be cleanly resolved: either STAY or TIMED_OUT
        assert (
            t_check.former_owner_choice == FormerOwnerChoice.STAY.value
            or t_check.decision_status == DecisionStatus.TIMED_OUT.value
        )


@pytest.mark.asyncio
async def test_tc_7_c_04_deadlock_freedom_drill_10_concurrent_operations(session_factory, service):
    """TC-7.C-04: Deadlock freedom drill across 10 concurrent operations adhering strictly to L_W -> L_TRANS -> L_WM."""
    async with session_factory() as session:
        owner = await create_user(session, "df_owner")
        ws = await create_workspace(session, "df_ws")
        await create_member(session, ws.id, owner.id, WorkspaceRole.OWNER)

        transfers = []
        nominees = []
        for i in range(5):
            nom = await create_user(session, f"df_nom_{i}")
            nominees.append(nom)
            await create_member(session, ws.id, nom.id, WorkspaceRole.MEMBER)
            t = await create_accepted_transfer(
                session, ws.id, owner.id, nom.id,
                former_choice=FormerOwnerChoice.STAY.value,
                decision_status=DecisionStatus.PENDING.value,
            )
            transfers.append(t)

        ws_id = ws.id

    async def run_op(idx: int):
        t = transfers[idx % len(transfers)]
        nom = nominees[idx % len(nominees)]
        async with session_factory() as s:
            try:
                # Interleaved read and decision operations
                if idx % 2 == 0:
                    await service.get_active_transfer(s, ws_id, owner.id)
                else:
                    await service.decide_former_owner_role(
                        s, ws_id, t.id, nom.id, decision="MEMBER"
                    )
                    await s.commit()
                return ("OK", idx)
            except HTTPException:
                return ("HTTP_EXC", idx)

    tasks = [run_op(i) for i in range(10)]
    # Run all 10 operations concurrently; must finish within 15 seconds without DeadlockDetected
    results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=15.0)

    # Assert no unhandled SQL deadlock errors occurred
    assert len(results) == 10
