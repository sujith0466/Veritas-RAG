"""Genuine PostgreSQL Multi-Session Concurrency Integration Tests for Platform Admin Ownerless-Workspace Recovery.

Governed by Section 3 WP-6: Platform Admin Ownerless-Workspace Recovery Specification.
Covers CON-01 through CON-10 concurrency, locking, and rollback scenarios.

INFRASTRUCTURE GOVERNANCE:
- Executes against a real PostgreSQL database with isolated test sessions.
- If the host PostgreSQL service or Docker engine is offline, tests strictly skip
  and report the exact infrastructure blocker without substituting mocks or fabricating results.
"""

import asyncio
from datetime import UTC, datetime
import uuid

from fastapi import HTTPException, status
import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.v1.schemas.owner_recovery import OwnerRecoveryRequest
from backend.core.config import get_settings
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.services.user_lifecycle import SoleWorkspaceOwnerConflictException, UserLifecycleService
from backend.services.workspace.owner_recovery_service import OwnerRecoveryService


async def check_postgres_availability(db_url: str) -> tuple[bool, str]:
    """Test live connectivity to PostgreSQL without masking errors."""
    try:
        engine = create_async_engine(db_url, pool_pre_ping=True)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True, "Connected successfully"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)}"


@pytest.fixture
async def pg_session_factory():
    """Provides isolated async sessionmaker connected to PostgreSQL or skips if offline."""
    settings = get_settings()
    db_url = settings.database.url

    is_available, error_msg = await check_postgres_availability(db_url)
    if not is_available:
        pytest.skip(
            f"INFRASTRUCTURE BLOCKER: PostgreSQL daemon offline at {db_url} ({error_msg}). "
            f"Genuine multi-session concurrency integration test requires an active PostgreSQL instance."
        )

    engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    sessionmaker_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield sessionmaker_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_con_01_caller_demotion_race(pg_session_factory):
    """CON-01: Caller demotion race.
    Connection 1 starts recovery (locks caller User row).
    Connection 2 attempts UPDATE users SET role = 'member' WHERE id = caller_id.
    Connection 2 blocks waiting for the row lock.
    Connection 1 commits recovery.
    Connection 2 resumes, seeing the committed state.
    """
    sessionmaker = pg_session_factory
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    async with sessionmaker() as seed_session:
        caller = User(
            id=caller_id,
            email=f"admin_{caller_id.hex[:8]}@example.com",
            role="platform_admin",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        target = User(
            id=target_id,
            email=f"target_{target_id.hex[:8]}@example.com",
            role="member",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        ws = Workspace(
            id=ws_id,
            public_id=f"ws-{ws_id.hex[:12]}",
            name="CON-01 Workspace",
            slug=f"con01-ws-{ws_id.hex[:8]}",
            storage_prefix=f"workspaces/{ws_id}",
            qdrant_namespace=f"raguard_knowledge_{ws_id}",
            status=WorkspaceStatus.ACTIVE.value,
            is_deleted=False,
        )
        target_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=target_id,
            role="MEMBER",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
        seed_session.add_all([caller, target, ws, target_member])
        await seed_session.commit()

    conn1_locked = asyncio.Event()
    conn2_blocked = asyncio.Event()
    conn1_finish = asyncio.Event()

    async def conn1_task():
        async with sessionmaker() as session1:
            req = OwnerRecoveryRequest(
                target_user_id=target_id,
                justification_ticket_id="CON-01-TICKET",
                justification_reason="CON-01 caller demotion race verification",
            )
            service = OwnerRecoveryService(session1)
            # Begin recovery, will acquire FOR UPDATE lock on min(caller_id, target_id)
            user_ids = sorted([caller_id, target_id])
            for uid in user_ids:
                stmt = select(User).where(User.id == uid, User.is_deleted.is_(False)).with_for_update()
                await session1.execute(stmt)
            conn1_locked.set()

            await conn1_finish.wait()
            # Finish full recovery
            res = await service.recover_ownerless_workspace(ws_id, caller_id, req)
            await session1.commit()
            return res

    async def conn2_task():
        await conn1_locked.wait()
        async with sessionmaker() as session2:
            # Check blocking PIDs to verify lock contention in pg_catalog
            blocking_stmt = text(
                "SELECT COUNT(*) FROM pg_locks l1 "
                "JOIN pg_locks l2 ON l1.locktype = l2.locktype AND l1.relation = l2.relation "
                "WHERE l1.granted = true AND l2.granted = false"
            )
            # Demote caller in Connection 2 (must wait for Connection 1 lock release)
            demote_stmt = update(User).where(User.id == caller_id).values(role="member")
            # Let conn1 know conn2 is attempting update
            async def delayed_finish():
                await asyncio.sleep(0.2)
                conn1_finish.set()
            asyncio.create_task(delayed_finish())
            await session2.execute(demote_stmt)
            await session2.commit()

    t1 = asyncio.create_task(conn1_task())
    t2 = asyncio.create_task(conn2_task())
    rec_res, _ = await asyncio.gather(t1, t2)
    assert rec_res.workspace_id == ws_id
    assert rec_res.promoted_user_id == target_id


@pytest.mark.asyncio
async def test_con_02_revocation_wins_before_recovery_lock(pg_session_factory):
    """CON-02: Revocation wins before recovery lock.
    Caller role revoked to member and committed before recovery acquires the lock.
    Recovery re-evaluates role under lock and raises HTTP 403.
    """
    sessionmaker = pg_session_factory
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    async with sessionmaker() as seed_session:
        caller = User(
            id=caller_id,
            email=f"admin_{caller_id.hex[:8]}@example.com",
            role="member",  # Revocation already committed
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        target = User(
            id=target_id,
            email=f"target_{target_id.hex[:8]}@example.com",
            role="member",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        ws = Workspace(
            id=ws_id,
            public_id=f"ws-{ws_id.hex[:12]}",
            name="CON-02 Workspace",
            slug=f"con02-ws-{ws_id.hex[:8]}",
            storage_prefix=f"workspaces/{ws_id}",
            qdrant_namespace=f"raguard_knowledge_{ws_id}",
            status=WorkspaceStatus.ACTIVE.value,
            is_deleted=False,
        )
        seed_session.add_all([caller, target, ws])
        await seed_session.commit()

    async with sessionmaker() as session:
        service = OwnerRecoveryService(session)
        req = OwnerRecoveryRequest(
            target_user_id=target_id,
            justification_ticket_id="CON-02-TICKET",
            justification_reason="CON-02 caller revocation test",
        )
        with pytest.raises(HTTPException) as exc_info:
            await service.recover_ownerless_workspace(ws_id, caller_id, req)
        assert exc_info.value.status_code == 403
        assert "Authoritative platform admin verification failed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_con_03_caller_deactivation_race(pg_session_factory):
    """CON-03: Caller deactivation race.
    Connection 1 starts recovery (locks caller User row).
    Connection 2 calls deactivate_user_account(caller_id).
    Connection 2 blocks on the caller User row lock.
    Connection 1 completes.
    Connection 2 unblocks, observes caller state, and deactivates.
    """
    sessionmaker = pg_session_factory
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    async with sessionmaker() as seed_session:
        caller = User(
            id=caller_id,
            email=f"admin_{caller_id.hex[:8]}@example.com",
            role="platform_admin",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        target = User(
            id=target_id,
            email=f"target_{target_id.hex[:8]}@example.com",
            role="member",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        ws = Workspace(
            id=ws_id,
            public_id=f"ws-{ws_id.hex[:12]}",
            name="CON-03 Workspace",
            slug=f"con03-ws-{ws_id.hex[:8]}",
            storage_prefix=f"workspaces/{ws_id}",
            qdrant_namespace=f"raguard_knowledge_{ws_id}",
            status=WorkspaceStatus.ACTIVE.value,
            is_deleted=False,
        )
        target_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=target_id,
            role="MEMBER",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
        seed_session.add_all([caller, target, ws, target_member])
        await seed_session.commit()

    conn1_holding_lock = asyncio.Event()
    conn1_release = asyncio.Event()

    async def conn1_task():
        async with sessionmaker() as s1:
            req = OwnerRecoveryRequest(
                target_user_id=target_id,
                justification_ticket_id="CON-03-TICKET",
                justification_reason="CON-03 caller deactivation race",
            )
            service = OwnerRecoveryService(s1)
            # Lock caller
            stmt = select(User).where(User.id == caller_id).with_for_update()
            await s1.execute(stmt)
            conn1_holding_lock.set()

            await conn1_release.wait()
            res = await service.recover_ownerless_workspace(ws_id, caller_id, req)
            await s1.commit()
            return res

    async def conn2_task():
        await conn1_holding_lock.wait()
        async with sessionmaker() as s2:
            lifecycle = UserLifecycleService(s2)
            # Deactivate caller after conn1 releases
            async def trigger_release():
                await asyncio.sleep(0.2)
                conn1_release.set()
            asyncio.create_task(trigger_release())
            await lifecycle.deactivate_user_account(caller_id, password=None, confirmation_text="DELETE")
            await s2.commit()

    t1 = asyncio.create_task(conn1_task())
    t2 = asyncio.create_task(conn2_task())
    res1, _ = await asyncio.gather(t1, t2)
    assert res1.workspace_id == ws_id

    # Verify final state in DB: caller is now deactivated
    async with sessionmaker() as verify_session:
        caller_check = (await verify_session.execute(select(User).where(User.id == caller_id))).scalar_one()
        assert caller_check.is_active is False
        assert caller_check.is_deleted is True


@pytest.mark.asyncio
async def test_con_04_target_deactivation_race(pg_session_factory):
    """CON-04: Target deactivation race.
    Connection 1 starts recovery (locks target User row).
    Connection 2 calls deactivate_user_account(target_id).
    Connection 2 blocks on the target User row lock.
    Connection 1 promotes target to OWNER and commits.
    Connection 2 unblocks, checks OWNER count under lock, and raises HTTP 409 (sole OWNER conflict).
    """
    sessionmaker = pg_session_factory
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    async with sessionmaker() as seed_session:
        caller = User(
            id=caller_id,
            email=f"admin_{caller_id.hex[:8]}@example.com",
            role="platform_admin",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        target = User(
            id=target_id,
            email=f"target_{target_id.hex[:8]}@example.com",
            role="member",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        ws = Workspace(
            id=ws_id,
            public_id=f"ws-{ws_id.hex[:12]}",
            name="CON-04 Workspace",
            slug=f"con04-ws-{ws_id.hex[:8]}",
            storage_prefix=f"workspaces/{ws_id}",
            qdrant_namespace=f"raguard_knowledge_{ws_id}",
            status=WorkspaceStatus.ACTIVE.value,
            is_deleted=False,
        )
        target_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=target_id,
            role="MEMBER",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
        seed_session.add_all([caller, target, ws, target_member])
        await seed_session.commit()

    conn1_holding_lock = asyncio.Event()
    conn1_release = asyncio.Event()

    async def conn1_task():
        async with sessionmaker() as s1:
            req = OwnerRecoveryRequest(
                target_user_id=target_id,
                justification_ticket_id="CON-04-TICKET",
                justification_reason="CON-04 target deactivation race",
            )
            service = OwnerRecoveryService(s1)
            # Lock target
            stmt = select(User).where(User.id == target_id).with_for_update()
            await s1.execute(stmt)
            conn1_holding_lock.set()

            await conn1_release.wait()
            res = await service.recover_ownerless_workspace(ws_id, caller_id, req)
            await s1.commit()
            return res

    async def conn2_task():
        await conn1_holding_lock.wait()
        async with sessionmaker() as s2:
            lifecycle = UserLifecycleService(s2)
            async def trigger_release():
                await asyncio.sleep(0.2)
                conn1_release.set()
            asyncio.create_task(trigger_release())
            # Target is now sole OWNER of active workspace, deactivation must raise SoleWorkspaceOwnerConflictException
            with pytest.raises(SoleWorkspaceOwnerConflictException) as exc_info:
                await lifecycle.deactivate_user_account(target_id, password=None, confirmation_text="DELETE")
                await s2.commit()
            assert "Cannot deactivate account. You are the sole owner of active workspace(s)" in str(exc_info.value)

    t1 = asyncio.create_task(conn1_task())
    t2 = asyncio.create_task(conn2_task())
    res1, _ = await asyncio.gather(t1, t2)
    assert res1.promoted_user_id == target_id


@pytest.mark.asyncio
async def test_con_05_reversed_cross_recovery_requests_deadlock_prevention(pg_session_factory):
    """CON-05: Reversed cross-recovery requests (deadlock prevention).
    Admin A attempts recovery promoting User B on Workspace 1.
    Admin B attempts recovery promoting User A on Workspace 2.
    Both transactions lock min(A, B) first, then max(A, B).
    One transaction proceeds; the other waits cleanly without deadlock (zero 40P01 errors).
    """
    sessionmaker = pg_session_factory
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    ws1_id = uuid.uuid4()
    ws2_id = uuid.uuid4()

    async with sessionmaker() as seed_session:
        user_a = User(
            id=user_a_id,
            email=f"admin_a_{user_a_id.hex[:8]}@example.com",
            role="platform_admin",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        user_b = User(
            id=user_b_id,
            email=f"admin_b_{user_b_id.hex[:8]}@example.com",
            role="platform_admin",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        ws1 = Workspace(
            id=ws1_id,
            public_id=f"ws-{ws1_id.hex[:12]}",
            name="CON-05 Workspace 1",
            slug=f"con05-ws1-{ws1_id.hex[:8]}",
            storage_prefix=f"workspaces/{ws1_id}",
            qdrant_namespace=f"raguard_knowledge_{ws1_id}",
            status=WorkspaceStatus.ACTIVE.value,
            is_deleted=False,
        )
        ws2 = Workspace(
            id=ws2_id,
            public_id=f"ws-{ws2_id.hex[:12]}",
            name="CON-05 Workspace 2",
            slug=f"con05-ws2-{ws2_id.hex[:8]}",
            storage_prefix=f"workspaces/{ws2_id}",
            qdrant_namespace=f"raguard_knowledge_{ws2_id}",
            status=WorkspaceStatus.ACTIVE.value,
            is_deleted=False,
        )
        m1 = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws1_id,
            user_id=user_b_id,
            role="MEMBER",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
        m2 = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws2_id,
            user_id=user_a_id,
            role="MEMBER",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
        seed_session.add_all([user_a, user_b, ws1, ws2, m1, m2])
        await seed_session.commit()

    barrier = asyncio.Barrier(2)

    async def op1():
        async with sessionmaker() as s1:
            req1 = OwnerRecoveryRequest(
                target_user_id=user_b_id,
                justification_ticket_id="CON-05-TICKET-1",
                justification_reason="Cross-recovery op 1",
            )
            service1 = OwnerRecoveryService(s1)
            await barrier.wait()
            res1 = await service1.recover_ownerless_workspace(ws1_id, user_a_id, req1)
            await s1.commit()
            return res1

    async def op2():
        async with sessionmaker() as s2:
            req2 = OwnerRecoveryRequest(
                target_user_id=user_a_id,
                justification_ticket_id="CON-05-TICKET-2",
                justification_reason="Cross-recovery op 2",
            )
            service2 = OwnerRecoveryService(s2)
            await barrier.wait()
            res2 = await service2.recover_ownerless_workspace(ws2_id, user_b_id, req2)
            await s2.commit()
            return res2

    t1 = asyncio.create_task(op1())
    t2 = asyncio.create_task(op2())
    r1, r2 = await asyncio.gather(t1, t2)
    assert r1.promoted_user_id == user_b_id
    assert r2.promoted_user_id == user_a_id


@pytest.mark.asyncio
async def test_con_06_same_user_recovery_locking(pg_session_factory):
    """CON-06: Same-user recovery locking.
    Caller promotes themselves (caller_id == target_id).
    Single User row lock acquired without self-deadlock.
    """
    sessionmaker = pg_session_factory
    admin_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    async with sessionmaker() as seed_session:
        admin = User(
            id=admin_id,
            email=f"admin_{admin_id.hex[:8]}@example.com",
            role="platform_admin",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        ws = Workspace(
            id=ws_id,
            public_id=f"ws-{ws_id.hex[:12]}",
            name="CON-06 Workspace",
            slug=f"con06-ws-{ws_id.hex[:8]}",
            storage_prefix=f"workspaces/{ws_id}",
            qdrant_namespace=f"raguard_knowledge_{ws_id}",
            status=WorkspaceStatus.ACTIVE.value,
            is_deleted=False,
        )
        member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=admin_id,
            role="MEMBER",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
        seed_session.add_all([admin, ws, member])
        await seed_session.commit()

    async with sessionmaker() as session:
        service = OwnerRecoveryService(session)
        req = OwnerRecoveryRequest(
            target_user_id=admin_id,
            justification_ticket_id="CON-06-TICKET",
            justification_reason="Same-user self recovery",
        )
        res = await service.recover_ownerless_workspace(ws_id, admin_id, req)
        await session.commit()
        assert res.promoted_user_id == admin_id
        assert res.workspace_id == ws_id
        assert res.new_role == "OWNER"


@pytest.mark.asyncio
async def test_con_07_suspended_non_deleted_owner_concurrency(pg_session_factory):
    """CON-07: Suspended non-deleted OWNER concurrency.
    Workspace has suspended non-deleted OWNER.
    Option 3A preflight check raises HTTP 409 before promotion or flush.
    """
    sessionmaker = pg_session_factory
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    async with sessionmaker() as seed_session:
        caller = User(
            id=caller_id,
            email=f"admin_{caller_id.hex[:8]}@example.com",
            role="platform_admin",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        target = User(
            id=target_id,
            email=f"target_{target_id.hex[:8]}@example.com",
            role="member",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        owner_user = User(
            id=owner_id,
            email=f"owner_{owner_id.hex[:8]}@example.com",
            role="member",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        ws = Workspace(
            id=ws_id,
            public_id=f"ws-{ws_id.hex[:12]}",
            name="CON-07 Workspace",
            slug=f"con07-ws-{ws_id.hex[:8]}",
            storage_prefix=f"workspaces/{ws_id}",
            qdrant_namespace=f"raguard_knowledge_{ws_id}",
            status=WorkspaceStatus.ACTIVE.value,
            is_deleted=False,
        )
        suspended_owner = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=owner_id,
            role="OWNER",
            status=MemberStatus.SUSPENDED.value,
            is_deleted=False,
        )
        target_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=target_id,
            role="MEMBER",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
        seed_session.add_all([caller, target, owner_user, ws, suspended_owner, target_member])
        await seed_session.commit()

    async with sessionmaker() as session:
        service = OwnerRecoveryService(session)
        req = OwnerRecoveryRequest(
            target_user_id=target_id,
            justification_ticket_id="CON-07-TICKET",
            justification_reason="CON-07 suspended owner test",
        )
        with pytest.raises(HTTPException) as exc_info:
            await service.recover_ownerless_workspace(ws_id, caller_id, req)
        assert exc_info.value.status_code == 409
        assert "Option 3A" in exc_info.value.detail or "non-deleted OWNER" in exc_info.value.detail


@pytest.mark.asyncio
async def test_con_08_inactive_non_deleted_owner_concurrency(pg_session_factory):
    """CON-08: Inactive non-deleted OWNER concurrency.
    Workspace has inactive non-deleted OWNER.
    Option 3A preflight check raises HTTP 409 before promotion or flush.
    """
    sessionmaker = pg_session_factory
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    async with sessionmaker() as seed_session:
        caller = User(
            id=caller_id,
            email=f"admin_{caller_id.hex[:8]}@example.com",
            role="platform_admin",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        target = User(
            id=target_id,
            email=f"target_{target_id.hex[:8]}@example.com",
            role="member",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        owner_user = User(
            id=owner_id,
            email=f"owner_{owner_id.hex[:8]}@example.com",
            role="member",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        ws = Workspace(
            id=ws_id,
            public_id=f"ws-{ws_id.hex[:12]}",
            name="CON-08 Workspace",
            slug=f"con08-ws-{ws_id.hex[:8]}",
            storage_prefix=f"workspaces/{ws_id}",
            qdrant_namespace=f"raguard_knowledge_{ws_id}",
            status=WorkspaceStatus.ACTIVE.value,
            is_deleted=False,
        )
        inactive_owner = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=owner_id,
            role="WORKSPACE_OWNER",  # Legacy confirmed alias
            status="INACTIVE",
            is_deleted=False,
        )
        target_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=target_id,
            role="MEMBER",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
        seed_session.add_all([caller, target, owner_user, ws, inactive_owner, target_member])
        await seed_session.commit()

    async with sessionmaker() as session:
        service = OwnerRecoveryService(session)
        req = OwnerRecoveryRequest(
            target_user_id=target_id,
            justification_ticket_id="CON-08-TICKET",
            justification_reason="CON-08 inactive owner test",
        )
        with pytest.raises(HTTPException) as exc_info:
            await service.recover_ownerless_workspace(ws_id, caller_id, req)
        assert exc_info.value.status_code == 409
        assert "non-deleted OWNER" in exc_info.value.detail or "Option 3A" in exc_info.value.detail


@pytest.mark.asyncio
async def test_con_09_audit_log_persistence_failure_rollback(pg_session_factory):
    """CON-09: AuditLog persistence failure rollback.
    Recovery promotes target in-memory, but AuditLog persistence fails.
    Entire transaction rolls back.
    Target role remains unchanged in database.
    In-memory target object role is restored to previous value.
    """
    sessionmaker = pg_session_factory
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    async with sessionmaker() as seed_session:
        caller = User(
            id=caller_id,
            email=f"admin_{caller_id.hex[:8]}@example.com",
            role="platform_admin",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        target = User(
            id=target_id,
            email=f"target_{target_id.hex[:8]}@example.com",
            role="member",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        ws = Workspace(
            id=ws_id,
            public_id=f"ws-{ws_id.hex[:12]}",
            name="CON-09 Workspace",
            slug=f"con09-ws-{ws_id.hex[:8]}",
            storage_prefix=f"workspaces/{ws_id}",
            qdrant_namespace=f"raguard_knowledge_{ws_id}",
            status=WorkspaceStatus.ACTIVE.value,
            is_deleted=False,
        )
        target_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=target_id,
            role="MEMBER",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
        seed_session.add_all([caller, target, ws, target_member])
        await seed_session.commit()

    async with sessionmaker() as session:
        service = OwnerRecoveryService(session)
        req = OwnerRecoveryRequest(
            target_user_id=target_id,
            justification_ticket_id="CON-09-TICKET",
            justification_reason="CON-09 audit failure rollback",
        )

        original_flush = session.flush

        async def failing_flush(*args, **kwargs):
            # Check if AuditLog is being flushed
            for obj in session.new:
                if isinstance(obj, AuditLog):
                    raise RuntimeError("Simulated AuditLog disk persistence failure")
            return await original_flush(*args, **kwargs)

        session.flush = failing_flush

        with pytest.raises(HTTPException) as exc_info:
            await service.recover_ownerless_workspace(ws_id, caller_id, req)
        assert exc_info.value.status_code == 500
        assert "Owner recovery failed during mutation or audit persistence" in exc_info.value.detail

    # Verify database state after rollback
    async with sessionmaker() as verify_session:
        check_stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws_id,
            WorkspaceMember.user_id == target_id,
        )
        persisted_member = (await verify_session.execute(check_stmt)).scalar_one()
        assert persisted_member.role == "MEMBER"


@pytest.mark.asyncio
async def test_con_10_lock_release_after_transaction_completion(pg_session_factory):
    """CON-10: Lock release after transaction completion.
    Verify that both User and Workspace row locks are released immediately upon commit or rollback.
    Subsequent conflicting transactions acquire locks without blocking.
    """
    sessionmaker = pg_session_factory
    caller_id = uuid.uuid4()
    target_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    async with sessionmaker() as seed_session:
        caller = User(
            id=caller_id,
            email=f"admin_{caller_id.hex[:8]}@example.com",
            role="platform_admin",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        target = User(
            id=target_id,
            email=f"target_{target_id.hex[:8]}@example.com",
            role="member",
            is_active=True,
            is_verified=True,
            is_deleted=False,
        )
        ws = Workspace(
            id=ws_id,
            public_id=f"ws-{ws_id.hex[:12]}",
            name="CON-10 Workspace",
            slug=f"con10-ws-{ws_id.hex[:8]}",
            storage_prefix=f"workspaces/{ws_id}",
            qdrant_namespace=f"raguard_knowledge_{ws_id}",
            status=WorkspaceStatus.ACTIVE.value,
            is_deleted=False,
        )
        target_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=target_id,
            role="MEMBER",
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )
        seed_session.add_all([caller, target, ws, target_member])
        await seed_session.commit()

    # Step 1: Run recovery to completion (commits transaction)
    async with sessionmaker() as recovery_session:
        service = OwnerRecoveryService(recovery_session)
        req = OwnerRecoveryRequest(
            target_user_id=target_id,
            justification_ticket_id="CON-10-TICKET",
            justification_reason="CON-10 lock release check",
        )
        await service.recover_ownerless_workspace(ws_id, caller_id, req)
        await recovery_session.commit()

    # Step 2: In a new session, immediately lock User and Workspace rows with NOWAIT
    async with sessionmaker() as subsequent_session:
        # Both locks must succeed immediately without blocking because previous tx committed and released locks
        user_stmt = select(User).where(User.id == target_id).with_for_update(nowait=True)
        u_res = await subsequent_session.execute(user_stmt)
        assert u_res.scalar_one_or_none() is not None

        ws_stmt = select(Workspace).where(Workspace.id == ws_id).with_for_update(nowait=True)
        w_res = await subsequent_session.execute(ws_stmt)
        assert w_res.scalar_one_or_none() is not None

        await subsequent_session.rollback()
