"""Genuine PostgreSQL Multi-Session Concurrency Integration Test for Workspace Invitations.

Governed by Section 2 Remediation Requirement 2:
Verifies that when two distinct valid invitations target the same workspace and user,
and both acceptance attempts execute concurrently across separate database sessions:
1. The database unique index 'uq_workspace_members_active_user' prevents duplicate active memberships.
2. The losing transaction rolls back correctly.
3. The application returns the intended conflict response (HTTP 409 / InvitationConflictError).
4. Exactly one active membership exists afterward.

INFRASTRUCTURE GOVERNANCE:
- Executes against a real PostgreSQL database with isolated test sessions.
- If the host PostgreSQL service or Docker engine is offline, the test strictly skips
  and reports the exact infrastructure blocker without substituting mocks or fabricating results.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import get_settings
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_invitation import (
    InvitationStatus,
    WorkspaceInvitation,
)
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_invitation import WorkspaceInvitationRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.services.workspace.invitation_service import (
    InvitationConflictError,
    WorkspaceInvitationService,
    generate_invitation_token,
)


class SynchronizedMemberRepository(WorkspaceMemberRepository):
    """
    Test-only repository wrapper enforcing deterministic concurrency at the
    database insertion boundary.
    """

    def __init__(
        self,
        session: AsyncSession,
        barrier: asyncio.Barrier,
        pre_check_observations: list,
    ):
        super().__init__(session)
        self.barrier = barrier
        self.pre_check_observations = pre_check_observations

    async def get_membership(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        include_suspended: bool = True,
        include_deleted: bool = False,
    ) -> WorkspaceMember | None:
        result = await super().get_membership(
            workspace_id=workspace_id,
            user_id=user_id,
            include_suspended=include_suspended,
            include_deleted=include_deleted,
        )
        self.pre_check_observations.append(result)
        await asyncio.wait_for(self.barrier.wait(), timeout=5.0)
        return result


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


@pytest.mark.asyncio
async def test_genuine_concurrent_invitation_acceptance_postgres():
    """Genuine PostgreSQL concurrency test using separate database sessions and concurrent transactions."""
    settings = get_settings()
    db_url = settings.database.url

    is_available, error_msg = await check_postgres_availability(db_url)
    if not is_available:
        pytest.skip(
            f"INFRASTRUCTURE BLOCKER: PostgreSQL daemon offline at {db_url} ({error_msg}). "
            f"Genuine multi-session concurrency integration test requires an active PostgreSQL instance."
        )

    # Initialize isolated engine and sessionmaker
    engine = create_async_engine(db_url, pool_size=5, max_overflow=5)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    test_suffix = uuid.uuid4().hex[:8]
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    user_id = uuid.uuid4()
    target_email = f"concurrent_{test_suffix}@example.com"

    # Step 1: Seed test workspace, owner, and target user
    async with session_factory() as seed_session:
        workspace = Workspace(
            id=workspace_id,
            name=f"Concurrency WS {test_suffix}",
            slug=f"concurrent-{test_suffix}",
            public_id=f"CONCUR-{test_suffix.upper()}",
            storage_prefix=f"storage_{test_suffix}",
            qdrant_namespace=f"qdrant_{test_suffix}",
            status=WorkspaceStatus.ACTIVE.value,
        )
        owner_user = User(
            id=owner_id,
            email=f"owner_{test_suffix}@example.com",
            display_name="Concurrency Owner",
            hashed_password="mock_hashed_password",
            role="admin",
            is_active=True,
            is_verified=True,
        )
        target_user = User(
            id=user_id,
            email=target_email,
            display_name="Target User",
            hashed_password="mock_hashed_password",
            role="viewer",
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
        seed_session.add_all([workspace, owner_user, target_user, owner_member])
        await seed_session.commit()

    # Step 2: Create two distinct, valid invitations for the same workspace and user
    raw_token_1, selector_1, hash_1 = generate_invitation_token()
    raw_token_2, selector_2, hash_2 = generate_invitation_token()

    invitation_1_id = uuid.uuid4()
    invitation_2_id = uuid.uuid4()

    async with session_factory() as seed_session:
        inv1 = WorkspaceInvitation(
            id=invitation_1_id,
            workspace_id=workspace_id,
            email=target_email,
            role="MEMBER",
            token_hash=hash_1,
            token_selector=selector_1,
            status=InvitationStatus.PENDING.value,
            invited_by_user_id=owner_id,
            version=1,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        inv2 = WorkspaceInvitation(
            id=invitation_2_id,
            workspace_id=workspace_id,
            email=target_email,
            role="MEMBER",
            token_hash=hash_2,
            token_selector=selector_2,
            status=InvitationStatus.PENDING.value,
            invited_by_user_id=owner_id,
            version=1,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        seed_session.add_all([inv1, inv2])
        await seed_session.commit()

    # Step 3: Concurrently accept both invitations from separate sessions with barrier synchronization
    barrier = asyncio.Barrier(2)
    pre_check_observations = []
    dummy_email_provider = MagicMock()

    async def run_worker(raw_token: str) -> dict:
        async with session_factory() as session:
            inv_repo = WorkspaceInvitationRepository(session)
            ws_repo = WorkspaceRepository(session)
            m_repo = SynchronizedMemberRepository(session, barrier, pre_check_observations)
            service = WorkspaceInvitationService(
                invitation_repo=inv_repo,
                member_repo=m_repo,
                workspace_repo=ws_repo,
                settings_repo=None,
                email_provider=dummy_email_provider,
            )
            user_ctx = type("UserCtx", (), {"id": user_id, "email": target_email})()
            try:
                return await service.accept_invitation(session, raw_token, user_ctx)
            except InvitationConflictError as exc:
                exc._session_rolled_back = not session.in_transaction()
                raise

    results = await asyncio.gather(
        run_worker(raw_token_1),
        run_worker(raw_token_2),
        return_exceptions=True,
    )

    try:
        # Step 4: Verify outcomes and guard against unexpected worker exceptions
        for r in results:
            if isinstance(r, Exception) and not isinstance(r, InvitationConflictError):
                raise AssertionError(f"Worker encountered unexpected failure: {type(r).__name__}: {r}") from r

        assert len(pre_check_observations) == 2, f"Expected 2 pre-check queries, got {len(pre_check_observations)}"
        assert all(obs is None for obs in pre_check_observations), (
            f"Both workers must observe no active membership prior to insert: {pre_check_observations}"
        )

        successes = [r for r in results if isinstance(r, dict) and r.get("success") is True]
        conflicts = [r for r in results if isinstance(r, InvitationConflictError)]

        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}: {results}"
        assert len(conflicts) == 1, f"Expected 1 conflict, got {len(conflicts)}: {results}"

        conflict_err = conflicts[0]
        assert str(conflict_err) == "You are already an active member of this workspace.", (
            f"Expected DB unique constraint rejection message, got: {conflict_err}"
        )
        assert conflict_err.__cause__ is not None, "Conflict must be chained from underlying IntegrityError"

        # Verify driver-level SQLSTATE 23505 and constraint name uq_workspace_members_active_user
        orig_err = getattr(conflict_err.__cause__, "orig", None)
        sqlstate = getattr(orig_err, "sqlstate", None) or getattr(orig_err, "pgcode", None)
        if sqlstate:
            assert sqlstate == "23505", f"Expected SQLSTATE 23505, got {sqlstate}"
        else:
            assert "23505" in str(conflict_err.__cause__), f"Expected 23505 in error, got {conflict_err.__cause__}"

        constraint_name = getattr(orig_err, "constraint_name", None)
        if constraint_name:
            assert constraint_name == "uq_workspace_members_active_user", (
                f"Expected constraint 'uq_workspace_members_active_user', got {constraint_name}"
            )
        else:
            assert "uq_workspace_members_active_user" in str(conflict_err.__cause__).lower()

        # Verify losing session was rolled back before closing
        assert getattr(conflict_err, "_session_rolled_back", False) is True, (
            "Losing transaction must be rolled back before session close"
        )

        # Step 5: Verify database state via independent read session
        async with session_factory() as verify_session:
            members_stmt = select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.is_deleted == False,
            )
            active_members = (await verify_session.execute(members_stmt)).scalars().all()

            # The database unique partial index must guarantee exactly one active membership
            assert len(active_members) == 1, f"Expected 1 active member, found {len(active_members)}"
            assert active_members[0].role == "MEMBER"
            assert active_members[0].is_deleted is False

            total_stmt = select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
            total_members = (await verify_session.execute(total_stmt)).scalars().all()
            assert len(total_members) == 1, f"Expected exactly 1 total member row, found {len(total_members)}"

    finally:
        # Step 6: Isolated cleanup
        async with session_factory() as cleanup_session:
            await cleanup_session.execute(
                text("DELETE FROM workspace_members WHERE workspace_id = :wid"), {"wid": workspace_id}
            )
            await cleanup_session.execute(
                text("DELETE FROM workspace_invitations WHERE workspace_id = :wid"), {"wid": workspace_id}
            )
            await cleanup_session.execute(
                text("DELETE FROM workspaces WHERE id = :wid"), {"wid": workspace_id}
            )
            await cleanup_session.execute(
                text("DELETE FROM users WHERE id IN (:u1, :u2)"), {"u1": owner_id, "u2": user_id}
            )
            await cleanup_session.commit()
        await engine.dispose()
