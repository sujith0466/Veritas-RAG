"""Unit tests for ProcessingJobService (F6.6, F6.7)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.document.models.job import ProcessingJob
from backend.document.models.job_step import ProcessingJobStep
from backend.document.services.processing_job_service import ProcessingJobService

pytestmark = pytest.mark.asyncio


class DummyAsyncLock:
    async def __aenter__(self):
        return "lock_token"

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_job_repo():
    return AsyncMock()


@pytest.fixture
def mock_step_repo():
    return AsyncMock()


@pytest.fixture
def mock_audit_repo():
    return AsyncMock()


@pytest.fixture
def mock_failed_job_repo():
    return AsyncMock()


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
def mock_session():
    mock_s = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_s.execute.return_value = mock_res
    return mock_s


@pytest.fixture
def job_service(
    mock_job_repo,
    mock_step_repo,
    mock_audit_repo,
    mock_failed_job_repo,
    mock_redis,
):
    return ProcessingJobService(
        job_repo=mock_job_repo,
        step_repo=mock_step_repo,
        audit_repo=mock_audit_repo,
        redis_client=mock_redis,
        failed_job_repo=mock_failed_job_repo,
    )


async def test_enqueue_job_idempotent(job_service, mock_job_repo, mock_session):
    doc_id = uuid.uuid4()
    version_id = uuid.uuid4()

    # Case 1: Existing active job returned
    existing_job = ProcessingJob(
        id=uuid.uuid4(),
        document_id=doc_id,
        status="QUEUED",
        current_step="upload",
    )
    mock_job_repo.get_by_idempotency_key.return_value = existing_job

    job = await job_service.enqueue_job(
        document_id=doc_id,
        priority=1,
        started_at=None,
        actor="test_user",
        session=mock_session,
        version_id=version_id,
    )
    assert job == existing_job
    mock_job_repo.create.assert_not_called()

    # Case 2: New job enqueued
    mock_job_repo.get_by_idempotency_key.return_value = None
    new_job = ProcessingJob(
        id=uuid.uuid4(),
        document_id=doc_id,
        status="PENDING",
        current_step="upload",
    )
    mock_job_repo.create.return_value = new_job

    job2 = await job_service.enqueue_job(
        document_id=doc_id,
        priority=2,
        started_at=None,
        actor="test_user",
        session=mock_session,
        version_id=version_id,
    )
    assert job2 == new_job
    mock_job_repo.create.assert_called_once()


async def test_claim_job_with_lock(job_service, mock_job_repo, mock_session):
    job_id = uuid.uuid4()
    job_obj = ProcessingJob(
        id=job_id,
        document_id=uuid.uuid4(),
        status="QUEUED",
        current_step="upload",
    )
    mock_job_repo.get_by_id.return_value = job_obj

    with patch("backend.document.services.processing_job_service.acquire_lock", return_value=DummyAsyncLock()):
        claimed = await job_service.claim_job(job_id, worker_id="worker_1", session=mock_session)

        assert claimed is not None
        assert claimed.status == "CLAIMED"
        assert claimed.claimed_by_worker == "worker_1"
        assert claimed.claimed_at is not None
        mock_session.flush.assert_called()


async def test_start_and_complete_step(job_service, mock_job_repo, mock_step_repo, mock_session):
    job_id = uuid.uuid4()
    job_obj = ProcessingJob(
        id=job_id,
        document_id=uuid.uuid4(),
        status="CLAIMED",
        current_step="upload",
    )
    mock_job_repo.get_by_id.return_value = job_obj

    step_obj = ProcessingJobStep(
        id=uuid.uuid4(),
        job_id=job_id,
        step_name="extraction",
        step_status="IN_PROGRESS",
        started_at=datetime.now(UTC),
    )
    mock_step_repo.create_step.return_value = step_obj
    mock_step_repo.get_step.return_value = step_obj

    # 1. Start step
    step = await job_service.start_step(job_id, "extraction", "worker_1", mock_session)
    assert step == step_obj
    assert job_obj.status == "PROCESSING"
    assert job_obj.current_step == "extraction"

    # 2. Complete step
    await job_service.complete_step(
        job_id, "extraction", "worker_1", {"pages": 12}, mock_session
    )
    mock_step_repo.update_step_status.assert_called_once()
    assert job_obj.step_metrics["extraction"] == {"pages": 12}


async def test_record_step_error_retries_and_dlq(
    job_service, mock_job_repo, mock_step_repo, mock_failed_job_repo, mock_session
):
    job_id = uuid.uuid4()
    job_obj = ProcessingJob(
        id=job_id,
        document_id=uuid.uuid4(),
        status="PROCESSING",
        current_step="extraction",
        retry_count=0,
        max_retries=3,
        step_metrics={},
    )
    mock_job_repo.get_by_id.return_value = job_obj
    mock_step_repo.get_step.return_value = MagicMock(id=uuid.uuid4())

    # 1. Non-fatal retry
    await job_service.record_step_error(
        job_id=job_id,
        step_name="extraction",
        worker_id="worker_1",
        error_code="TIMEOUT",
        error_message="Worker timeout",
        is_fatal=False,
        session=mock_session,
    )
    assert job_obj.retry_count == 1
    assert job_obj.status == "QUEUED"
    mock_failed_job_repo.create_diagnostics.assert_not_called()

    # 2. Fatal error moves to DLQ and saves diagnostics
    await job_service.record_step_error(
        job_id=job_id,
        step_name="extraction",
        worker_id="worker_1",
        error_code="CORRUPT_FILE",
        error_message="Corrupted PDF bytes",
        is_fatal=True,
        session=mock_session,
    )
    assert job_obj.status == "DLQ"
    assert job_obj.error_code == "CORRUPT_FILE"
    assert job_obj.dlq_reason == "[extraction] CORRUPT_FILE: Corrupted PDF bytes"
    mock_failed_job_repo.create_diagnostics.assert_called_once()


async def test_requeue_stale_jobs(job_service, mock_job_repo, mock_redis, mock_session):
    stale_job1 = ProcessingJob(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        status="CLAIMED",
        claimed_by_worker="dead_worker",
    )
    mock_job_repo.get_stale_claimed_jobs.return_value = [stale_job1]
    mock_redis.exists.return_value = False  # Lock released/expired

    count = await job_service.requeue_stale_jobs(threshold_minutes=5, session=mock_session)

    assert count == 1
    assert stale_job1.status == "QUEUED"
    assert stale_job1.claimed_by_worker is None
    assert stale_job1.claimed_at is None
