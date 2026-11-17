"""Genuine 50-User PostgreSQL Concurrency Stress Drills for Sections 4 and 5.

Governed by:
- Master Implementation & Testing Plan v2.6 (VRAG-PLAN-SEC4-SEC5-20261114-V2.6)
- Operational Remediation Execution Plan V1.6 (Section 11)
- Binding Decisions Q1, Q2, Q3, Q4, Q5 (Option B), Q6 (Option A)

Authoritative Drill Architecture:
1. test_50_user_concurrent_reusable_invitation_redemption:
   - 50 distinct virtual users concurrently redeem the same reusable link (is_legacy_bound=False, email=None).
   - Synchronized simultaneous execution via asyncio.Barrier(50) across 50 independent database sessions.
   - Validates: HTTP 200 / success, role == 'MEMBER', invitation remains PENDING, 50 WorkspaceMember rows,
     50 WorkspaceInvitationRedemption rows, 0 deadlocks (pg_stat_database delta == 0).
2. test_50_user_concurrent_repeat_redemptions:
   - The same 50 users simultaneously re-redeem the same reusable link via asyncio.Barrier(50).
   - Validates: Idempotent return (status == 'ALREADY_MEMBER'), active membership count remains exactly 50 (0 duplicates).
3. test_50_user_concurrent_join_code_usage_increment:
   - 50 concurrent tasks invoke atomic increment_usage() across 50 separate database sessions.
   - Validates: Initial counter (0) vs final counter delta is exactly +50 with zero lost updates.
4. test_5_worker_outbox_claiming_contention:
   - CLASSIFICATION: Database-Level Concurrency & Locking Verification Drill.
   - 5 concurrent asyncio worker coroutines (not OS processes) contend for 50 pending outbox records using
     PostgreSQL SELECT ... FOR UPDATE SKIP LOCKED.
   - Validates: Distribution matrix guarantees every row is claimed by exactly 1 worker; zero duplicate claims.
   - ARCHITECTURAL BOUNDARY: The production worker in join_code_notifications.py hardcodes the global
     get_session_factory() targeting default port 5432 and lacks skip_locked. Because modifying production files
     is strictly forbidden under governance rules, this test exercises PostgreSQL engine-level locking on
     the real notification_outbox table on port 5434. This is a database-level concurrency verification drill,
     not a production Celery worker verification.

INFRASTRUCTURE GOVERNANCE:
- Executes strictly against the isolated staging PostgreSQL 15 instance on port 5434.
- Fails closed if invoked against arbitrary hosts, ports, or databases.
- Separates genuine infrastructure unavailability (skips) from authentication, configuration,
  schema, and application errors (fails).
- Preflight engine disposal is guaranteed in a finally block across connection and auth failures.
- Teardown is multi-stage failure-safe: tracks primary test exceptions, cleanup exceptions, and engine
  disposal exceptions independently, reporting all failures without masking the primary cause.
"""

import asyncio
from datetime import UTC, datetime, timedelta
import os
import socket
import time
from typing import Any
from unittest.mock import MagicMock
from urllib.parse import quote_plus, urlparse
import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models.entities.notification_outbox import NotificationOutbox
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_invitation import (
    InvitationStatus,
    WorkspaceInvitation,
    WorkspaceInvitationRedemption,
)
from backend.models.entities.workspace_join_code import WorkspaceJoinCode
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_invitation import WorkspaceInvitationRepository
from backend.repositories.workspace_join_code import WorkspaceJoinCodeRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.services.workspace.invitation_service import (
    WorkspaceInvitationService,
    generate_invitation_token,
)

# Concurrency barrier timeout in seconds
BARRIER_TIMEOUT_SECONDS = 15.0


def validate_staging_db_url(db_url: str) -> None:
    """Strictly validates that the connection URL targets the staging database on port 5434."""
    if not db_url:
        raise ValueError("DATABASE CONFIGURATION ERROR: Staging database URL is missing or empty.")

    parsed = urlparse(db_url)
    hostname = parsed.hostname or ""
    if hostname not in ("127.0.0.1", "localhost"):
        raise ValueError(
            f"DATABASE CONFIGURATION ERROR: Target host must be '127.0.0.1' or 'localhost', got '{hostname}'."
        )

    port = parsed.port or 5432
    if port != 5434:
        raise ValueError(
            f"DATABASE CONFIGURATION ERROR: Target port must be strictly 5434, got {port}."
        )

    db_name = parsed.path.lstrip("/")
    if db_name != "raguard_staging_db":
        raise ValueError(
            f"DATABASE CONFIGURATION ERROR: Target database must be strictly 'raguard_staging_db', got '{db_name}'."
        )

    username = parsed.username or ""
    if username != "raguard_staging_admin":
        raise ValueError(
            f"DATABASE CONFIGURATION ERROR: Target username must be 'raguard_staging_admin', got '{username}'."
        )

    if not parsed.password:
        raise ValueError(
            "DATABASE CONFIGURATION ERROR: Staging password is required and cannot be empty."
        )


