"""Unit tests for Phase 6 WP-ARCH Remainder remediation.

Covers:
- ARCH-003: Qdrant collection name contract type annotation.
- ARCH-004: Document status API current_step accuracy during active downstream processing.
- ARCH-005: Celery Beat watchdog for stuck chunking/embedding/vector sync documents.
- PERF-002: Reusing singleton AsyncEngine for database health check probes.
- PERF-003: Global Celery task timeouts and worker_prefetch_multiplier = 1.
- PERF-004: Explicit Redis connection pool disconnect on loop teardown.
- OBS-001: Kubernetes root /ready route registration and response.
"""

import asyncio
from datetime import UTC, datetime, timedelta
import inspect
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.cache.client import (
    _state as cache_state,
    disconnect_redis_pool,
    get_redis_client,
    get_redis_pool,
)
from backend.cache.locks import LockAcquisitionError
from backend.core.config.qdrant import QdrantSettings
from backend.database.engine import _state as db_state, check_db_health, close_db, get_raw_engine
from backend.document.models.document import Document, DocumentStatus
from backend.document.models.job import ProcessingJob
from backend.document.services.document_service import DocumentService
from backend.document.workers.watchdog_worker import sweep_stale_pipeline_documents
from backend.main import create_app
from backend.modules.chunking.workers.tasks import process_document_chunking_task
from backend.modules.embedding.models.embedding_job import EmbeddingJob
from backend.tasks.celery_app import celery_app


# ==============================================================================
# ARCH-003: Qdrant collection name contract
# ==============================================================================
class TestArch003QdrantConfig:
    """ARCH-003: Verify collection_name accepts string/int tenant_id and is not misnamed dimension: int."""

    def test_collection_name_accepts_tenant_id_string(self):
        settings = QdrantSettings(collection_prefix="test_prefix")
        name = settings.collection_name("tenant_123")
        assert name == "test_prefix_knowledge_tenant_123"

    def test_collection_name_signature_parameter_name(self):
        sig = inspect.signature(QdrantSettings.collection_name)
        params = list(sig.parameters.keys())
        assert "self" in params
        param_name = params[1]
        assert param_name != "dimension", "Parameter should be tenant_id, not dimension"
        assert param_name == "tenant_id"


# ==============================================================================
# ARCH-004: API status current_step reflection during chunking/embedding/sync
# ==============================================================================
class TestArch004DocumentStatusStep:
    """ARCH-004: Ensure get_status does not report current_step='completed' during downstream stages."""

    @pytest.mark.asyncio
    async def test_chunking_status_reports_step_chunking_not_completed(self):
        mock_repo = MagicMock()
        mock_job_repo = MagicMock()
        doc_service = DocumentService(doc_repo=mock_repo, job_repo=mock_job_repo)
        doc_id = uuid.uuid4()
        now = datetime.now(UTC)

        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.status = DocumentStatus.CHUNKING
        mock_doc.created_at = now
        mock_doc.updated_at = now

        # Simulate job that completed extraction stage with current_step="completed"
        mock_job = MagicMock()
        mock_job.current_step = "completed"
        mock_job.retry_count = 0
        mock_job.error_code = None
        mock_job.error_message = None

        mock_repo.get_by_id = AsyncMock(return_value=mock_doc)
        mock_job_repo.get_by_document_id = AsyncMock(return_value=mock_job)

        resp = await doc_service.get_status(doc_id, "tenant-1", AsyncMock())
        assert resp is not None
        assert resp.current_step == "chunking", f"Expected 'chunking', got {resp.current_step}"
        assert resp.progress_percent == 65

    @pytest.mark.asyncio
    async def test_embedding_and_vector_sync_report_accurate_step(self):
        mock_repo = MagicMock()
        mock_job_repo = MagicMock()
        doc_service = DocumentService(doc_repo=mock_repo, job_repo=mock_job_repo)
        now = datetime.now(UTC)

        for status_val, expected_step, expected_prog in [
            (DocumentStatus.EMBEDDING, "embedding", 80),
            (DocumentStatus.VECTOR_SYNC, "vector_sync", 90),
            (DocumentStatus.PROCESSED, "processed", 50),
        ]:
            doc_id = uuid.uuid4()
            mock_doc = MagicMock()
            mock_doc.id = doc_id
            mock_doc.status = status_val
            mock_doc.created_at = now
            mock_doc.updated_at = now

            mock_job = MagicMock()
            mock_job.current_step = "completed"
            mock_job.retry_count = 0
            mock_job.error_code = None
            mock_job.error_message = None

            mock_repo.get_by_id = AsyncMock(return_value=mock_doc)
            mock_job_repo.get_by_document_id = AsyncMock(return_value=mock_job)

            resp = await doc_service.get_status(doc_id, "tenant-1", AsyncMock())
            assert resp is not None
            assert resp.current_step == expected_step
            assert resp.progress_percent == expected_prog

    @pytest.mark.asyncio
    async def test_ready_status_reports_completed(self):
        mock_repo = MagicMock()
        mock_job_repo = MagicMock()
        doc_service = DocumentService(doc_repo=mock_repo, job_repo=mock_job_repo)
        now = datetime.now(UTC)
        doc_id = uuid.uuid4()

        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.status = DocumentStatus.READY
        mock_doc.created_at = now
        mock_doc.updated_at = now

        mock_job = MagicMock()
        mock_job.current_step = "completed"
        mock_job.retry_count = 0
        mock_job.error_code = None
        mock_job.error_message = None

        mock_repo.get_by_id = AsyncMock(return_value=mock_doc)
        mock_job_repo.get_by_document_id = AsyncMock(return_value=mock_job)

        resp = await doc_service.get_status(doc_id, "tenant-1", AsyncMock())
        assert resp is not None
        assert resp.current_step == "completed"
        assert resp.progress_percent == 100


