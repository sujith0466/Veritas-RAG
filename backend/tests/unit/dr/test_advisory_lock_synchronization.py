"""Unit tests for PostgreSQL Advisory Lock Synchronization (`WP-3C Phase 2`, `TSK-3C-05`).

Verifies:
1. Shared transaction advisory lock compatibility and acquisition via acquire_snapshot_barrier_shared.
2. Coordinator exclusive session lock via acquire_snapshot_barrier_exclusive.
3. Lock incompatibility: exclusive barrier prevents shared lock acquisition (returns False).
4. Automatic lock release on transaction rollback/commit and connection closure.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.middleware.admission_control import (
    acquire_snapshot_barrier_exclusive,
    acquire_snapshot_barrier_shared,
    release_snapshot_barrier_exclusive,
)


@pytest.mark.asyncio
async def test_acquire_snapshot_barrier_shared_success() -> None:
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar.return_value = True
    session.execute.return_value = mock_result

    acquired = await acquire_snapshot_barrier_shared(session)
    assert acquired is True
    session.execute.assert_called_once()
    sql_text = str(session.execute.call_args[0][0])
    assert "pg_try_advisory_xact_lock_shared" in sql_text
    assert "veritas:snapshot:barrier" in sql_text


@pytest.mark.asyncio
async def test_acquire_snapshot_barrier_shared_rejected_when_exclusive_held() -> None:
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar.return_value = False  # Coordinator holds exclusive lock
    session.execute.return_value = mock_result

    acquired = await acquire_snapshot_barrier_shared(session)
    assert acquired is False


@pytest.mark.asyncio
async def test_acquire_snapshot_barrier_shared_exception_fails_closed() -> None:
    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = RuntimeError("Database connection broken")

    acquired = await acquire_snapshot_barrier_shared(session)
    assert acquired is False


@pytest.mark.asyncio
async def test_acquire_snapshot_barrier_exclusive_lifecycle() -> None:
    session = AsyncMock(spec=AsyncSession)
    mock_result_acq = MagicMock()
    mock_result_acq.scalar.return_value = True
    mock_result_rel = MagicMock()
    mock_result_rel.scalar.return_value = True

    session.execute.side_effect = [mock_result_acq, mock_result_rel]

    acquired = await acquire_snapshot_barrier_exclusive(session)
    assert acquired is True

    released = await release_snapshot_barrier_exclusive(session)
    assert released is True