def resolve_staging_db_url() -> str:
    """Resolves and strictly validates the staging database URL from environment variables.
    
    Safe Resolution Rules:
    - Checks STAGING_DATABASE_URL or derives from STAGING_DB_PASSWORD.
    - Zero unsafe fallback to arbitrary DATABASE_URL.
    - Zero hardcoded or dummy credentials.
    """
    if os.environ.get("STAGING_DATABASE_URL"):
        url = os.environ["STAGING_DATABASE_URL"]
        validate_staging_db_url(url)
        return url

    staging_pw = os.environ.get("STAGING_DB_PASSWORD")
    if staging_pw:
        encoded_pw = quote_plus(staging_pw)
        url = f"postgresql+asyncpg://raguard_staging_admin:{encoded_pw}@127.0.0.1:5434/raguard_staging_db"
        validate_staging_db_url(url)
        return url

    # No credentials provided: return empty string (do not invent dummy credentials)
    return ""


def is_staging_port_open(host: str = "127.0.0.1", port: int = 5434, timeout: float = 1.0) -> bool:
    """Checks if TCP port 5434 is listening on loopback."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout, ConnectionRefusedError):
        return False


async def wait_at_barrier(barrier: asyncio.Barrier, timeout: float = BARRIER_TIMEOUT_SECONDS) -> None:
    """Waits at barrier with bounded timeout and cancellation/broken barrier handling."""
    try:
        await asyncio.wait_for(barrier.wait(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise TimeoutError(
            f"Worker timed out waiting at concurrency barrier after {timeout} seconds."
        ) from exc
    except asyncio.BrokenBarrierError as exc:
        raise RuntimeError(
            "Concurrency barrier broken due to failure or cancellation in a peer worker."
        ) from exc


async def get_deadlock_count(engine) -> int:
    """Queries current database deadlock count from pg_stat_database.
    
    MEASUREMENT LIMITATION:
    pg_stat_database.deadlocks is a cumulative counter for the entire database.
    This measurement isolates deadlocks occurring during the execution window of
    this drill, assuming zero external concurrent activity on the isolated staging database.
    """
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT deadlocks FROM pg_stat_database WHERE datname = current_database();")
        )
        row = result.first()
        return int(row[0]) if row and row[0] is not None else 0


@pytest.fixture(scope="module")
async def staging_db_url():
    """Provides validated staging database URL.
    
    Strict Preflight Order (Finding B):
    1. Resolve and validate STAGING_DATABASE_URL or STAGING_DB_PASSWORD first.
    2. Missing credentials or invalid staging configuration must fail (pytest.fail).
    3. Only after valid configuration is verified, check whether 127.0.0.1:5434 is listening.
    4. A correctly configured but unavailable staging PostgreSQL instance produces an infrastructure skip (pytest.skip).
    5. Connection and engine disposal errors are tracked independently and preserved without masking.
    """
    # 1. Resolve and validate STAGING_DATABASE_URL or STAGING_DB_PASSWORD first (Finding B)
    db_url = resolve_staging_db_url()
    if not db_url:
        pytest.fail(
            "CONFIGURATION ERROR: STAGING_DB_PASSWORD or STAGING_DATABASE_URL environment variable is missing. "
            "Staging configuration must be provided before executing concurrency drills."
        )

    # 2. Check whether staging PostgreSQL instance is listening on port 5434
    if not is_staging_port_open("127.0.0.1", 5434):
        pytest.skip(
            "INFRASTRUCTURE BLOCKER: Staging PostgreSQL daemon is not listening on 127.0.0.1:5434. "
            "Isolated staging container is offline. Concurrency tests strictly skip."
        )

    engine = create_async_engine(db_url, pool_pre_ping=True)
    conn_exc = None
    dispose_exc = None
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        conn_exc = exc
    finally:
        # Preflight engine disposal is guaranteed under all circumstances
        try:
            await engine.dispose()
        except Exception as d_exc:
            dispose_exc = d_exc

    # Failure reporting logic preserving both connection and disposal errors independently
    if conn_exc is not None and dispose_exc is not None:
        pytest.fail(
            f"PREFLIGHT COMPOSITE FAILURE: [Connection Failed: {type(conn_exc).__name__}: {conn_exc}] "
            f"AND [Engine Disposal Failed: {type(dispose_exc).__name__}: {dispose_exc}]"
        )
    elif dispose_exc is not None:
        pytest.fail(
            f"PREFLIGHT DISPOSAL ERROR: Preflight connection succeeded, but engine disposal failed: {type(dispose_exc).__name__}: {dispose_exc}"
        )
    elif conn_exc is not None:
        exc_str = str(conn_exc).lower()
        if "password authentication failed" in exc_str or "invalidpassworderror" in exc_str:
            pytest.fail(
                f"AUTHENTICATION FAILURE: Connected to staging PostgreSQL on 127.0.0.1:5434, "
                f"but credentials for 'raguard_staging_admin' were rejected: {conn_exc}"
            )
        elif "connection refused" in exc_str or "cannotconnectnowerror" in exc_str:
            pytest.skip(
                f"INFRASTRUCTURE BLOCKER: Could not connect to staging PostgreSQL on port 5434 ({conn_exc})."
            )
        else:
            pytest.fail(
                f"STAGING DATABASE INITIALIZATION ERROR: Staging instance on port 5434 returned error: {conn_exc}"
            )

    return db_url


@pytest.mark.asyncio
async def test_50_user_concurrent_reusable_invitation_redemption(staging_db_url):
    """Drill 1: 50 concurrent virtual users redeem the same reusable link under row locking."""
    engine = create_async_engine(staging_db_url, pool_size=60, max_overflow=20, pool_timeout=30.0)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    test_suffix = uuid.uuid4().hex[:8]
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    invitation_id = uuid.uuid4()
    num_users = 50

    user_ids = [uuid.uuid4() for _ in range(num_users)]
    user_contexts = [
        type("UserCtx", (), {"id": uid, "email": f"concur_{test_suffix}_{idx}@synth.test"})()
        for idx, uid in enumerate(user_ids)
    ]
    all_seeded_user_ids = [owner_id] + user_ids

    main_exception = None
    cleanup_exception = None
    dispose_exception = None

    try:
        initial_deadlocks = await get_deadlock_count(engine)

        # Step 1: Seed workspace, owner, and 50 target users
        async with session_factory() as seed_session:
            workspace = Workspace(
                id=workspace_id,
                name=f"Concurrency 50 WS {test_suffix}",
                slug=f"concur50-{test_suffix}",
                public_id=f"CONCUR50-{test_suffix.upper()}",
                storage_prefix=f"storage_{test_suffix}",
                qdrant_namespace=f"qdrant_{test_suffix}",
                status=WorkspaceStatus.ACTIVE.value,
            )
            owner_user = User(
                id=owner_id,
                email=f"owner_{test_suffix}@synth.test",
                display_name="Concurrency 50 Owner",
                hashed_password="mock_hashed_password",
                role="admin",
                is_active=True,
                is_verified=True,
            )
            owner_member = WorkspaceMember(
                workspace_id=workspace_id,
                user_id=owner_id,
                role="OWNER",
                status=MemberStatus.ACTIVE.value,
                joined_at=datetime.now(UTC),
                is_deleted=False,
                version=1,
            )
            users_to_seed = [
                User(
                    id=uid,
                    email=uctx.email,
                    display_name=f"Concurrent User {idx}",
                    hashed_password="mock_hashed_password",
                    role="viewer",
                    is_active=True,
                    is_verified=True,
                )
                for idx, (uid, uctx) in enumerate(zip(user_ids, user_contexts))
            ]

            seed_session.add(workspace)
            seed_session.add(owner_user)
            seed_session.add(owner_member)
            seed_session.add_all(users_to_seed)
            await seed_session.commit()

        # Step 2: Seed reusable multi-user invitation link (is_legacy_bound=False, email=None)
        raw_token, token_selector, token_hash = generate_invitation_token()

        async with session_factory() as seed_session:
            invitation = WorkspaceInvitation(
                id=invitation_id,
                workspace_id=workspace_id,
                email=None,  # Reusable multi-user link
                role="MEMBER",
                token_hash=token_hash,
                token_selector=token_selector,
                status=InvitationStatus.PENDING.value,
                is_legacy_bound=False,
                invited_by_user_id=owner_id,
                version=1,
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
            seed_session.add(invitation)
            await seed_session.commit()

        # Step 3: Concurrently accept invitation across 50 independent sessions via Barrier
        barrier = asyncio.Barrier(num_users)
        dummy_email_provider = MagicMock()

        async def simulate_joiner(user_context: Any) -> dict[str, Any]:
            async with session_factory() as session:
                inv_repo = WorkspaceInvitationRepository(session)
                ws_repo = WorkspaceRepository(session)
                m_repo = WorkspaceMemberRepository(session)
                service = WorkspaceInvitationService(
                    invitation_repo=inv_repo,
                    member_repo=m_repo,
                    workspace_repo=ws_repo,
                    settings_repo=None,
                    email_provider=dummy_email_provider,
                )
                await wait_at_barrier(barrier)
                start_time = time.perf_counter()
                result = await service.accept_invitation(session, raw_token, user_context)
                latency = time.perf_counter() - start_time
                result["_latency"] = latency
                return result

        results = await asyncio.gather(
            *[simulate_joiner(uctx) for uctx in user_contexts],
            return_exceptions=True,
        )

        # Step 4: Verify 50 successful redemptions
        for idx, r in enumerate(results):
            if isinstance(r, Exception):
                raise AssertionError(f"Virtual user {idx} failed with {type(r).__name__}: {r}") from r
            assert r.get("success") is True, f"Virtual user {idx} redemption failed: {r}"
            assert r.get("role") == "MEMBER", f"Virtual user {idx} got non-MEMBER role: {r.get('role')}"
            assert str(r.get("workspace_id")) == str(workspace_id)

        # Step 5: Verify invitation remains PENDING
        async with session_factory() as verify_session:
            inv_res = await verify_session.execute(
                select(WorkspaceInvitation).where(WorkspaceInvitation.id == invitation_id)
            )
            persisted_inv = inv_res.scalar_one()
            assert persisted_inv.status == InvitationStatus.PENDING.value, (
                f"Reusable invitation must remain PENDING, got {persisted_inv.status}"
            )

            # Step 6: Verify exactly 50 WorkspaceMember rows created with role MEMBER
            m_res = await verify_session.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.role == "MEMBER",
                    WorkspaceMember.is_deleted == False,
                )
            )
            members = m_res.scalars().all()
            assert len(members) == 50, f"Expected 50 active MEMBER rows, found {len(members)}"

            # Step 7: Verify exactly 50 WorkspaceInvitationRedemption rows in ledger
            r_res = await verify_session.execute(
                select(WorkspaceInvitationRedemption).where(
                    WorkspaceInvitationRedemption.invitation_id == invitation_id
                )
            )
            redemptions = r_res.scalars().all()
            assert len(redemptions) == 50, f"Expected 50 redemption ledger rows, found {len(redemptions)}"

        # Step 8: Verify 0 deadlocks occurred during the drill
        final_deadlocks = await get_deadlock_count(engine)
        deadlock_delta = final_deadlocks - initial_deadlocks
        assert deadlock_delta == 0, f"Deadlocks detected during 50-user concurrent drill: {deadlock_delta}"

    except Exception as exc:
        main_exception = exc
    finally:
        # Failure-safe teardown: independent tracking of cleanup and engine disposal
        try:
            async with session_factory() as cleanup_session:
                await cleanup_session.execute(
                    text("DELETE FROM workspace_invitation_redemptions WHERE workspace_id = :wid;"),
                    {"wid": workspace_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM workspace_members WHERE workspace_id = :wid;"),
                    {"wid": workspace_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM workspace_invitations WHERE id = :inv_id;"),
                    {"inv_id": invitation_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM workspaces WHERE id = :wid;"),
                    {"wid": workspace_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM users WHERE id = ANY(:uids);"),
                    {"uids": all_seeded_user_ids},
                )
                await cleanup_session.commit()
        except Exception as c_exc:
            cleanup_exception = c_exc

        try:
            await engine.dispose()
        except Exception as d_exc:
            dispose_exception = d_exc

        failures = []
        if main_exception:
            failures.append(f"[Main Test Failure: {type(main_exception).__name__}: {main_exception}]")
        if cleanup_exception:
            failures.append(f"[Cleanup Failure: {type(cleanup_exception).__name__}: {cleanup_exception}]")
        if dispose_exception:
            failures.append(f"[Engine Disposal Failure: {type(dispose_exception).__name__}: {dispose_exception}]")

        if len(failures) > 1:
            primary = main_exception or cleanup_exception or dispose_exception
            raise RuntimeError(f"COMPOSITE DRILL FAILURE: {' AND '.join(failures)}") from primary
        elif main_exception:
            raise main_exception
        elif cleanup_exception:
            raise cleanup_exception
        elif dispose_exception:
            raise dispose_exception


@pytest.mark.asyncio
async def test_50_user_concurrent_repeat_redemptions(staging_db_url):
    """Drill 2: 50 existing members simultaneously re-redeem reusable link, asserting idempotent ALREADY_MEMBER."""
    engine = create_async_engine(staging_db_url, pool_size=60, max_overflow=20, pool_timeout=30.0)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    test_suffix = uuid.uuid4().hex[:8]
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    invitation_id = uuid.uuid4()
    num_users = 50

    user_ids = [uuid.uuid4() for _ in range(num_users)]
    user_contexts = [
        type("UserCtx", (), {"id": uid, "email": f"repeat_{test_suffix}_{idx}@synth.test"})()
        for idx, uid in enumerate(user_ids)
    ]
    all_seeded_user_ids = [owner_id] + user_ids

    main_exception = None
    cleanup_exception = None
    dispose_exception = None

    try:
        # Step 1: Seed workspace, owner, 50 users, 50 already-active memberships, and reusable invitation
        async with session_factory() as seed_session:
            workspace = Workspace(
                id=workspace_id,
                name=f"Repeat Concur 50 WS {test_suffix}",
                slug=f"repeat-concur50-{test_suffix}",
                public_id=f"REPCON50-{test_suffix.upper()}",
                storage_prefix=f"storage_rep_{test_suffix}",
                qdrant_namespace=f"qdrant_rep_{test_suffix}",
                status=WorkspaceStatus.ACTIVE.value,
            )
            owner_user = User(
                id=owner_id,
                email=f"owner_rep_{test_suffix}@synth.test",
                display_name="Repeat Owner",
                hashed_password="mock_hashed_password",
                role="admin",
                is_active=True,
                is_verified=True,
            )
            seed_session.add_all([workspace, owner_user])

            users_to_seed = [
                User(
                    id=uid,
                    email=uctx.email,
                    display_name=f"Repeat User {idx}",
                    hashed_password="mock_hashed_password",
                    role="viewer",
                    is_active=True,
                    is_verified=True,
                )
                for idx, (uid, uctx) in enumerate(zip(user_ids, user_contexts))
            ]
            members_to_seed = [
                WorkspaceMember(
                    workspace_id=workspace_id,
                    user_id=uid,
                    role="MEMBER",
                    status=MemberStatus.ACTIVE.value,
                    joined_at=datetime.now(UTC),
                    is_deleted=False,
                    version=1,
                )
                for uid in user_ids
            ]
            seed_session.add_all(users_to_seed)
            seed_session.add_all(members_to_seed)
            await seed_session.commit()

        raw_token, token_selector, token_hash = generate_invitation_token()

        async with session_factory() as seed_session:
            invitation = WorkspaceInvitation(
                id=invitation_id,
                workspace_id=workspace_id,
                email=None,
                role="MEMBER",
                token_hash=token_hash,
                token_selector=token_selector,
                status=InvitationStatus.PENDING.value,
                is_legacy_bound=False,
                invited_by_user_id=owner_id,
                version=1,
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
            seed_session.add(invitation)
            await seed_session.commit()

        # Step 2: Concurrently re-redeem via Barrier
        barrier = asyncio.Barrier(num_users)
        dummy_email_provider = MagicMock()

        async def simulate_repeat_joiner(user_context: Any) -> dict[str, Any]:
            async with session_factory() as session:
                service = WorkspaceInvitationService(
                    invitation_repo=WorkspaceInvitationRepository(session),
                    member_repo=WorkspaceMemberRepository(session),
                    workspace_repo=WorkspaceRepository(session),
                    settings_repo=None,
                    email_provider=dummy_email_provider,
                )
                await wait_at_barrier(barrier)
                return await service.accept_invitation(session, raw_token, user_context)

        results = await asyncio.gather(
            *[simulate_repeat_joiner(uctx) for uctx in user_contexts],
            return_exceptions=True,
        )

        # Step 3: Assert all 50 return ALREADY_MEMBER status
        for idx, r in enumerate(results):
            if isinstance(r, Exception):
                raise AssertionError(f"Repeat user {idx} threw unexpected error: {type(r).__name__}: {r}") from r
            assert r.get("status") == "ALREADY_MEMBER", (
                f"Expected ALREADY_MEMBER idempotent status, got: {r}"
            )

        # Step 4: Assert active membership count remains exactly 50 (zero duplicates)
        async with session_factory() as verify_session:
            m_res = await verify_session.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.is_deleted == False,
                )
            )
            active_members = m_res.scalars().all()
            assert len(active_members) == 50, f"Expected 50 active members, found {len(active_members)}"

    except Exception as exc:
        main_exception = exc
    finally:
        try:
            async with session_factory() as cleanup_session:
                await cleanup_session.execute(
                    text("DELETE FROM workspace_invitation_redemptions WHERE workspace_id = :wid;"),
                    {"wid": workspace_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM workspace_members WHERE workspace_id = :wid;"),
                    {"wid": workspace_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM workspace_invitations WHERE id = :inv_id;"),
                    {"inv_id": invitation_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM workspaces WHERE id = :wid;"),
                    {"wid": workspace_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM users WHERE id = ANY(:uids);"),
                    {"uids": all_seeded_user_ids},
                )
                await cleanup_session.commit()
        except Exception as c_exc:
            cleanup_exception = c_exc

        try:
            await engine.dispose()
        except Exception as d_exc:
            dispose_exception = d_exc

        failures = []
        if main_exception:
            failures.append(f"[Main Test Failure: {type(main_exception).__name__}: {main_exception}]")
        if cleanup_exception:
            failures.append(f"[Cleanup Failure: {type(cleanup_exception).__name__}: {cleanup_exception}]")
        if dispose_exception:
            failures.append(f"[Engine Disposal Failure: {type(dispose_exception).__name__}: {dispose_exception}]")

        if len(failures) > 1:
            primary = main_exception or cleanup_exception or dispose_exception
            raise RuntimeError(f"COMPOSITE DRILL FAILURE: {' AND '.join(failures)}") from primary
        elif main_exception:
            raise main_exception
        elif cleanup_exception:
            raise cleanup_exception
        elif dispose_exception:
            raise dispose_exception


@pytest.mark.asyncio
async def test_50_user_concurrent_join_code_usage_increment(staging_db_url):
    """Drill 3: 50 concurrent tasks invoke atomic increment_usage(), asserting exact +50 counter delta."""
    engine = create_async_engine(staging_db_url, pool_size=60, max_overflow=20, pool_timeout=30.0)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    test_suffix = uuid.uuid4().hex[:8]
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    code_id = uuid.uuid4()
    concurrency_count = 50

    main_exception = None
    cleanup_exception = None
    dispose_exception = None

    try:
        # Step 1: Seed workspace, owner, and join code with use_count = 0
        async with session_factory() as seed_session:
            workspace = Workspace(
                id=workspace_id,
                name=f"Join Code Concur WS {test_suffix}",
                slug=f"jc-concur-{test_suffix}",
                public_id=f"JCCON-{test_suffix.upper()}",
                storage_prefix=f"storage_jc_{test_suffix}",
                qdrant_namespace=f"qdrant_jc_{test_suffix}",
                status=WorkspaceStatus.ACTIVE.value,
            )
            owner_user = User(
                id=owner_id,
                email=f"owner_jc_{test_suffix}@synth.test",
                display_name="JC Owner",
                hashed_password="mock_hashed_password",
                role="admin",
                is_active=True,
                is_verified=True,
            )
            join_code = WorkspaceJoinCode(
                id=code_id,
                workspace_id=workspace_id,
                created_by_user_id=owner_id,
                operational_custodian_user_id=None,
                code_hash="mock_hash_v2",
                lookup_pepper_version="v2",
                encrypted_code="mock_encrypted_code",
                encryption_key_version="enc_v1",
                code_display="VR-JC****",
                is_enabled=True,
                is_legacy=False,
                expires_at=datetime.now(UTC) + timedelta(days=30),
                use_count=0,
                version=1,
            )
            seed_session.add_all([workspace, owner_user, join_code])
            await seed_session.commit()

        # Step 2: 50 concurrent tasks invoke increment_usage() via Barrier
        barrier = asyncio.Barrier(concurrency_count)

        async def worker_increment():
            async with session_factory() as session:
                repo = WorkspaceJoinCodeRepository(session)
                await wait_at_barrier(barrier)
                await repo.increment_usage(session, code_id)
                await session.commit()

        results = await asyncio.gather(
            *[worker_increment() for _ in range(concurrency_count)],
            return_exceptions=True,
        )

        for idx, r in enumerate(results):
            if isinstance(r, Exception):
                raise AssertionError(f"Increment worker {idx} failed: {type(r).__name__}: {r}") from r

        # Step 3: Verify initial counter (0) + 50 = exactly 50 in database
        async with session_factory() as verify_session:
            jc_res = await verify_session.execute(
                select(WorkspaceJoinCode).where(WorkspaceJoinCode.id == code_id)
            )
            updated_code = jc_res.scalar_one()
            assert updated_code.use_count == 50, (
                f"Expected use_count delta of +50 (final 50), found {updated_code.use_count}"
            )

    except Exception as exc:
        main_exception = exc
    finally:
        try:
            async with session_factory() as cleanup_session:
                await cleanup_session.execute(
                    text("DELETE FROM workspace_join_codes WHERE id = :code_id;"),
                    {"code_id": code_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM workspaces WHERE id = :wid;"),
                    {"wid": workspace_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM users WHERE id = :uid;"),
                    {"uid": owner_id},
                )
                await cleanup_session.commit()
        except Exception as c_exc:
            cleanup_exception = c_exc

        try:
            await engine.dispose()
        except Exception as d_exc:
            dispose_exception = d_exc

        failures = []
        if main_exception:
            failures.append(f"[Main Test Failure: {type(main_exception).__name__}: {main_exception}]")
        if cleanup_exception:
            failures.append(f"[Cleanup Failure: {type(cleanup_exception).__name__}: {cleanup_exception}]")
        if dispose_exception:
            failures.append(f"[Engine Disposal Failure: {type(dispose_exception).__name__}: {dispose_exception}]")

        if len(failures) > 1:
            primary = main_exception or cleanup_exception or dispose_exception
            raise RuntimeError(f"COMPOSITE DRILL FAILURE: {' AND '.join(failures)}") from primary
        elif main_exception:
            raise main_exception
        elif cleanup_exception:
            raise cleanup_exception
        elif dispose_exception:
            raise dispose_exception


@pytest.mark.asyncio
async def test_5_worker_outbox_claiming_contention(staging_db_url):
    """Drill 4: 5 concurrent asyncio workers contend for 50 pending outbox records using FOR UPDATE SKIP LOCKED.
    
    CLASSIFICATION: Database-Level Concurrency & Locking Verification Drill.
    
    ARCHITECTURAL LIMITATION & BOUNDARY:
    The application task _async_dispatch_notification_outbox() in join_code_notifications.py
    hardcodes the global get_session_factory() (targeting default port 5432) without parameterization,
    and executes an unversioned SELECT without FOR UPDATE SKIP LOCKED.
    Because governance rules strictly prohibit mutating production source files, this test directly
    exercises PostgreSQL row-level locking semantics (SELECT ... FOR UPDATE SKIP LOCKED) on the real
    NotificationOutbox table in schema 'public' on port 5434 using 5 concurrent asyncio worker coroutines
    (not OS processes). This is an engine-level locking verification drill, not a production Celery
    worker verification.
    """
    engine = create_async_engine(staging_db_url, pool_size=60, max_overflow=20, pool_timeout=30.0)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    test_suffix = uuid.uuid4().hex[:8]
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    code_id = uuid.uuid4()
    num_outbox = 50
    num_workers = 5

    outbox_ids = [uuid.uuid4() for _ in range(num_outbox)]
    main_exception = None
    cleanup_exception = None
    dispose_exception = None

    try:
        # Step 1: Seed workspace, owner, join code, and 50 PENDING outbox records
        async with session_factory() as seed_session:
            workspace = Workspace(
                id=workspace_id,
                name=f"Outbox Concur WS {test_suffix}",
                slug=f"ob-concur-{test_suffix}",
                public_id=f"OBCON-{test_suffix.upper()}",
                storage_prefix=f"storage_ob_{test_suffix}",
                qdrant_namespace=f"qdrant_ob_{test_suffix}",
                status=WorkspaceStatus.ACTIVE.value,
            )
            owner_user = User(
                id=owner_id,
                email=f"owner_ob_{test_suffix}@synth.test",
                display_name="Outbox Owner",
                hashed_password="mock_hashed_password",
                role="admin",
                is_active=True,
                is_verified=True,
            )
            join_code = WorkspaceJoinCode(
                id=code_id,
                workspace_id=workspace_id,
                created_by_user_id=owner_id,
                code_hash="mock_hash_ob",
                lookup_pepper_version="v2",
                encrypted_code="mock_encrypted_ob",
                encryption_key_version="enc_v1",
                code_display="VR-OB****",
                is_enabled=True,
                is_legacy=False,
                expires_at=datetime.now(UTC) + timedelta(days=30),
                use_count=0,
                version=1,
            )
            seed_session.add_all([workspace, owner_user, join_code])

            outbox_entries = [
                NotificationOutbox(
                    id=oid,
                    join_code_id=code_id,
                    join_code_version=1,
                    workspace_id=workspace_id,
                    recipient_user_id=owner_id,
                    checkpoint="24H",
                    channel="EMAIL",
                    status="PENDING",
                    idempotency_key=f"outbox_drill_{test_suffix}_{idx}",
                    scheduled_for=datetime.now(UTC),
                )
                for idx, oid in enumerate(outbox_ids)
            ]
            seed_session.add_all(outbox_entries)
            await seed_session.commit()

        # Step 2: 5 concurrent asyncio worker coroutines claim records using FOR UPDATE SKIP LOCKED
        barrier = asyncio.Barrier(num_workers)
        worker_claimed_map: dict[str, list[uuid.UUID]] = {f"worker_{w}": [] for w in range(num_workers)}

        async def worker_claim_loop(worker_id: str):
            await wait_at_barrier(barrier)
            batch_size = 10
            now = datetime.now(UTC)
            lease_duration = timedelta(minutes=5)

            while True:
                async with session_factory() as session:
                    # Select pending rows with pessimistic locking and skip locked
                    stmt = (
                        select(NotificationOutbox)
                        .where(
                            NotificationOutbox.workspace_id == workspace_id,
                            NotificationOutbox.status == "PENDING",
                        )
                        .with_for_update(skip_locked=True)
                        .limit(batch_size)
                    )
                    res = await session.execute(stmt)
                    claimed_batch = res.scalars().all()

                    if not claimed_batch:
                        break

                    for entry in claimed_batch:
                        entry.status = "CLAIMED"
                        entry.lease_expires_at = now + lease_duration
                        session.add(entry)
                        worker_claimed_map[worker_id].append(entry.id)

                    await session.commit()
                # Yield control briefly to ensure natural contention interleaving
                await asyncio.sleep(0.01)

        worker_tasks = [worker_claim_loop(f"worker_{w}") for w in range(num_workers)]
        await asyncio.gather(*worker_tasks)

        # Step 3: Verification
        all_claimed_ids = []
        for w_id, claimed_ids in worker_claimed_map.items():
            all_claimed_ids.extend(claimed_ids)

        assert len(all_claimed_ids) == num_outbox, (
            f"Expected {num_outbox} total claimed outbox rows, got {len(all_claimed_ids)}"
        )

        unique_claimed_ids = set(all_claimed_ids)
        assert len(unique_claimed_ids) == num_outbox, (
            f"Duplicate claims detected! Total claimed {len(all_claimed_ids)}, unique {len(unique_claimed_ids)}"
        )

        for w1 in worker_claimed_map:
            for w2 in worker_claimed_map:
                if w1 != w2:
                    overlap = set(worker_claimed_map[w1]).intersection(set(worker_claimed_map[w2]))
                    assert len(overlap) == 0, f"Worker {w1} and {w2} both claimed rows: {overlap}"

        # Step 4: Verify in database that all 50 entries have status CLAIMED
        async with session_factory() as verify_session:
            db_res = await verify_session.execute(
                select(func.count(NotificationOutbox.id)).where(
                    NotificationOutbox.id.in_(outbox_ids),
                    NotificationOutbox.status == "CLAIMED",
                )
            )
            count_claimed = db_res.scalar_one()
            assert count_claimed == num_outbox, (
                f"Expected {num_outbox} entries in CLAIMED state in database, found {count_claimed}"
            )

    except Exception as exc:
        main_exception = exc
    finally:
        try:
            async with session_factory() as cleanup_session:
                await cleanup_session.execute(
                    text("DELETE FROM notification_outbox WHERE id = ANY(:oids);"),
                    {"oids": outbox_ids},
                )
                await cleanup_session.execute(
                    text("DELETE FROM workspace_join_codes WHERE id = :code_id;"),
                    {"code_id": code_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM workspaces WHERE id = :wid;"),
                    {"wid": workspace_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM users WHERE id = :uid;"),
                    {"uid": owner_id},
                )
                await cleanup_session.commit()
        except Exception as c_exc:
            cleanup_exception = c_exc

        try:
            await engine.dispose()
        except Exception as d_exc:
            dispose_exception = d_exc

        failures = []
        if main_exception:
            failures.append(f"[Main Test Failure: {type(main_exception).__name__}: {main_exception}]")
        if cleanup_exception:
            failures.append(f"[Cleanup Failure: {type(cleanup_exception).__name__}: {cleanup_exception}]")
        if dispose_exception:
            failures.append(f"[Engine Disposal Failure: {type(dispose_exception).__name__}: {dispose_exception}]")

        if len(failures) > 1:
            primary = main_exception or cleanup_exception or dispose_exception
            raise RuntimeError(f"COMPOSITE DRILL FAILURE: {' AND '.join(failures)}") from primary
        elif main_exception:
            raise main_exception
        elif cleanup_exception:
            raise cleanup_exception
        elif dispose_exception:
            raise dispose_exception