# ==============================================================================
# ARCH-005: Celery Beat Watchdog for stuck pipeline documents
# ==============================================================================
class TestArch005PipelineWatchdog:
    """ARCH-005: Watchdog sweeps documents stuck in CHUNKING/EMBEDDING/VECTOR_SYNC."""

    def test_watchdog_task_registration_and_beat_schedule(self):
        """Verify task is included in celery_app and scheduled in beat_schedule."""
        assert "backend.document.workers.watchdog_worker" in celery_app.conf.include
        beat = celery_app.conf.beat_schedule
        assert "document-pipeline-watchdog" in beat
        assert beat["document-pipeline-watchdog"]["task"] == "documents.sweep_stale_pipeline_documents"
        assert beat["document-pipeline-watchdog"]["schedule"] == 300.0

    @pytest.mark.asyncio
    async def test_sweep_requeues_stuck_document_with_retries(self):
        mock_session = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        mock_redis.exists.return_value = False

        stale_time = datetime.now(UTC) - timedelta(minutes=20)
        doc = Document(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            status=DocumentStatus.CHUNKING,
            updated_at=stale_time,
            is_deleted=False,
            latest_version_id=uuid.uuid4(),
        )
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc.id,
            status="PROCESSING",
            current_step="chunking",
            retry_count=1,
            max_retries=3,
            is_deleted=False,
            created_at=stale_time,
        )

        mock_doc_result = MagicMock()
        mock_doc_result.scalars.return_value.all.return_value = [doc]
        mock_job_result = MagicMock()
        mock_job_result.scalar_one_or_none.return_value = job

        def mock_execute_side_effect(stmt):
            sql = str(stmt).lower()
            if "processingjob" in sql or "processing_job" in sql:
                return mock_job_result
            return mock_doc_result

        mock_session.execute.side_effect = mock_execute_side_effect

        with patch("backend.modules.chunking.workers.tasks.process_document_chunking_task.apply_async") as mock_dispatch:
            handled = await sweep_stale_pipeline_documents(
                stale_threshold_minutes=15,
                session=mock_session,
                redis_client=mock_redis,
            )

            assert handled == 1
            assert job.retry_count == 2
            assert job.status == "QUEUED"
            assert mock_dispatch.called

    @pytest.mark.asyncio
    async def test_sweep_marks_failed_when_retries_exhausted(self):
        mock_session = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        mock_redis.exists.return_value = False

        stale_time = datetime.now(UTC) - timedelta(minutes=20)
        doc = Document(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            status=DocumentStatus.VECTOR_SYNC,
            updated_at=stale_time,
            is_deleted=False,
            latest_version_id=uuid.uuid4(),
        )
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc.id,
            status="PROCESSING",
            current_step="vector_sync",
            retry_count=3,
            max_retries=3,  # Retries exhausted
            is_deleted=False,
            created_at=stale_time,
        )

        mock_doc_result = MagicMock()
        mock_doc_result.scalars.return_value.all.return_value = [doc]
        mock_job_result = MagicMock()
        mock_job_result.scalar_one_or_none.return_value = job

        def mock_execute_side_effect(stmt):
            sql = str(stmt).lower()
            if "processingjob" in sql or "processing_job" in sql:
                return mock_job_result
            return mock_doc_result

        mock_session.execute.side_effect = mock_execute_side_effect

        with patch("backend.document.services.failure_service.PipelineFailureSynchronizer.record_pipeline_failure", new_callable=AsyncMock) as mock_failure:
            handled = await sweep_stale_pipeline_documents(
                stale_threshold_minutes=15,
                session=mock_session,
                redis_client=mock_redis,
            )

            assert handled == 1
            assert mock_failure.called
            call_kwargs = mock_failure.call_args[1]
            assert call_kwargs["error_code"] == "STUCK_PIPELINE_TIMEOUT"
            assert call_kwargs["document_id"] == doc.id

    @pytest.mark.asyncio
    async def test_sweep_skips_when_vector_sync_lock_active(self):
        """Active vector sync lock prevents duplicate processing and premature failure."""
        mock_session = AsyncMock()
        version_id = uuid.uuid4()
        stale_time = datetime.now(UTC) - timedelta(minutes=20)
        doc = Document(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            status=DocumentStatus.VECTOR_SYNC,
            updated_at=stale_time,
            is_deleted=False,
            latest_version_id=version_id,
        )
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc.id,
            status="PROCESSING",
            current_step="vector_sync",
            retry_count=1,
            max_retries=3,
            is_deleted=False,
            created_at=stale_time,
        )

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        # Stage lock lock:vector:sync:{version_id} exists
        mock_redis.exists.side_effect = lambda k: k == f"lock:vector:sync:{version_id}"

        mock_doc_result = MagicMock()
        mock_doc_result.scalars.return_value.all.return_value = [doc]
        mock_job_result = MagicMock()
        mock_job_result.scalar_one_or_none.return_value = job

        def mock_execute_side_effect(stmt):
            sql = str(stmt).lower()
            if "processingjob" in sql or "processing_job" in sql:
                return mock_job_result
            return mock_doc_result

        mock_session.execute.side_effect = mock_execute_side_effect

        with patch("backend.modules.vector.workers.tasks.sync_vectors_to_qdrant_task.apply_async") as mock_dispatch:
            handled = await sweep_stale_pipeline_documents(
                stale_threshold_minutes=15,
                session=mock_session,
                redis_client=mock_redis,
            )

            assert handled == 0
            assert job.retry_count == 1  # Unmodified
            assert not mock_dispatch.called

    @pytest.mark.asyncio
    async def test_sweep_skips_when_embedding_lock_active(self):
        """Active embedding job lock prevents duplicate batch processing."""
        mock_session = AsyncMock()
        version_id = uuid.uuid4()
        emb_job_id = uuid.uuid4()
        stale_time = datetime.now(UTC) - timedelta(minutes=20)
        doc = Document(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            status=DocumentStatus.EMBEDDING,
            updated_at=stale_time,
            is_deleted=False,
            latest_version_id=version_id,
        )
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc.id,
            status="PROCESSING",
            current_step="embedding",
            retry_count=1,
            max_retries=3,
            is_deleted=False,
            created_at=stale_time,
        )
        emb_job = EmbeddingJob(
            id=emb_job_id,
            tenant_id="tenant-1",
            document_id=doc.id,
            document_version_id=version_id,
            status="PROCESSING",
            provider="openai",
            model_name="text-embedding-3-small",
            total_chunks=10,
        )

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        # Stage lock lock:embedding:job:{emb_job_id} exists
        mock_redis.exists.side_effect = lambda k: k == f"lock:embedding:job:{emb_job_id}"

        mock_doc_result = MagicMock()
        mock_doc_result.scalars.return_value.all.return_value = [doc]
        mock_job_result = MagicMock()
        mock_job_result.scalar_one_or_none.return_value = job
        mock_emb_result = MagicMock()
        mock_emb_result.scalar_one_or_none.return_value = emb_job

        def mock_execute_side_effect(stmt):
            sql = str(stmt).lower()
            if "embeddingjob" in sql or "embedding_job" in sql:
                return mock_emb_result
            if "processingjob" in sql or "processing_job" in sql:
                return mock_job_result
            return mock_doc_result

        mock_session.execute.side_effect = mock_execute_side_effect

        with patch("backend.modules.embedding.workers.tasks.process_embedding_batch_task.apply_async") as mock_dispatch:
            handled = await sweep_stale_pipeline_documents(
                stale_threshold_minutes=15,
                session=mock_session,
                redis_client=mock_redis,
            )

            assert handled == 0
            assert job.retry_count == 1
            assert not mock_dispatch.called

    @pytest.mark.asyncio
    async def test_sweep_skips_when_chunking_lock_active(self):
        """Active chunking lock prevents duplicate chunking tasks."""
        mock_session = AsyncMock()
        version_id = uuid.uuid4()
        stale_time = datetime.now(UTC) - timedelta(minutes=20)
        doc = Document(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            status=DocumentStatus.CHUNKING,
            updated_at=stale_time,
            is_deleted=False,
            latest_version_id=version_id,
        )
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc.id,
            status="PROCESSING",
            current_step="chunking",
            retry_count=1,
            max_retries=3,
            is_deleted=False,
            created_at=stale_time,
        )

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        mock_redis.exists.side_effect = lambda k: k == f"lock:chunking:{version_id}"

        mock_doc_result = MagicMock()
        mock_doc_result.scalars.return_value.all.return_value = [doc]
        mock_job_result = MagicMock()
        mock_job_result.scalar_one_or_none.return_value = job

        def mock_execute_side_effect(stmt):
            sql = str(stmt).lower()
            if "processingjob" in sql or "processing_job" in sql:
                return mock_job_result
            return mock_doc_result

        mock_session.execute.side_effect = mock_execute_side_effect

        with patch("backend.modules.chunking.workers.tasks.process_document_chunking_task.apply_async") as mock_dispatch:
            handled = await sweep_stale_pipeline_documents(
                stale_threshold_minutes=15,
                session=mock_session,
                redis_client=mock_redis,
            )

            assert handled == 0
            assert job.retry_count == 1
            assert not mock_dispatch.called

    @pytest.mark.asyncio
    async def test_sweep_concurrent_lock_contention_returns_zero(self):
        """When another watchdog instance holds the distributed sweep lock, sweep aborts immediately."""
        mock_session = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.set.return_value = False  # Lock held by peer worker

        handled = await sweep_stale_pipeline_documents(
            stale_threshold_minutes=15,
            session=mock_session,
            redis_client=mock_redis,
        )

        assert handled == 0
        assert not mock_session.execute.called

    @pytest.mark.asyncio
    async def test_sweep_redispatches_embedding_stage_with_embedding_job(self):
        """Stuck EMBEDDING stage with active EmbeddingJob re-dispatches process_embedding_batch_task to embeddings queue."""
        mock_session = AsyncMock()
        version_id = uuid.uuid4()
        emb_job_id = uuid.uuid4()
        stale_time = datetime.now(UTC) - timedelta(minutes=20)
        doc = Document(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            status=DocumentStatus.EMBEDDING,
            updated_at=stale_time,
            is_deleted=False,
            latest_version_id=version_id,
        )
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc.id,
            status="PROCESSING",
            current_step="embedding",
            retry_count=1,
            max_retries=3,
            is_deleted=False,
            created_at=stale_time,
        )
        emb_job = EmbeddingJob(
            id=emb_job_id,
            tenant_id="tenant-1",
            document_id=doc.id,
            document_version_id=version_id,
            status="PROCESSING",
            provider="openai",
            model_name="text-embedding-3-small",
            total_chunks=10,
        )

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        mock_redis.exists.return_value = False

        mock_doc_result = MagicMock()
        mock_doc_result.scalars.return_value.all.return_value = [doc]
        mock_job_result = MagicMock()
        mock_job_result.scalar_one_or_none.return_value = job
        mock_emb_result = MagicMock()
        mock_emb_result.scalar_one_or_none.return_value = emb_job

        def mock_execute_side_effect(stmt):
            sql = str(stmt).lower()
            if "embeddingjob" in sql or "embedding_job" in sql:
                return mock_emb_result
            if "processingjob" in sql or "processing_job" in sql:
                return mock_job_result
            return mock_doc_result

        mock_session.execute.side_effect = mock_execute_side_effect

        with patch("backend.modules.embedding.workers.tasks.process_embedding_batch_task.apply_async") as mock_dispatch:
            handled = await sweep_stale_pipeline_documents(
                stale_threshold_minutes=15,
                session=mock_session,
                redis_client=mock_redis,
            )

            assert handled == 1
            assert job.retry_count == 2
            assert mock_dispatch.called
            call_kwargs = mock_dispatch.call_args[1]
            assert call_kwargs["queue"] == "embeddings"
            assert call_kwargs["args"] == [str(emb_job_id), "tenant-1", 100, False]

    @pytest.mark.asyncio
    async def test_sweep_redispatches_embedding_fallback_to_chunking_when_no_job(self):
        """Stuck EMBEDDING stage without an existing EmbeddingJob safely falls back to chunking."""
        mock_session = AsyncMock()
        version_id = uuid.uuid4()
        stale_time = datetime.now(UTC) - timedelta(minutes=20)
        doc = Document(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            status=DocumentStatus.EMBEDDING,
            updated_at=stale_time,
            is_deleted=False,
            latest_version_id=version_id,
        )
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc.id,
            status="PROCESSING",
            current_step="embedding",
            retry_count=1,
            max_retries=3,
            is_deleted=False,
            created_at=stale_time,
        )

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        mock_redis.exists.return_value = False

        mock_doc_result = MagicMock()
        mock_doc_result.scalars.return_value.all.return_value = [doc]
        mock_job_result = MagicMock()
        mock_job_result.scalar_one_or_none.return_value = job
        mock_emb_result = MagicMock()
        mock_emb_result.scalar_one_or_none.return_value = None  # No EmbeddingJob found

        def mock_execute_side_effect(stmt):
            sql = str(stmt).lower()
            if "embeddingjob" in sql or "embedding_job" in sql:
                return mock_emb_result
            if "processingjob" in sql or "processing_job" in sql:
                return mock_job_result
            return mock_doc_result

        mock_session.execute.side_effect = mock_execute_side_effect

        with patch("backend.modules.chunking.workers.tasks.process_document_chunking_task.apply_async") as mock_dispatch:
            handled = await sweep_stale_pipeline_documents(
                stale_threshold_minutes=15,
                session=mock_session,
                redis_client=mock_redis,
            )

            assert handled == 1
            assert job.retry_count == 2
            assert mock_dispatch.called
            call_kwargs = mock_dispatch.call_args[1]
            assert call_kwargs["queue"] == "ingestion"
            assert call_kwargs["args"] == ["tenant-1", str(doc.id), str(version_id)]

    @pytest.mark.asyncio
    async def test_sweep_redispatch_failure_reverts_retry_count_and_continues(self):
        """When Celery dispatch fails, retry count is reverted and sweep continues safely."""
        mock_session = AsyncMock()
        version_id = uuid.uuid4()
        stale_time = datetime.now(UTC) - timedelta(minutes=20)
        doc = Document(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            status=DocumentStatus.CHUNKING,
            updated_at=stale_time,
            is_deleted=False,
            latest_version_id=version_id,
        )
        job = ProcessingJob(
            id=uuid.uuid4(),
            document_id=doc.id,
            status="PROCESSING",
            current_step="chunking",
            retry_count=1,
            max_retries=3,
            is_deleted=False,
            created_at=stale_time,
        )

        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        mock_redis.exists.return_value = False

        mock_doc_result = MagicMock()
        mock_doc_result.scalars.return_value.all.return_value = [doc]
        mock_job_result = MagicMock()
        mock_job_result.scalar_one_or_none.return_value = job

        def mock_execute_side_effect(stmt):
            sql = str(stmt).lower()
            if "processingjob" in sql or "processing_job" in sql:
                return mock_job_result
            return mock_doc_result

        mock_session.execute.side_effect = mock_execute_side_effect

        with patch(
            "backend.modules.chunking.workers.tasks.process_document_chunking_task.apply_async",
            side_effect=Exception("RabbitMQ connection refused"),
        ):
            handled = await sweep_stale_pipeline_documents(
                stale_threshold_minutes=15,
                session=mock_session,
                redis_client=mock_redis,
            )

            assert handled == 0
            assert job.retry_count == 1  # Reverted back
            assert job.status == "PROCESSING"  # Reverted back

    def test_chunking_worker_retries_on_lock_acquisition_failure(self):
        """Chunking Celery worker catches LockAcquisitionError and schedules task retry."""
        with patch.object(process_document_chunking_task, "retry", side_effect=Exception("CeleryRetryTriggered")) as mock_retry:
            with patch("backend.modules.chunking.workers.tasks._async_process_chunking", side_effect=LockAcquisitionError("Lock acquisition failed")):
                with pytest.raises(Exception, match="CeleryRetryTriggered"):
                    process_document_chunking_task.run(
                        tenant_id="tenant-1",
                        document_id=str(uuid.uuid4()),
                        version_id=str(uuid.uuid4()),
                    )

                assert mock_retry.called
                call_kwargs = mock_retry.call_args[1]
                assert call_kwargs["countdown"] == 10


