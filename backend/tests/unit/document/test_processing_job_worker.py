"""Unit tests for processing job worker Celery tasks."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.document.workers.processing_job_worker import requeue_stale_jobs


def test_requeue_stale_jobs_task_no_event_loop():
    """Verify requeue_stale_jobs runs without a pre-existing event loop."""
    asyncio.set_event_loop(None)

    mock_service = MagicMock()
    mock_service.requeue_stale_jobs = AsyncMock(return_value=3)
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    class MockContextManager:
        async def __aenter__(self):
            return mock_service, mock_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("backend.document.workers.processing_job_worker._get_job_service", return_value=MockContextManager()):
        # Calling bound Celery task without args injects self automatically
        requeue_stale_jobs()

        mock_service.requeue_stale_jobs.assert_called_once_with(threshold_minutes=5, session=mock_session)
        mock_session.commit.assert_called_once()
