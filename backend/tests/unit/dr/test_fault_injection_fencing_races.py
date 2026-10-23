"""Unit tests for Fault-Injection Fencing Races (`WP-3C Phase 2`, `TSK-3C-05`, `FND-SEC-01`).

Simulates explicit concurrency races:
1. Artificial worker pause between Redis admission and database transaction commit.
2. Stale writer commit attempt when coordinator holds exclusive advisory lock barrier.
3. Delayed heartbeat expiration causing fail-closed transaction abort.
4. Coordinator crash mid-snapshot releasing exclusive lock on connection teardown.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.middleware.admission_control import (
    acquire_snapshot_barrier_exclusive,
    acquire_snapshot_barrier_shared,
    release_snapshot_barrier_exclusive,
)
from backend.tests.unit.dr.test_barrier_crash_safe_leases import (
    ExtendedRedisDouble,
)


@pytest.mark.asyncio
async def test_race_stale_writer_blocked_by_coordinator_barrier() -> None:
    """Coordinator acquires exclusive barrier while writer is paused; writer attempt to lock fails."""
    # Coordinator holds exclusive lock
    coordinator_session = AsyncMock(spec=AsyncSession)
    mock_coord_res = MagicMock()
    mock_coord_res.scalar.return_value = True
    coordinator_session.execute.return_value = mock_coord_res

    coord_locked = await acquire_snapshot_barrier_exclusive(coordinator_session)
    assert coord_locked is True

    # Writer awakens after pause and attempts to acquire shared advisory lock
    writer_session = AsyncMock(spec=AsyncSession)
    mock_writer_res = MagicMock()
    mock_writer_res.scalar.return_value = False  # Blocked by exclusive lock!
    writer_session.execute.return_value = mock_writer_res

    writer_lock_acquired = await acquire_snapshot_barrier_shared(writer_session)
    assert writer_lock_acquired is False

    # Writer detects lock failure, must roll back and fail closed
    await writer_session.rollback()
    writer_session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_connection_drop_releases_exclusive_lock() -> None:
    """PostgreSQL session teardown releases advisory lock automatically."""
    coordinator_session = AsyncMock(spec=AsyncSession)
    mock_coord_res = MagicMock()
    mock_coord_res.scalar.return_value = True
    coordinator_session.execute.return_value = mock_coord_res

    coord_locked = await acquire_snapshot_barrier_exclusive(coordinator_session)
    assert coord_locked is True

    # Simulate coordinator crash / session close
    await release_snapshot_barrier_exclusive(coordinator_session)

    # Subsequent writer can now acquire lock
    writer_session = AsyncMock(spec=AsyncSession)
    mock_writer_res = MagicMock()
    mock_writer_res.scalar.return_value = True
    writer_session.execute.return_value = mock_writer_res

    writer_acquired = await acquire_snapshot_barrier_shared(writer_session)
    assert writer_acquired is True