# ==============================================================================
# PERF-002: AsyncEngine health check reuse
# ==============================================================================
class TestPerf002DbHealthEngineReuse:
    """PERF-002: Health check reuses singleton raw AsyncEngine instead of creating per probe."""

    @pytest.mark.asyncio
    async def test_get_raw_engine_returns_singleton_per_loop(self):
        loop = asyncio.get_running_loop()
        engine1 = get_raw_engine()
        engine2 = get_raw_engine()
        assert engine1 is engine2
        assert db_state.raw_engines[loop] is engine1

    @pytest.mark.asyncio
    async def test_check_db_health_reuses_raw_engine_with_pgbouncer(self):
        mock_settings = MagicMock()
        mock_settings.database.url = "postgresql+asyncpg://user:pass@localhost:5432/test"
        mock_settings.database.use_pgbouncer = True

        mock_conn = AsyncMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__aenter__.return_value = mock_conn

        with patch("backend.database.engine.get_settings", return_value=mock_settings), \
             patch("backend.database.engine.get_engine", return_value=mock_engine), \
             patch("backend.database.engine.get_raw_engine", return_value=mock_engine) as mock_get_raw, \
             patch("backend.database.engine.create_async_engine") as mock_create_engine:
            res1 = await check_db_health()
            res2 = await check_db_health()

            assert res1 is True
            assert res2 is True
            assert mock_get_raw.call_count == 2
            # Crucial: create_async_engine must NOT be called directly inside check_db_health
            assert mock_create_engine.call_count == 0


