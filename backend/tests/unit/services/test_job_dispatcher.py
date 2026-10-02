"""Unit tests for JobDispatcher service and resilient dispatch outbox (D2.1)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import uuid

import pytest

from backend.document.models.job import DispatchState, ProcessingJob
from backend.document.services.job_dispatcher import JobDispatcher, DispatchResult


@pytest.fixture
def sample_job():
    return ProcessingJob(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        version_id=uuid.uuid4(),
        status="PENDING",
        current_step="upload",
        dispatch_state=DispatchState.PENDING_DISPATCH.value,
        retry_count=0,
        max_retries=3,
    )


def test_job_dispatcher_success_sync(sample_job):
    """Test successful dispatch sets DISPATCHED, persists task_id, and clears error."""
    mock_task = MagicMock()
    mock_task.id = "celery-task-12345"

    with patch("backend.document.workers.ingestion.process_document_job.apply_async", return_value=mock_task) as mock_apply:
        result = JobDispatcher.dispatch_job_sync(sample_job, queue="ingestion")

        assert result.success is True
        assert result.task_id == "celery-task-12345"
        assert result.dispatch_state == DispatchState.DISPATCHED.value
        assert result.error is None
        assert result.deduplicated is False

        assert sample_job.dispatch_state == DispatchState.DISPATCHED.value
        assert sample_job.celery_task_id == "celery-task-12345"
        assert sample_job.dispatched_at is not None
        assert sample_job.dispatch_error is None

        mock_apply.assert_called_once_with(args=[str(sample_job.id)], queue="ingestion")


def test_job_dispatcher_broker_failure_sync(sample_job):
    """Test broker failure transitions job to FAILED_DISPATCH with error captured."""
    with patch(
        "backend.document.workers.ingestion.process_document_job.apply_async",
        side_effect=ConnectionError("Redis connection refused"),
    ):
        result = JobDispatcher.dispatch_job_sync(sample_job, queue="ingestion")

        assert result.success is False
        assert result.task_id is None
        assert result.dispatch_state == DispatchState.FAILED_DISPATCH.value
        assert "ConnectionError: Redis connection refused" in result.error

        assert sample_job.dispatch_state == DispatchState.FAILED_DISPATCH.value
        assert "Redis connection refused" in sample_job.dispatch_error
        assert sample_job.dispatched_at is not None


def test_job_dispatcher_deduplication_cooldown(sample_job):
    """Test dispatch is deduplicated if recently dispatched within cooldown window."""
    sample_job.dispatch_state = DispatchState.DISPATCHED.value
    sample_job.celery_task_id = "existing-task-999"
    sample_job.dispatched_at = datetime.now(timezone.utc) - timedelta(seconds=20)

    with patch("backend.document.workers.ingestion.process_document_job.apply_async") as mock_apply:
        result = JobDispatcher.dispatch_job_sync(sample_job, queue="ingestion")

        assert result.success is True
        assert result.task_id == "existing-task-999"
        assert result.deduplicated is True
        mock_apply.assert_not_called()


def test_job_dispatcher_force_bypass_cooldown(sample_job):
    """Test force=True bypasses deduplication cooldown."""
    sample_job.dispatch_state = DispatchState.DISPATCHED.value
    sample_job.celery_task_id = "old-task-888"
    sample_job.dispatched_at = datetime.now(timezone.utc) - timedelta(seconds=10)

    mock_task = MagicMock()
    mock_task.id = "new-task-777"

    with patch("backend.document.workers.ingestion.process_document_job.apply_async", return_value=mock_task) as mock_apply:
        result = JobDispatcher.dispatch_job_sync(sample_job, queue="ingestion", force=True)

        assert result.success is True
        assert result.task_id == "new-task-777"
        assert result.deduplicated is False
        mock_apply.assert_called_once()


def test_job_dispatcher_skip_active_job(sample_job):
    """Test jobs already actively processing are not re-dispatched."""
    sample_job.status = "PROCESSING"
    sample_job.dispatch_state = DispatchState.ACKNOWLEDGED.value
    sample_job.celery_task_id = "active-task-111"

    with patch("backend.document.workers.ingestion.process_document_job.apply_async") as mock_apply:
        result = JobDispatcher.dispatch_job_sync(sample_job, queue="ingestion")

        assert result.success is True
        assert result.task_id == "active-task-111"
        assert result.deduplicated is True
        mock_apply.assert_not_called()


@pytest.mark.asyncio
async def test_job_dispatcher_async(sample_job):
    """Test asynchronous dispatch wrapper."""
    mock_task = MagicMock()
    mock_task.id = "async-task-555"

    with patch("backend.document.workers.ingestion.process_document_job.apply_async", return_value=mock_task):
        result = await JobDispatcher.dispatch_job(sample_job, session=None, queue="ingestion")

        assert result.success is True
        assert result.task_id == "async-task-555"
        assert sample_job.dispatch_state == DispatchState.DISPATCHED.value
