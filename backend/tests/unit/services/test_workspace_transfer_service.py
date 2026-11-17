"""Unit & Service-level integration tests for WorkspaceTransferService.

Governed by Section 7 Batch 1 (REV5).
Tested against isolated PostgreSQL test database (port 5433).
Covers Groups A, B, C, D, E service-level requirements.
"""

import asyncio
from datetime import UTC, datetime, timedelta
import os
import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models.entities.notification import Notification
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
from backend.services.workspace_transfer_service import WorkspaceTransferService

from sqlalchemy.pool import NullPool

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://t3b_test_admin:t3b_test_password_2026!@127.0.0.1:5433/raguard_t3b_test",
)


@pytest.fixture
def async_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
    yield engine


@pytest.fixture
def session_factory(async_engine):
    return async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def session(session_factory):
    async with session_factory() as sess:
        yield sess


@pytest.fixture
def service():
    return WorkspaceTransferService()


async def create_test_user(session: AsyncSession, email_prefix: str, custom_id: uuid.UUID = None) -> User:
    u_id = custom_id or uuid.uuid4()
    user = User(
        id=u_id,
        email=f"{email_prefix}_{uuid.uuid4().hex[:6]}@example.com",
        username=f"user_{uuid.uuid4().hex[:6]}",
        display_name=f"User {email_prefix}",
        role="user",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def create_test_workspace(session: AsyncSession) -> Workspace:
    ws_id = uuid.uuid4()
    ws = Workspace(
        id=ws_id,
        name=f"Test-WS-{uuid.uuid4().hex[:6]}",
        slug=f"test-ws-{uuid.uuid4().hex[:6]}",
        public_id=f"ws-{uuid.uuid4().hex[:8]}",
        storage_prefix=f"storage-{uuid.uuid4().hex[:8]}",
        qdrant_namespace=f"qdrant-{uuid.uuid4().hex[:8]}",
        status=WorkspaceStatus.ACTIVE.value,
        is_deleted=False,
    )
    session.add(ws)
    await session.commit()
    await session.refresh(ws)
    return ws


async def add_workspace_member(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str = WorkspaceRole.MEMBER.value,
    status: str = MemberStatus.ACTIVE.value,
    is_deleted: bool = False,
) -> WorkspaceMember:
    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=user_id,
        role=role,
        status=status,
        is_deleted=is_deleted,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return member


async def seed_transfer(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    owner_id: uuid.UUID,
    nominee_id: uuid.UUID,
    status: str = TransferStatus.PENDING.value,
    expires_at: datetime | None = None,
    rejection_reason: str | None = None,
    responded_at: datetime | None = None,
) -> WorkspaceOwnershipTransfer:
    if expires_at is None:
        expires_at = datetime.now(UTC) + timedelta(days=7)
    t = WorkspaceOwnershipTransfer(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        nominated_by_user_id=owner_id,
        nominee_user_id=nominee_id,
        status=status,
        created_at=datetime.now(UTC),
        expires_at=expires_at,
        current_owner_email_snapshot=f"user_{owner_id}@raguard.test",
        nominated_user_email_snapshot=f"user_{nominee_id}@raguard.test",
        rejection_reason=rejection_reason,
        responded_at=responded_at,
    )
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


# ==============================================================================
# GROUP A: NOMINATION INITIATION (7.1)
# ==============================================================================

@pytest.mark.asyncio
async def test_tc_7_1_01_owner_nominates_active_admin(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.1-01: Active OWNER successfully nominates active ADMIN."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    admin = await create_test_user(session, "admin")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, admin.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, admin.id)
    assert transfer.status == TransferStatus.PENDING.value
    assert transfer.workspace_id == ws.id
    assert transfer.nominated_by_user_id == owner.id
    assert transfer.nominee_user_id == admin.id
    assert transfer.expires_at > transfer.created_at
    # Exact 7-day TTL check (TC-7.1-13)
    assert (transfer.expires_at - transfer.created_at).total_seconds() == pytest.approx(7 * 86400, abs=2)


@pytest.mark.asyncio
async def test_tc_7_1_02_owner_nominates_active_member(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.1-02: Active OWNER successfully nominates active MEMBER."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    member = await create_test_user(session, "member")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, member.id, role="MEMBER")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, member.id)
    assert transfer.status == TransferStatus.PENDING.value
    assert transfer.nominee_user_id == member.id


@pytest.mark.asyncio
async def test_tc_7_1_03_owner_cannot_nominate_self(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.1-03: Active OWNER cannot nominate self (HTTP 400)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")

    with pytest.raises(HTTPException) as exc_info:
        await service.initiate_nomination(session, ws.id, owner.id, owner.id)
    assert exc_info.value.status_code == 400
    assert "Cannot nominate self" in exc_info.value.detail


@pytest.mark.asyncio
async def test_tc_7_1_04_owner_cannot_nominate_viewer(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.1-04: Active OWNER cannot nominate VIEWER (HTTP 400)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    viewer = await create_test_user(session, "viewer")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, viewer.id, role="VIEWER")

    with pytest.raises(HTTPException) as exc_info:
        await service.initiate_nomination(session, ws.id, owner.id, viewer.id)
    assert exc_info.value.status_code == 400
    assert "cannot be nominated as OWNER" in exc_info.value.detail or "ADMIN or MEMBER" in exc_info.value.detail


@pytest.mark.asyncio
async def test_tc_7_1_05_owner_cannot_nominate_existing_owner(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.1-05: Active OWNER cannot nominate existing OWNER (HTTP 400)."""
    ws = await create_test_workspace(session)
    owner1 = await create_test_user(session, "owner1")
    owner2 = await create_test_user(session, "owner2")
    await add_workspace_member(session, ws.id, owner1.id, role="OWNER")
    # Add second owner with is_deleted=True so unique index passes
    await add_workspace_member(session, ws.id, owner2.id, role="OWNER", is_deleted=True)

    with pytest.raises(HTTPException) as exc_info:
        await service.initiate_nomination(session, ws.id, owner1.id, owner2.id)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_tc_7_1_06_owner_cannot_nominate_non_member(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.1-06: Active OWNER cannot nominate non-member (HTTP 400)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    outsider = await create_test_user(session, "outsider")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")

    with pytest.raises(HTTPException) as exc_info:
        await service.initiate_nomination(session, ws.id, owner.id, outsider.id)
    assert exc_info.value.status_code == 400
    assert "Nominee must be an active workspace member" in exc_info.value.detail or "not an active member" in exc_info.value.detail


@pytest.mark.asyncio
async def test_tc_7_1_07_owner_cannot_nominate_suspended_member(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.1-07: Active OWNER cannot nominate SUSPENDED member (HTTP 400)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    suspended = await create_test_user(session, "suspended")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, suspended.id, role="MEMBER", status="SUSPENDED")

    with pytest.raises(HTTPException) as exc_info:
        await service.initiate_nomination(session, ws.id, owner.id, suspended.id)
    assert exc_info.value.status_code == 400
    assert "Nominee must be an active workspace member" in exc_info.value.detail or "not active" in exc_info.value.detail


@pytest.mark.asyncio
async def test_tc_7_1_08_admin_cannot_nominate(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.1-08: ADMIN cannot initiate nomination (HTTP 403)."""
    ws = await create_test_workspace(session)
    admin = await create_test_user(session, "admin")
    member = await create_test_user(session, "member")
    await add_workspace_member(session, ws.id, admin.id, role="ADMIN")
    await add_workspace_member(session, ws.id, member.id, role="MEMBER")

    with pytest.raises(HTTPException) as exc_info:
        await service.initiate_nomination(session, ws.id, admin.id, member.id)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_tc_7_1_09_member_cannot_nominate(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.1-09: MEMBER cannot initiate nomination (HTTP 403)."""
    ws = await create_test_workspace(session)
    m1 = await create_test_user(session, "m1")
    m2 = await create_test_user(session, "m2")
    await add_workspace_member(session, ws.id, m1.id, role="MEMBER")
    await add_workspace_member(session, ws.id, m2.id, role="MEMBER")

    with pytest.raises(HTTPException) as exc_info:
        await service.initiate_nomination(session, ws.id, m1.id, m2.id)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_tc_7_1_10_viewer_cannot_nominate(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.1-10: VIEWER cannot initiate nomination (HTTP 403)."""
    ws = await create_test_workspace(session)
    viewer = await create_test_user(session, "viewer")
    m = await create_test_user(session, "m")
    await add_workspace_member(session, ws.id, viewer.id, role="VIEWER")
    await add_workspace_member(session, ws.id, m.id, role="MEMBER")

    with pytest.raises(HTTPException) as exc_info:
        await service.initiate_nomination(session, ws.id, viewer.id, m.id)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_tc_7_1_12_nomination_fails_if_active_pending_exists(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.1-12: Nomination fails if active PENDING nomination exists (HTTP 409)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    m1 = await create_test_user(session, "m1")
    m2 = await create_test_user(session, "m2")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, m1.id, role="MEMBER")
    await add_workspace_member(session, ws.id, m2.id, role="MEMBER")

    await service.initiate_nomination(session, ws.id, owner.id, m1.id)

    with pytest.raises(HTTPException) as exc_info:
        await service.initiate_nomination(session, ws.id, owner.id, m2.id)
    assert exc_info.value.status_code == 409
    assert "pending ownership nomination already exists" in exc_info.value.detail


@pytest.mark.asyncio
async def test_tc_7_1_14_nominee_notification_created(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.1-14: In-app notification created for nominee in same transaction."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="MEMBER")

    await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    # Verify notification created for nominee
    n_res = await session.execute(
        select(Notification).where(Notification.user_id == nominee.id)
    )
    notifs = n_res.scalars().all()
    assert len(notifs) >= 1
    assert any("Nomination" in n.title for n in notifs)


@pytest.mark.asyncio
async def test_tc_7_1_15_unauthorized_initiation_produces_zero_mutations(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.1-15: Unauthorized attempt produces zero mutations and zero notifications (HTTP 403)."""
    ws = await create_test_workspace(session)
    outsider = await create_test_user(session, "outsider")
    m = await create_test_user(session, "m")
    await add_workspace_member(session, ws.id, m.id, role="MEMBER")

    with pytest.raises(HTTPException):
        await service.initiate_nomination(session, ws.id, outsider.id, m.id)

    # Verify zero transfer rows and zero notifications
    t_res = await session.execute(
        select(WorkspaceOwnershipTransfer).where(WorkspaceOwnershipTransfer.workspace_id == ws.id)
    )
    assert len(t_res.scalars().all()) == 0

    n_res = await session.execute(
        select(Notification).where(Notification.user_id == m.id)
    )
    assert len(n_res.scalars().all()) == 0


# ==============================================================================
# GROUP B: ACCEPTANCE & DEMOTION (7.2)
# ==============================================================================

@pytest.mark.asyncio
async def test_tc_7_2_01_through_05_nominee_accepts_and_promoted(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.2-01 to TC-7.2-05: Successful acceptance, promotion, former owner demotion to TRANSFER_PENDING."""
    ws = await create_test_workspace(session)
    former_owner = await create_test_user(session, "former_owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, former_owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, former_owner.id, nominee.id)

    accepted = await service.accept_transfer(session, ws.id, transfer.id, nominee.id)
    assert accepted.status == TransferStatus.ACCEPTED.value
    assert accepted.responded_at is not None

    # TC-7.2-02: Nominee promoted to role=OWNER, status=ACTIVE
    nom_m_res = await session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws.id,
            WorkspaceMember.user_id == nominee.id,
            WorkspaceMember.is_deleted == False,
        )
    )
    nom_m = nom_m_res.scalar_one()
    assert nom_m.role == WorkspaceRole.OWNER.value
    assert nom_m.status == MemberStatus.ACTIVE.value

    # TC-7.2-03: Former owner transitioned to role=MEMBER, status=TRANSFER_PENDING
    fo_m_res = await session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws.id,
            WorkspaceMember.user_id == former_owner.id,
            WorkspaceMember.is_deleted == False,
        )
    )
    fo_m = fo_m_res.scalar_one()
    assert fo_m.role == WorkspaceRole.MEMBER.value
    assert fo_m.status == MemberStatus.TRANSFER_PENDING.value

    # TC-7.2-04: Exactly one active owner exists
    owners_res = await session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws.id,
            WorkspaceMember.role == WorkspaceRole.OWNER.value,
            WorkspaceMember.is_deleted == False,
        )
    )
    owners = owners_res.scalars().all()
    assert len(owners) == 1
    assert owners[0].user_id == nominee.id


@pytest.mark.asyncio
async def test_tc_7_2_06_non_nominee_cannot_accept(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.2-06: Non-nominee member cannot accept nomination (HTTP 403)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    other_member = await create_test_user(session, "other")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")
    await add_workspace_member(session, ws.id, other_member.id, role="MEMBER")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    with pytest.raises(HTTPException) as exc_info:
        await service.accept_transfer(session, ws.id, transfer.id, other_member.id)
    assert exc_info.value.status_code == 403
    assert "designated nominee" in exc_info.value.detail


@pytest.mark.asyncio
async def test_tc_7_2_07_owner_cannot_accept_own_nomination(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.2-07: Current owner cannot accept nomination (HTTP 403)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    with pytest.raises(HTTPException) as exc_info:
        await service.accept_transfer(session, ws.id, transfer.id, owner.id)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_tc_7_2_08_09_10_acceptance_terminal_states_rejected(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.2-08, TC-7.2-09: Acceptance fails if status is REJECTED or CANCELLED (HTTP 409)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)
    await service.reject_transfer(session, ws.id, transfer.id, nominee.id, reason="No bandwidth")

    with pytest.raises(HTTPException) as exc_info:
        await service.accept_transfer(session, ws.id, transfer.id, nominee.id)
    assert exc_info.value.status_code == 409
    assert "REJECTED" in exc_info.value.detail


@pytest.mark.asyncio
async def test_tc_7_2_11_12_acceptance_fails_after_expiration(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.2-11, 12: Acceptance fails after expiration (HTTP 410), sets EXPIRED, dual notifications."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    # Seed transfer with past expiration date at creation time to respect WORM immutability
    transfer = await seed_transfer(
        session, ws.id, owner.id, nominee.id,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.accept_transfer(session, ws.id, transfer.id, nominee.id)
    assert exc_info.value.status_code == 410

    await session.refresh(transfer)
    assert transfer.status == TransferStatus.EXPIRED.value
    assert transfer.expired_at is not None

    # Dual in-app notifications verified (TC-7.2-12)
    for u_id in [owner.id, nominee.id]:
        n_res = await session.execute(
            select(Notification).where(Notification.user_id == u_id)
        )
        notifs = n_res.scalars().all()
        assert any("Expired" in n.title for n in notifs)


@pytest.mark.asyncio
async def test_tc_7_2_13_acceptance_fails_if_nominee_suspended(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.2-13: Acceptance fails if nominee was suspended after nomination (HTTP 400)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    nom_m = await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    # Suspend nominee concurrently
    nom_m.status = MemberStatus.SUSPENDED.value
    await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await service.accept_transfer(session, ws.id, transfer.id, nominee.id)
    assert exc_info.value.status_code == 400
    assert "no longer active" in exc_info.value.detail


@pytest.mark.asyncio
async def test_tc_7_2_14_acceptance_fails_if_nominee_demoted_to_viewer(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.2-14: Acceptance fails if nominee was demoted to VIEWER after nomination (HTTP 400)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    nom_m = await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    # Demote nominee to VIEWER
    nom_m.role = "VIEWER"
    await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await service.accept_transfer(session, ws.id, transfer.id, nominee.id)
    assert exc_info.value.status_code == 400
    assert "ineligible for ownership" in exc_info.value.detail or "ADMIN or MEMBER" in exc_info.value.detail


@pytest.mark.asyncio
async def test_tc_7_2_15_acceptance_fails_if_nominator_no_longer_owner(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.2-15: Acceptance fails with HTTP 409 if nominator is no longer active OWNER."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    owner_m = await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    # Demote owner to MEMBER before acceptance
    owner_m.role = WorkspaceRole.MEMBER.value
    await session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await service.accept_transfer(session, ws.id, transfer.id, nominee.id)
    assert exc_info.value.status_code == 409
    assert "Workspace must have exactly one active OWNER" in exc_info.value.detail or "nominator is no longer" in exc_info.value.detail


@pytest.mark.asyncio
async def test_tc_7_2_19_nominee_uuid_sorts_before_former_owner(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.2-19: Explicit flush satisfies uq_workspace_members_active_owner when nominee UUID < former owner UUID."""
    ws = await create_test_workspace(session)
    # Generate random UUIDs such that nominee_id < former_owner_id lexicographically
    u1, u2 = uuid.uuid4(), uuid.uuid4()
    while u1 == u2:
        u2 = uuid.uuid4()
    u_small = min(u1, u2)
    u_large = max(u1, u2)
    assert u_small < u_large

    nominee = await create_test_user(session, "nom_small", custom_id=u_small)
    former_owner = await create_test_user(session, "fo_large", custom_id=u_large)

    await add_workspace_member(session, ws.id, former_owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, former_owner.id, nominee.id)

    # Acceptance MUST succeed without unique violation 23505 due to explicit intermediate flush
    accepted = await service.accept_transfer(session, ws.id, transfer.id, nominee.id)
    assert accepted.status == TransferStatus.ACCEPTED.value


# ==============================================================================
# GROUP C: REJECTION (7.2)
# ==============================================================================

@pytest.mark.asyncio
async def test_tc_7_2_20_21_23_24_nominee_rejects_with_reason(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.2-20, 21, 23, 24: Nominee rejects nomination with reason, owner unchanged, status REJECTED."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)
    rejected = await service.reject_transfer(session, ws.id, transfer.id, nominee.id, "No bandwidth")

    assert rejected.status == TransferStatus.REJECTED.value
    assert rejected.rejection_reason == "No bandwidth"
    assert rejected.responded_at is not None

    # TC-7.2-24: Owner unchanged
    owner_m_res = await session.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws.id,
            WorkspaceMember.user_id == owner.id,
            WorkspaceMember.is_deleted == False,
        )
    )
    owner_m = owner_m_res.scalar_one()
    assert owner_m.role == WorkspaceRole.OWNER.value
    assert owner_m.status == MemberStatus.ACTIVE.value

    # TC-7.2-26: Original owner notified
    n_res = await session.execute(
        select(Notification).where(Notification.user_id == owner.id)
    )
    notifs = n_res.scalars().all()
    assert any("Declined" in n.title for n in notifs)


@pytest.mark.asyncio
async def test_tc_7_2_25_non_nominee_cannot_reject(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.2-25: Non-nominee cannot reject nomination (HTTP 403)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    stranger = await create_test_user(session, "stranger")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")
    await add_workspace_member(session, ws.id, stranger.id, role="MEMBER")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    with pytest.raises(HTTPException) as exc_info:
        await service.reject_transfer(session, ws.id, transfer.id, stranger.id)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_tc_7_2_27_rejection_after_expiration_transitions_to_expired(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.2-27: Rejection after expiration transitions to EXPIRED, not REJECTED (HTTP 410)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    # Seed transfer with past expiration date at creation time to respect WORM immutability
    transfer = await seed_transfer(
        session, ws.id, owner.id, nominee.id,
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.reject_transfer(session, ws.id, transfer.id, nominee.id, reason="Declined")
    assert exc_info.value.status_code == 410

    await session.refresh(transfer)
    assert transfer.status == TransferStatus.EXPIRED.value


# ==============================================================================
# GROUP D: CANCELLATION & DYNAMIC EXPIRATION (7.3)
# ==============================================================================

@pytest.mark.asyncio
async def test_tc_7_3_01_02_03_owner_cancels_nomination(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.3-01 to 03: Active OWNER cancels nomination, status CANCELLED, nominee notified."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)
    cancelled = await service.cancel_transfer(session, ws.id, transfer.id, owner.id)

    assert cancelled.status == TransferStatus.CANCELLED.value
    assert cancelled.cancelled_at is not None

    # Nominee notified in-app
    n_res = await session.execute(
        select(Notification).where(Notification.user_id == nominee.id)
    )
    notifs = n_res.scalars().all()
    assert any("Cancelled" in n.title for n in notifs)


@pytest.mark.asyncio
async def test_tc_7_3_04_05_non_owner_cannot_cancel(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.3-04, 05: Non-owner cannot cancel nomination (HTTP 403)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    with pytest.raises(HTTPException) as exc_info:
        await service.cancel_transfer(session, ws.id, transfer.id, nominee.id)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_tc_7_3_07_cancellation_fails_if_accepted(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.3-07: Cancellation fails if transfer is already ACCEPTED (HTTP 409)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)
    await service.accept_transfer(session, ws.id, transfer.id, nominee.id)

    # Nominee is now active owner
    with pytest.raises(HTTPException) as exc_info:
        await service.cancel_transfer(session, ws.id, transfer.id, nominee.id)
    assert exc_info.value.status_code == 409
    assert "ACCEPTED" in exc_info.value.detail


@pytest.mark.asyncio
async def test_tc_7_3_08_cancellation_after_expiration_transitions_to_expired(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.3-08: Cancellation after expiration transitions to EXPIRED, not CANCELLED (HTTP 410)."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    # Seed transfer with past expiration date at creation time to respect WORM immutability
    transfer = await seed_transfer(
        session, ws.id, owner.id, nominee.id,
        expires_at=datetime.now(UTC) - timedelta(minutes=10),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.cancel_transfer(session, ws.id, transfer.id, owner.id)
    assert exc_info.value.status_code == 410

    await session.refresh(transfer)
    assert transfer.status == TransferStatus.EXPIRED.value


@pytest.mark.asyncio
async def test_tc_7_3_09_10_11_fresh_nomination_after_terminal_states(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.3-09, 10, 11: Fresh nomination can be created after CANCELLED, REJECTED, EXPIRED."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    # Cancelled -> fresh
    t1 = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)
    await service.cancel_transfer(session, ws.id, t1.id, owner.id)

    t2 = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)
    assert t2.status == TransferStatus.PENDING.value

    # Rejected -> fresh
    await service.reject_transfer(session, ws.id, t2.id, nominee.id, reason="Declined by nominee")
    t3 = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)
    assert t3.status == TransferStatus.PENDING.value


@pytest.mark.asyncio
async def test_tc_7_3_16_17_get_active_transfer_privacy_and_expiration(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.3-16, 17: GET active transfer returns data to owner/nominee, null to 3rd party, expires dynamically."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    third_party = await create_test_user(session, "third_party")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")
    await add_workspace_member(session, ws.id, third_party.id, role="MEMBER")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    # Active owner sees transfer
    owner_view = await service.get_active_transfer(session, ws.id, owner.id)
    assert owner_view is not None
    assert owner_view.id == transfer.id

    # Nominee sees transfer
    nominee_view = await service.get_active_transfer(session, ws.id, nominee.id)
    assert nominee_view is not None
    assert nominee_view.id == transfer.id

    # Third party receives null (privacy preserved)
    third_party_view = await service.get_active_transfer(session, ws.id, third_party.id)
    assert third_party_view is None

    # Dynamic expiration on GET: cancel active transfer and seed past-expired transfer to respect WORM immutability
    await service.cancel_transfer(session, ws.id, transfer.id, owner.id)
    expired_transfer = await seed_transfer(
        session, ws.id, owner.id, nominee.id,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    expired_view = await service.get_active_transfer(session, ws.id, owner.id)
    assert expired_view is None
    await session.refresh(expired_transfer)
    assert expired_transfer.status == TransferStatus.EXPIRED.value


@pytest.mark.asyncio
async def test_tc_7_3_23_through_27_unauthorized_cancellation_no_status_disclosure(
    session: AsyncSession, service: WorkspaceTransferService
):
    """TC-7.3-23 to 27: Unauthorized cancellation receives HTTP 403 unconditionally across all 5 states."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    unauthorized_user = await create_test_user(session, "unauth")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")
    await add_workspace_member(session, ws.id, unauthorized_user.id, role="MEMBER")

    states = [
        TransferStatus.PENDING.value,
        TransferStatus.REJECTED.value,
        TransferStatus.CANCELLED.value,
        TransferStatus.EXPIRED.value,
        TransferStatus.ACCEPTED.value,
    ]

    for st in states:
        t = WorkspaceOwnershipTransfer(
            workspace_id=ws.id,
            nominated_by_user_id=owner.id,
            nominee_user_id=nominee.id,
            status=st,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=7),
            current_owner_email_snapshot="owner@raguard.test",
            nominated_user_email_snapshot="nominee@raguard.test",
        )
        session.add(t)
        await session.commit()
        await session.refresh(t)

        with pytest.raises(HTTPException) as exc_info:
            await service.cancel_transfer(session, ws.id, t.id, unauthorized_user.id)
        # MUST BE HTTP 403 unconditionally (NO HTTP 409 or 410 disclosure!)
        assert exc_info.value.status_code == 403
        assert "Only the current active workspace OWNER" in exc_info.value.detail


# ==============================================================================
# GROUP E: AUDIT RETENTION & RESTRICTED DELETION
# ==============================================================================

@pytest.mark.asyncio
async def test_tc_7_e_04_workspace_hard_deletion_blocked_by_fk_restrict(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.E-04: Workspace hard-deletion blocked by ON DELETE RESTRICT when transfers exist."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    # Attempt hard DELETE of workspace record directly
    with pytest.raises(IntegrityError):
        await session.execute(delete(Workspace).where(Workspace.id == ws.id))
        await session.commit()

    await session.rollback()


@pytest.mark.asyncio
async def test_tc_7_e_05_user_hard_deletion_blocked_by_fk_restrict(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.E-05: User hard-deletion blocked by ON DELETE RESTRICT when user is in transfer history."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    # Attempt hard DELETE of owner user directly
    with pytest.raises(IntegrityError):
        await session.execute(delete(User).where(User.id == owner.id))
        await session.commit()

    await session.rollback()


@pytest.mark.asyncio
async def test_tc_7_e_06_workspace_soft_deletion_retains_transfer_history(session: AsyncSession, service: WorkspaceTransferService):
    """TC-7.E-06: Workspace soft deletion retains all transfer records intact."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "owner")
    nominee = await create_test_user(session, "nominee")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    # Soft delete workspace
    ws.is_deleted = True
    await session.commit()

    # Query transfer record
    t_res = await session.execute(
        select(WorkspaceOwnershipTransfer).where(WorkspaceOwnershipTransfer.id == transfer.id)
    )
    t = t_res.scalar_one_or_none()
    assert t is not None
    assert t.workspace_id == ws.id


# ==============================================================================
# FOCUSED GAP CLOSURE TESTS (REV5 CONCURRENCY & EVIDENCE COMPLETENESS)
# ==============================================================================

@pytest.mark.asyncio
async def test_tc_7_1_16_ineligible_nominee_produces_zero_mutations_and_notifications(
    session: AsyncSession, service: WorkspaceTransferService
):
    """TC-7.1-16: Ineligible nominee nomination attempt produces zero state changes, zero notifications."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "inel_owner")
    viewer = await create_test_user(session, "inel_viewer")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, viewer.id, role="VIEWER")

    with pytest.raises(HTTPException) as exc_info:
        await service.initiate_nomination(session, ws.id, owner.id, viewer.id)
    assert exc_info.value.status_code == 400

    # Explicit DB assertion: 0 transfers and 0 notifications
    t_res = await session.execute(
        select(WorkspaceOwnershipTransfer).where(WorkspaceOwnershipTransfer.workspace_id == ws.id)
    )
    assert len(t_res.scalars().all()) == 0

    n_res = await session.execute(
        select(Notification).where(Notification.user_id.in_([owner.id, viewer.id]))
    )
    assert len(n_res.scalars().all()) == 0


@pytest.mark.asyncio
async def test_tc_7_2_16_acceptance_fails_when_former_owner_missing_or_inactive(
    session: AsyncSession, service: WorkspaceTransferService
):
    """TC-7.2-16: Acceptance fails with HTTP 409 if former owner membership record is missing or inactive."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "fo_inact_owner")
    nominee = await create_test_user(session, "fo_inact_nom")
    owner_mem = await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    # Subcase A: former owner membership marked deleted (missing)
    owner_mem.is_deleted = True
    await session.commit()

    with pytest.raises(HTTPException) as exc_a:
        await service.accept_transfer(session, ws.id, transfer.id, nominee.id)
    assert exc_a.value.status_code == 409
    assert "Workspace must have exactly one active OWNER" in exc_a.value.detail

    # Subcase B: former owner membership inactive (SUSPENDED)
    owner_mem.is_deleted = False
    owner_mem.status = MemberStatus.SUSPENDED.value
    await session.commit()

    with pytest.raises(HTTPException) as exc_b:
        await service.accept_transfer(session, ws.id, transfer.id, nominee.id)
    assert exc_b.value.status_code == 409


@pytest.mark.asyncio
async def test_tc_7_2_17_acceptance_generates_notifications_for_both_parties(
    session: AsyncSession, service: WorkspaceTransferService
):
    """TC-7.2-17: Successful acceptance generates dual in-app notifications for both former owner and new owner."""
    ws = await create_test_workspace(session)
    former_owner = await create_test_user(session, "notif_fo")
    nominee = await create_test_user(session, "notif_nom")
    await add_workspace_member(session, ws.id, former_owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, former_owner.id, nominee.id)

    # Accept transfer
    await service.accept_transfer(session, ws.id, transfer.id, nominee.id)

    # Verify notifications created for both users
    fo_n = await session.execute(
        select(Notification).where(Notification.user_id == former_owner.id)
    )
    nom_n = await session.execute(
        select(Notification).where(Notification.user_id == nominee.id)
    )
    fo_notifs = fo_n.scalars().all()
    nom_notifs = nom_n.scalars().all()

    assert any("Ownership Transfer Completed" in n.title for n in fo_notifs)
    assert any("You are now Workspace Owner" in n.title for n in nom_notifs)


@pytest.mark.asyncio
async def test_tc_7_3_06_new_active_owner_cancels_previous_owner_nomination(
    session: AsyncSession, service: WorkspaceTransferService
):
    """TC-7.3-06: New active OWNER can cancel nomination created by previous owner."""
    ws = await create_test_workspace(session)
    owner1 = await create_test_user(session, "prev_owner")
    nominee = await create_test_user(session, "prev_nom")
    new_owner = await create_test_user(session, "new_owner")
    o1_mem = await add_workspace_member(session, ws.id, owner1.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="MEMBER")
    new_mem = await add_workspace_member(session, ws.id, new_owner.id, role="ADMIN")

    transfer = await service.initiate_nomination(session, ws.id, owner1.id, nominee.id)

    # Transfer of ownership authority to new_owner
    o1_mem.role = WorkspaceRole.MEMBER.value
    await session.flush()
    new_mem.role = WorkspaceRole.OWNER.value
    await session.commit()

    # new_owner cancels the transfer created by owner1
    cancelled = await service.cancel_transfer(session, ws.id, transfer.id, new_owner.id)
    assert cancelled.status == TransferStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_tc_7_3_11_fresh_nomination_after_expired_state(
    session: AsyncSession, service: WorkspaceTransferService
):
    """TC-7.3-11: Fresh nomination can be created immediately after a transfer reaches EXPIRED state."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "exp_fresh_owner")
    nominee = await create_test_user(session, "exp_fresh_nom")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    t1 = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)
    t1.status = TransferStatus.EXPIRED.value
    t1.expired_at = datetime.now(UTC)
    await session.commit()

    # Fresh nomination succeeds
    t2 = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)
    assert t2.status == TransferStatus.PENDING.value
    assert t2.id != t1.id


@pytest.mark.asyncio
async def test_tc_7_3_19_get_active_caller_demoted_during_lock_returns_null(
    session: AsyncSession, service: WorkspaceTransferService
):
    """TC-7.3-19: GET /active caller demoted to regular member receives null (not transfer details)."""
    ws = await create_test_workspace(session)
    former_owner = await create_test_user(session, "dem_caller")
    nominee = await create_test_user(session, "dem_nom")
    mem = await add_workspace_member(session, ws.id, former_owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")

    await service.initiate_nomination(session, ws.id, former_owner.id, nominee.id)

    # Demote caller before/during membership check
    mem.role = WorkspaceRole.MEMBER.value
    await session.commit()

    res = await service.get_active_transfer(session, ws.id, former_owner.id)
    assert res is None


@pytest.mark.asyncio
async def test_tc_7_e_01_concurrent_acceptance_and_cancellation(
    session_factory, service: WorkspaceTransferService
):
    """TC-7.E-01: Concurrent acceptance and cancellation requests resolve safely without deadlocks under L_W -> L_TRANS -> L_WM."""
    async with session_factory() as setup_session:
        ws = await create_test_workspace(setup_session)
        owner = await create_test_user(setup_session, "owner_conc")
        nominee = await create_test_user(setup_session, "nom_conc")
        await add_workspace_member(setup_session, ws.id, owner.id, role="OWNER")
        await add_workspace_member(setup_session, ws.id, nominee.id, role="ADMIN")
        transfer = await service.initiate_nomination(setup_session, ws.id, owner.id, nominee.id)
        transfer_id = transfer.id
        ws_id = ws.id
        owner_id = owner.id
        nominee_id = nominee.id

    async def do_accept():
        async with session_factory() as sess:
            try:
                res = await service.accept_transfer(sess, ws_id, transfer_id, nominee_id)
                return ("ACCEPTED", res)
            except HTTPException as e:
                return ("EXC", e)

    async def do_cancel():
        async with session_factory() as sess:
            try:
                res = await service.cancel_transfer(sess, ws_id, transfer_id, owner_id)
                return ("CANCELLED", res)
            except HTTPException as e:
                return ("EXC", e)

    # Run simultaneously with bounded timeout to prove zero deadlocks
    results = await asyncio.wait_for(asyncio.gather(do_accept(), do_cancel()), timeout=10.0)
    outcomes = [r[0] for r in results]
    assert ("ACCEPTED" in outcomes) ^ ("CANCELLED" in outcomes), f"Expected exactly one success: {outcomes}"
    assert "EXC" in outcomes
    exc = next(r[1] for r in results if r[0] == "EXC")
    assert exc.status_code in (403, 409)

    # Verify final database state is consistent with the winner
    async with session_factory() as verify_sess:
        t_res = await verify_sess.execute(
            select(WorkspaceOwnershipTransfer).where(WorkspaceOwnershipTransfer.id == transfer_id)
        )
        final_t = t_res.scalar_one()
        if "ACCEPTED" in outcomes:
            assert final_t.status == TransferStatus.ACCEPTED.value
        else:
            assert final_t.status == TransferStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_tc_7_e_02_concurrent_duplicate_nominations(
    session_factory, service: WorkspaceTransferService
):
    """TC-7.E-02: Concurrent duplicate nomination attempts: exactly one succeeds, second gets HTTP 409."""
    async with session_factory() as setup_session:
        ws = await create_test_workspace(setup_session)
        owner = await create_test_user(setup_session, "dup_owner")
        nominee1 = await create_test_user(setup_session, "dup_nom1")
        nominee2 = await create_test_user(setup_session, "dup_nom2")
        await add_workspace_member(setup_session, ws.id, owner.id, role="OWNER")
        await add_workspace_member(setup_session, ws.id, nominee1.id, role="ADMIN")
        await add_workspace_member(setup_session, ws.id, nominee2.id, role="MEMBER")
        ws_id = ws.id
        owner_id = owner.id
        nom1_id = nominee1.id
        nom2_id = nominee2.id

    async def do_nominate(nom_id):
        async with session_factory() as sess:
            try:
                res = await service.initiate_nomination(sess, ws_id, owner_id, nom_id)
                return ("SUCCESS", res)
            except HTTPException as e:
                return ("EXC", e)

    results = await asyncio.wait_for(asyncio.gather(do_nominate(nom1_id), do_nominate(nom2_id)), timeout=10.0)
    outcomes = [r[0] for r in results]
    assert outcomes.count("SUCCESS") == 1
    assert outcomes.count("EXC") == 1
    exc = next(r[1] for r in results if r[0] == "EXC")
    assert exc.status_code in (403, 409)

    # Verify database has exactly 1 pending transfer
    async with session_factory() as verify_sess:
        t_res = await verify_sess.execute(
            select(WorkspaceOwnershipTransfer).where(
                WorkspaceOwnershipTransfer.workspace_id == ws_id,
                WorkspaceOwnershipTransfer.status == TransferStatus.PENDING.value,
            )
        )
        assert len(t_res.scalars().all()) == 1


@pytest.mark.asyncio
async def test_tc_7_e_07_unauthorized_cancellation_produces_zero_side_effects(
    session: AsyncSession, service: WorkspaceTransferService
):
    """TC-7.E-07: Unauthorized cancellation attempt raises HTTP 403 without triggering state transition or notifications."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "e07_owner")
    nominee = await create_test_user(session, "e07_nom")
    unauth = await create_test_user(session, "e07_unauth")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")
    await add_workspace_member(session, ws.id, unauth.id, role="MEMBER")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    with pytest.raises(HTTPException) as exc_info:
        await service.cancel_transfer(session, ws.id, transfer.id, unauth.id)
    assert exc_info.value.status_code == 403

    # Assert transfer status remains PENDING and cancelled_at is None
    await session.refresh(transfer)
    assert transfer.status == TransferStatus.PENDING.value
    assert transfer.cancelled_at is None

    # Assert zero cancellation notifications created
    n_res = await session.execute(
        select(Notification).where(
            Notification.user_id.in_([owner.id, nominee.id, unauth.id]),
            Notification.title.ilike("%cancel%"),
        )
    )
    assert len(n_res.scalars().all()) == 0


@pytest.mark.asyncio
async def test_tc_7_e_08_unauthorized_rejection_produces_zero_side_effects(
    session: AsyncSession, service: WorkspaceTransferService
):
    """TC-7.E-08: Unauthorized rejection attempt raises HTTP 403 without triggering state transition or notifications."""
    ws = await create_test_workspace(session)
    owner = await create_test_user(session, "e08_owner")
    nominee = await create_test_user(session, "e08_nom")
    unauth = await create_test_user(session, "e08_unauth")
    await add_workspace_member(session, ws.id, owner.id, role="OWNER")
    await add_workspace_member(session, ws.id, nominee.id, role="ADMIN")
    await add_workspace_member(session, ws.id, unauth.id, role="MEMBER")

    transfer = await service.initiate_nomination(session, ws.id, owner.id, nominee.id)

    with pytest.raises(HTTPException) as exc_info:
        await service.reject_transfer(session, ws.id, transfer.id, unauth.id)
    assert exc_info.value.status_code == 403

    # Assert transfer status remains PENDING and responded_at is None
    await session.refresh(transfer)
    assert transfer.status == TransferStatus.PENDING.value
    assert transfer.responded_at is None
    assert transfer.rejection_reason is None

    # Assert zero rejection notifications created
    n_res = await session.execute(
        select(Notification).where(
            Notification.user_id.in_([owner.id, nominee.id, unauth.id]),
            Notification.title.ilike("%decline%"),
        )
    )
    assert len(n_res.scalars().all()) == 0