# ==============================================================================
# PERF-003: Celery task time limits and prefetch limits
# ==============================================================================
class TestPerf003CeleryTimeoutsAndPrefetch:
    """PERF-003: Global task timeouts and worker_prefetch_multiplier = 1."""

    def test_celery_prefetch_multiplier_is_one(self):
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_celery_task_time_limits_configured(self):
        assert celery_app.conf.task_soft_time_limit == 300
        assert celery_app.conf.task_time_limit == 360


# ==============================================================================
# PERF-004: Redis connection pool disconnect
# ==============================================================================
class TestPerf004RedisPoolDisconnect:
    """PERF-004: Explicit pool disconnect on loop teardown."""

    @pytest.mark.asyncio
    async def test_disconnect_redis_pool_current_loop(self):
        loop = asyncio.get_running_loop()
        mock_pool = AsyncMock()
        mock_client = AsyncMock()
        cache_state.pools[loop] = mock_pool
        cache_state.clients[loop] = mock_client

        await disconnect_redis_pool(loop)

        assert mock_pool.disconnect.called
        assert mock_client.close.called
        assert loop not in cache_state.pools
        assert loop not in cache_state.clients


# ==============================================================================
# OBS-001: Root /ready route responds HTTP 200
# ==============================================================================
class TestObs001RootReadyRoute:
    """OBS-001: Kubernetes readiness probe /ready responds HTTP 200."""

    @pytest.mark.asyncio
    async def test_root_ready_route_registered_and_responds_200(self):
        app = create_app()

        with patch("backend.api.v1.routes.health._check_dependencies") as mock_deps:
            from backend.api.v1.schemas.common import DependencyHealth
            mock_deps.return_value = {
                "postgresql": DependencyHealth(name="postgresql", status="healthy", latency_ms=1.2),
                "redis": DependencyHealth(name="redis", status="healthy", latency_ms=0.5),
                "qdrant": DependencyHealth(name="qdrant", status="healthy", latency_ms=2.1),
                "object_storage": DependencyHealth(name="object_storage", status="healthy", latency_ms=1.5),
            }

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get("/ready")
                assert res.status_code == 200
                data = res.json()
                assert data["status"] == "ready"
                assert "dependencies" in data
                assert data["dependencies"]["postgresql"] == "healthy"
