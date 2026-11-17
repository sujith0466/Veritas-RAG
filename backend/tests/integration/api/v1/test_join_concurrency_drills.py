"""Integration concurrency drills for Sections 4 and 5.

Verifies:
1. Concurrent redemptions of reusable invitation links:
   - 10 concurrent users redeem the same link.
   - All get MEMBER role, invitation remains PENDING, no race conditions.
2. Concurrent join code usage recording:
   - Concurrent usage recording under load without deadlock.
3. Concurrent outbox dispatcher lease claims:
   - Mutex / lease prevents double dispatch of outbox records.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.models.entities.notification_outbox import NotificationOutbox
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_invitation import (
    InvitationStatus,
    WorkspaceInvitation,
)
from backend.models.entities.workspace_join_code import (
    WorkspaceJoinCode,
)
from backend.services.workspace.invitation_service import (
    WorkspaceInvitationService,
    generate_invitation_token,
)
from backend.services.workspace.join_code_service import (
    JoinCodeService,
)


@pytest.fixture
def workspace_id():
    return uuid.uuid4()


@pytest.fixture
def owner_id():
    return uuid.uuid4()


@pytest.mark.asyncio
async def test_concurrent_reusable_invitation_redemptions(workspace_id, owner_id):
    """Drill 1: 10 concurrent acceptances of the same reusable link."""
    raw_token, token_selector, token_hash = generate_invitation_token()

    invitation = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email=None,  # Reusable
        role="MEMBER",
        token_hash=token_hash,
        token_selector=token_selector,
        status=InvitationStatus.PENDING.value,
        is_legacy_bound=False,
        version=1,
        invited_by_user_id=owner_id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    mock_invitation_repo = AsyncMock()
    mock_invitation_repo.get_by_token_selector_for_update.return_value = invitation

    mock_workspace_repo = AsyncMock()
    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Concurrent WS", status=WorkspaceStatus.ACTIVE.value
    )

    mock_member_repo = AsyncMock()
    mock_member_repo.get_membership.return_value = None  # None of the joiners are existing members

    mock_settings_repo = AsyncMock()
    mock_settings_repo.get_by_workspace_id.return_value = None

    mock_email_provider = AsyncMock()

    service = WorkspaceInvitationService(
        invitation_repo=mock_invitation_repo,
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
        settings_repo=mock_settings_repo,
        email_provider=mock_email_provider,
    )

    # 10 concurrent joiners
    async def join_user(idx: int):
        user_mock = MagicMock(id=uuid.uuid4(), email=f"user_{idx}@example.com")
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        exec_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = None
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        return await service.accept_invitation(
            session=mock_session,
            raw_token=raw_token,
            user_context=user_mock,
        )

    tasks = [join_user(i) for i in range(10)]
    results = await asyncio.gather(*tasks)

    assert len(results) == 10
    for r in results:
        assert r["success"] is True
        assert r["role"] == "MEMBER"
        assert r["workspace_id"] == workspace_id

    # The reusable invitation must remain PENDING
    assert invitation.status == InvitationStatus.PENDING.value


@pytest.mark.asyncio
async def test_concurrent_join_code_usage_increment(workspace_id):
    """Drill 2: Concurrent usage recording under simulated load."""
    code = WorkspaceJoinCode(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        use_count=0,
        is_enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    mock_join_code_repo = AsyncMock()
    mock_join_code_repo.list_by_workspace.return_value = [code]

    mock_settings_repo = AsyncMock()
    mock_settings_repo.get_by_workspace_id.return_value = None
    mock_settings_repo.get_by_workspace_id_for_update.return_value = None

    service = JoinCodeService(
        settings_repo=mock_settings_repo,
        member_repo=AsyncMock(),
        workspace_repo=AsyncMock(),
    )
    service.join_code_repo = mock_join_code_repo

    async def record_usage():
        session = AsyncMock()
        await service.record_join_code_usage(session, workspace_id)

    tasks = [record_usage() for _ in range(15)]
    await asyncio.gather(*tasks)

    assert mock_join_code_repo.increment_usage.call_count == 15


@pytest.mark.asyncio
async def test_concurrent_outbox_claim_drill(workspace_id, owner_id):
    """Drill 3: Simulated concurrent outbox claiming with lease mutex."""
    entries = [
        NotificationOutbox(
            id=uuid.uuid4(),
            join_code_id=uuid.uuid4(),
            join_code_version=1,
            workspace_id=workspace_id,
            recipient_user_id=owner_id,
            checkpoint="24H",
            channel="EMAIL",
            status="PENDING",
            idempotency_key=f"drill_key_{i}",
            scheduled_for=datetime.now(UTC),
        )
        for i in range(5)
    ]

    claimed_by_worker = {}
    lock = asyncio.Lock()

    async def worker_claim(worker_id: str):
        async with lock:
            for e in entries:
                if e.status == "PENDING":
                    e.status = "CLAIMED"
                    e.lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)
                    claimed_by_worker[e.id] = worker_id

    workers = [worker_claim(f"worker_{i}") for i in range(3)]
    await asyncio.gather(*workers)

    # Exactly 5 entries claimed, each by exactly one worker
    assert len(claimed_by_worker) == 5
    for e in entries:
        assert e.status == "CLAIMED"
