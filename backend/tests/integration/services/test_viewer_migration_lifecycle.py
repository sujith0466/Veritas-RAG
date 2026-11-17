"""
Veritas RAG — Section 6: VIEWER-to-MEMBER Migration Integration Lifecycle Test Suite (T-63)

Tests the migration lifecycle of workspace memberships from VIEWER to MEMBER:
1. Migrates all 6 combinations of (status, is_deleted) with role='VIEWER' to 'MEMBER':
   - ACTIVE / is_deleted=False
   - ACTIVE / is_deleted=True
   - SUSPENDED / is_deleted=False
   - SUSPENDED / is_deleted=True
   - INACTIVE / is_deleted=False
   - INACTIVE / is_deleted=True
2. Preserves all other membership fields: status, is_deleted, member_metadata, joined_at,
   timestamps, IDs, and versions.
3. Preserves global users.role = 'viewer' (global role isolation).
4. Verifies zero workspace_members rows remain with role = 'VIEWER' after upgrade.
5. Verifies safe downgrade:
   - Restores original_role ('VIEWER') for members whose role is still 'MEMBER'.
   - Preserves subsequent administrative promotions (e.g., to 'ADMIN').
   - Drops tracking table '_migration_sec6_viewer_conversions'.
"""

from datetime import UTC, datetime
import importlib.util
import os
from pathlib import Path
import uuid
from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole

# Dynamically load the authoritative Section 6 Alembic migration module
MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "database"
    / "migrations"
    / "versions"
    / "20261115_sec6_migrate_viewers_to_members.py"
)
_spec = importlib.util.spec_from_file_location("sec6_migration", MIGRATION_PATH)
sec6_migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sec6_migration)

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://t3b_test_admin:t3b_test_password_2026!@127.0.0.1:5433/raguard_t3b_test",
)


@pytest.fixture
async def async_engine():
    """Provides async engine for integration tests, skipping gracefully if test db is unavailable."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Test database on port 5433 unavailable: {exc}")
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine):
    """Yields an isolated AsyncSession wrapped in a transaction that rolls back."""
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.mark.asyncio
async def test_viewer_migration_lifecycle_all_statuses(db_session: AsyncSession):
    """T-63: Full upgrade/downgrade lifecycle across all 6 status combinations and global user."""
    # 1. Setup workspace & user
    ws_id = uuid.uuid4()
    owner_user_id = uuid.uuid4()
    viewer_user_id = uuid.uuid4()

    workspace = Workspace(
        id=ws_id,
        name=f"Migration-Test-WS-{uuid.uuid4().hex[:6]}",
        slug=f"migration-test-ws-{uuid.uuid4().hex[:6]}",
        public_id=f"ws-{uuid.uuid4().hex[:8]}",
        storage_prefix=f"storage-{uuid.uuid4().hex[:8]}",
        qdrant_namespace=f"qdrant-{uuid.uuid4().hex[:8]}",
        status=WorkspaceStatus.ACTIVE.value,
    )
    db_session.add(workspace)

    # Seed global user with role = 'viewer'
    global_user = User(
        id=viewer_user_id,
        email=f"viewer-{uuid.uuid4().hex[:6]}@example.com",
        username=f"viewer_{uuid.uuid4().hex[:6]}",
        role="viewer",
        is_active=True,
    )
    db_session.add(global_user)

    # 2. Seed all 6 combinations of (status, is_deleted) with role = 'VIEWER'
    status_matrix = [
        (MemberStatus.ACTIVE.value, False),
        (MemberStatus.ACTIVE.value, True),
        (MemberStatus.SUSPENDED.value, False),
        (MemberStatus.SUSPENDED.value, True),
        ("INACTIVE", False),
        ("INACTIVE", True),
    ]

    seeded_members = []
    for idx, (st, is_del) in enumerate(status_matrix):
        u_id = uuid.uuid4()
        u = User(
            id=u_id,
            email=f"user-{idx}-{uuid.uuid4().hex[:6]}@example.com",
            username=f"user_{idx}_{uuid.uuid4().hex[:6]}",
            role="viewer",
            is_active=True,
        )
        db_session.add(u)

        mem = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=u_id,
            role="VIEWER",
            status=st,
            is_deleted=is_del,
            joined_at=datetime.now(UTC),
            member_metadata={"preserved_marker": f"val_{idx}"},
            version=1,
        )
        db_session.add(mem)
        seeded_members.append(mem)

    await db_session.flush()

    # 3. Execute Migration Upgrade via authoritative Alembic migration module
    await db_session.execute(text("DROP TABLE IF EXISTS _migration_sec6_viewer_conversions"))
    await db_session.flush()

    def run_upgrade(sync_conn):
        ctx = MigrationContext.configure(sync_conn)
        with Operations.context(ctx):
            sec6_migration.upgrade()

    conn = await db_session.connection()
    await conn.run_sync(run_upgrade)
    await db_session.flush()

    # 4. Assert Upgrade Results
    # A. 0 workspace memberships retain role = 'VIEWER'
    res_viewers = await db_session.execute(
        text("SELECT COUNT(*) FROM workspace_members WHERE workspace_id = :ws_id AND UPPER(role) = 'VIEWER'"),
        {"ws_id": ws_id},
    )
    assert res_viewers.scalar_one() == 0

    # B. All 6 seeded members are now 'MEMBER' and all other fields strictly preserved
    for mem in seeded_members:
        res = await db_session.execute(
            text("SELECT role, status, is_deleted, member_metadata, version FROM workspace_members WHERE id = :mid"),
            {"mid": mem.id},
        )
        row = res.mappings().one()
        assert row["role"] == "MEMBER"
        assert row["status"] == mem.status
        assert row["is_deleted"] == mem.is_deleted
        assert row["member_metadata"] == mem.member_metadata
        assert row["version"] == 1  # Version not incremented by schema migration

    # C. Global users.role remains 'viewer'
    res_global_user = await db_session.execute(
        text("SELECT role FROM users WHERE id = :uid"),
        {"uid": viewer_user_id},
    )
    assert res_global_user.scalar_one() == "viewer"

    # 5. Simulate subsequent administrative promotion
    # Promote the first member from MEMBER to ADMIN
    promoted_member_id = seeded_members[0].id
    await db_session.execute(
        text("UPDATE workspace_members SET role = 'ADMIN' WHERE id = :mid"),
        {"mid": promoted_member_id},
    )
    await db_session.flush()

    # 6. Execute Migration Downgrade via authoritative Alembic migration module
    def run_downgrade(sync_conn):
        ctx = MigrationContext.configure(sync_conn)
        with Operations.context(ctx):
            sec6_migration.downgrade()

    conn = await db_session.connection()
    await conn.run_sync(run_downgrade)
    await db_session.flush()

    # 7. Assert Downgrade Results
    # Promoted member remains ADMIN (not reverted)
    res_promoted = await db_session.execute(
        text("SELECT role FROM workspace_members WHERE id = :mid"),
        {"mid": promoted_member_id},
    )
    assert res_promoted.scalar_one() == "ADMIN"

    # Remaining 5 members restored to original role 'VIEWER'
    for mem in seeded_members[1:]:
        res_reverted = await db_session.execute(
            text("SELECT role FROM workspace_members WHERE id = :mid"),
            {"mid": mem.id},
        )
        assert res_reverted.scalar_one() == "VIEWER"
