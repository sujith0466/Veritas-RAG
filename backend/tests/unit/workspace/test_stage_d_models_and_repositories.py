"""Unit tests for Stage D: ORM Domain Models & Repositories.

Verifies:
- WorkspaceFormerOwnerDeparture entity mapping, enums, to_dict().
- WorkspaceOwnershipTransfer email snapshot columns and relationships.
- Secure Vault entities (OfficerSigningKey, ActionNonce, RedactionExecutionFence).
- WorkspaceFormerOwnerDepartureRepository and WorkspaceOwnershipTransferRepository query construction.
- Live database ORM select parity on isolated port 5433.
"""

from datetime import UTC, datetime
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.models.entities.secure_vault import (
    ActionNonce,
    OfficerSigningKey,
    RedactionExecutionFence,
)
from backend.models.entities.workspace_former_owner_departure import (
    FormerOwnerDepartureType,
    WorkspaceFormerOwnerDeparture,
)
from backend.models.entities.workspace_ownership_transfer import (
    TransferStatus,
    WorkspaceOwnershipTransfer,
)
from backend.repositories.workspace_former_owner_departure import (
    WorkspaceFormerOwnerDepartureRepository,
)
from backend.repositories.workspace_ownership_transfer import (
    WorkspaceOwnershipTransferRepository,
)

TEST_DB_URL = "postgresql+asyncpg://t3b_test_admin:t3b_test_password_2026!@127.0.0.1:5433/raguard_t3b_test"


def test_former_owner_departure_model_instantiation():
    """Verify WorkspaceFormerOwnerDeparture model attributes and enum validity."""
    now = datetime.now(UTC)
    dep_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    former_owner_id = uuid.uuid4()
    transfer_id = uuid.uuid4()
    confirmed_by_id = uuid.uuid4()

    departure = WorkspaceFormerOwnerDeparture(
        id=dep_id,
        workspace_id=ws_id,
        former_owner_id=former_owner_id,
        transfer_id=transfer_id,
        departure_type=FormerOwnerDepartureType.VOLUNTARY_LEAVE.value,
        former_role="OWNER",
        retained_role=None,
        departure_confirmed_at=now,
        confirmed_by_user_id=confirmed_by_id,
        departure_notes="Former owner left voluntarily",
        created_at=now,
    )

    assert departure.id == dep_id
    assert departure.workspace_id == ws_id
    assert departure.former_owner_id == former_owner_id
    assert departure.transfer_id == transfer_id
    assert departure.departure_type == "VOLUNTARY_LEAVE"
    assert departure.former_role == "OWNER"
    assert departure.retained_role is None
    assert departure.departure_confirmed_at == now
    assert departure.confirmed_by_user_id == confirmed_by_id

    d_dict = departure.to_dict()
    assert d_dict["id"] == str(dep_id)
    assert d_dict["departure_type"] == "VOLUNTARY_LEAVE"
    assert d_dict["former_role"] == "OWNER"
    assert d_dict["retained_role"] is None


def test_transfer_model_has_snapshot_columns():
    """Verify WorkspaceOwnershipTransfer model contains snapshot columns."""
    t = WorkspaceOwnershipTransfer(
        workspace_id=uuid.uuid4(),
        nominated_by_user_id=uuid.uuid4(),
        nominee_user_id=uuid.uuid4(),
        status=TransferStatus.PENDING.value,
        expires_at=datetime.now(UTC),
        current_owner_email_snapshot="owner@raguard.test",
        nominated_user_email_snapshot="nominee@raguard.test",
    )
    assert t.current_owner_email_snapshot == "owner@raguard.test"
    assert t.nominated_user_email_snapshot == "nominee@raguard.test"
    assert hasattr(t, "former_owner_departure")


def test_vault_entities_table_args():
    """Verify vault entities are explicitly mapped to secure_vault schema."""
    assert OfficerSigningKey.__table__.schema == "secure_vault"
    assert ActionNonce.__table__.schema == "secure_vault"
    assert RedactionExecutionFence.__table__.schema == "secure_vault"


@pytest.mark.asyncio
async def test_live_database_orm_parity():
    """Verify that ORM models cleanly query the live test database without schema desynchronization."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as session:
        # 1. Query transfers table via ORM
        stmt = select(WorkspaceOwnershipTransfer).limit(5)
        res = await session.execute(stmt)
        transfers = res.scalars().all()
        assert len(transfers) > 0, "No transfers found in test database"
        for t in transfers:
            assert t.current_owner_email_snapshot is not None
            assert t.nominated_user_email_snapshot is not None

        # 2. Query departures table via ORM
        stmt_dep = select(WorkspaceFormerOwnerDeparture).limit(5)
        res_dep = await session.execute(stmt_dep)
        departures = res_dep.scalars().all()
        assert isinstance(departures, list)

        # 3. Test Repository instantiation
        dep_repo = WorkspaceFormerOwnerDepartureRepository(session)
        assert dep_repo.model_class == WorkspaceFormerOwnerDeparture
        trans_repo = WorkspaceOwnershipTransferRepository(session)
        assert trans_repo.model_class == WorkspaceOwnershipTransfer

        # Test list_by_workspace query execution
        first_ws_id = transfers[0].workspace_id
        ws_transfers = await trans_repo.list_by_workspace(first_ws_id, limit=5)
        assert isinstance(ws_transfers, list)

    await engine.dispose()


@pytest.mark.asyncio
async def test_repositories_crud_and_transactional_isolation():
    """Verify repository operations within an isolated transaction that rolls back."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as session:
        async with session.begin():
            # Find an existing transfer
            stmt = select(WorkspaceOwnershipTransfer).where(WorkspaceOwnershipTransfer.status == "ACCEPTED").limit(1)
            res = await session.execute(stmt)
            t = res.scalar_one()

            dep_repo = WorkspaceFormerOwnerDepartureRepository(session)
            trans_repo = WorkspaceOwnershipTransferRepository(session)

            # Test creating a departure record via repository
            now = datetime.now(UTC)
            dep = await dep_repo.create_departure(
                workspace_id=t.workspace_id,
                former_owner_id=t.nominated_by_user_id,
                transfer_id=t.id,
                departure_type=FormerOwnerDepartureType.VOLUNTARY_LEAVE,
                confirmed_by_user_id=t.nominee_user_id,
                departure_confirmed_at=now,
                former_role="OWNER",
                retained_role=None,
                departure_notes="Test departure via repository",
            )
            assert dep.id is not None
            assert dep.departure_type == "VOLUNTARY_LEAVE"

            # Query back by id
            dep_fetched = await dep_repo.get_by_id(dep.id)
            assert dep_fetched is not None
            assert dep_fetched.id == dep.id

            # Query back by transfer_id
            dep_by_t = await dep_repo.get_by_transfer_id(t.id)
            assert dep_by_t is not None
            assert dep_by_t.id == dep.id

            # List by workspace
            ws_deps = await dep_repo.list_by_workspace(t.workspace_id)
            assert len(ws_deps) >= 1

            # List by former owner
            user_deps = await dep_repo.list_by_former_owner(t.nominated_by_user_id)
            assert len(user_deps) >= 1

            # Test transfer repo lookups
            t_by_id = await trans_repo.get_by_id(t.id)
            assert t_by_id is not None
            assert t_by_id.id == t.id

            # Non-existent lookups
            fake_id = uuid.uuid4()
            assert await dep_repo.get_by_id(fake_id) is None
            assert await trans_repo.get_by_id(fake_id) is None

            # Always roll back so database remains completely clean
            await session.rollback()

    await engine.dispose()
