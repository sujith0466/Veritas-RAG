"""Unit tests for Phase 2 Milestone 2: Embedding Pipeline (Milestone E - Worker Layer).

Verifies `CeleryEmbeddingWorker` session orchestration, jittered exponential backoff calculation,
Celery state update callbacks (`update_state`), and exact retry boundary differentiation (`RECOVERABLE` vs `FATAL`).
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.embedding.models.embedding_job import EmbeddingJob
from backend.modules.embedding.schemas.errors import ProviderAuthenticationError, ProviderTimeoutError
from backend.modules.embedding.workers.embedding_worker import CeleryEmbeddingWorker


class RetrySignal(Exception):
    """Exception raised when mock Celery task.retry() is invoked."""
    pass


@pytest.mark.asyncio
class TestCeleryEmbeddingWorker:
    """Test suite verifying worker backoff calculations and Celery task coordination."""

    def test_calculate_jittered_backoff(self) -> None:
        # Retry 0: base 5.0 * (2**0) = 5.0 + jitter(1..5) => 6.0 .. 10.0
        b0 = CeleryEmbeddingWorker.calculate_jittered_backoff(retry_count=0, base_seconds=5.0)
        assert 6.0 <= b0 <= 10.0

        # Retry 2: base 5.0 * (2**2) = 20.0 + jitter(1..5) => 21.0 .. 25.0
        b2 = CeleryEmbeddingWorker.calculate_jittered_backoff(retry_count=2, base_seconds=5.0)
        assert 21.0 <= b2 <= 25.0

        # Max limit ceiling check
        b_max = CeleryEmbeddingWorker.calculate_jittered_backoff(retry_count=10, base_seconds=100.0, max_seconds=300.0)
        assert b_max <= 300.0

    async def test_execute_batch_success(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        worker = CeleryEmbeddingWorker(mock_session)

        job_id = uuid.uuid4()
        mock_job = EmbeddingJob(
            id=job_id,
            tenant_id="t1",
            document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            provider="openai",
            model_name="m",
            total_chunks=10,
            processed_chunks=10,
            total_tokens_consumed=150,
            status="COMPLETED",
        )
        worker.service.process_embedding_batch = AsyncMock(return_value=mock_job)

        mock_celery = MagicMock()
        mock_celery.update_state = MagicMock()

        result = await worker.execute_batch(
            celery_task=mock_celery,
            job_id=job_id,
            tenant_id="t1",
            batch_size=50,
        )

        assert result["status"] == "success"
        assert result["processed_chunks"] == 10
        assert result["tokens_consumed"] == 150
        mock_session.commit.assert_awaited_once()
        mock_celery.update_state.assert_called_once_with(
            state="SUCCESS",
            meta={
                "job_id": str(job_id),
                "processed": 10,
                "total": 10,
                "tokens": 150,
            },
        )

    async def test_execute_batch_retries_recoverable_error(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        worker = CeleryEmbeddingWorker(mock_session)

        job_id = uuid.uuid4()
        # ProviderTimeoutError is RECOVERABLE (EMB_004)
        worker.service.process_embedding_batch = AsyncMock(side_effect=ProviderTimeoutError("Gateway timeout"))

        mock_celery = MagicMock()
        mock_celery.request.retries = 1
        mock_celery.max_retries = 3
        mock_celery.retry.side_effect = RetrySignal("Retry triggered")

        with pytest.raises(RetrySignal):
            await worker.execute_batch(celery_task=mock_celery, job_id=job_id, tenant_id="t1")

        mock_session.rollback.assert_awaited_once()
        mock_celery.retry.assert_called_once()
        kwargs = mock_celery.retry.call_args[1]
        assert "exc" in kwargs
        assert isinstance(kwargs["exc"], ProviderTimeoutError)
        assert "countdown" in kwargs
        assert kwargs["countdown"] >= 10.0

    async def test_execute_batch_no_retry_on_fatal_error(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        worker = CeleryEmbeddingWorker(mock_session)

        job_id = uuid.uuid4()
        # ProviderAuthenticationError is FATAL (EMB_005)
        worker.service.process_embedding_batch = AsyncMock(side_effect=ProviderAuthenticationError("Invalid API key"))

        mock_celery = MagicMock()
        mock_celery.request.retries = 0
        mock_celery.max_retries = 3
        mock_celery.retry = MagicMock()

        with pytest.raises(ProviderAuthenticationError):
            await worker.execute_batch(celery_task=mock_celery, job_id=job_id, tenant_id="t1")

        mock_session.rollback.assert_awaited_once()
        mock_celery.retry.assert_not_called()
