"""Unit tests for document pipeline watchdog worker Celery task."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.document.workers.watchdog_worker import sweep_stale_pipeline_documents_task


def test_sweep_stale_pipeline_documents_task_no_event_loop():
    """Verify synchronous Celery watchdog task executes without a pre-existing event loop."""
    asyncio.set_event_loop(None)

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_factory = MagicMock(return_value=MagicMock(return_value=mock_session))

    with patch("backend.document.workers.watchdog_worker.get_session_factory", mock_factory), \
         patch("backend.document.workers.watchdog_worker.sweep_stale_pipeline_documents", new_callable=AsyncMock) as mock_sweep:

        mock_sweep.return_value = 2

        sweep_stale_pipeline_documents_task()

        mock_sweep.assert_called_once_with(stale_threshold_minutes=15, session=mock_session)
        mock_session.commit.assert_called_once()


def test_sweep_stale_pipeline_documents_task_no_stale_docs():
    """Verify commit is skipped when no documents were recovered."""
    asyncio.set_event_loop(None)

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_factory = MagicMock(return_value=MagicMock(return_value=mock_session))

    with patch("backend.document.workers.watchdog_worker.get_session_factory", mock_factory), \
         patch("backend.document.workers.watchdog_worker.sweep_stale_pipeline_documents", new_callable=AsyncMock) as mock_sweep:

        mock_sweep.return_value = 0

        sweep_stale_pipeline_documents_task()

        mock_sweep.assert_called_once_with(stale_threshold_minutes=15, session=mock_session)
        mock_session.commit.assert_not_called()


def test_sweep_stale_pipeline_documents_task_exception_propagates():
    """Verify unhandled exceptions bubble up properly to Celery worker."""
    asyncio.set_event_loop(None)

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_factory = MagicMock(return_value=MagicMock(return_value=mock_session))

    with patch("backend.document.workers.watchdog_worker.get_session_factory", mock_factory), \
         patch("backend.document.workers.watchdog_worker.sweep_stale_pipeline_documents", new_callable=AsyncMock) as mock_sweep:

        mock_sweep.side_effect = ValueError("Database query failed")

        with pytest.raises(ValueError, match="Database query failed"):
            sweep_stale_pipeline_documents_task()
