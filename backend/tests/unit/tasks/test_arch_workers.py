"""Unit tests for Phase 2 (WP-ARCH Critical Subset): ARCH-001, ARCH-002, ARCH-006, ING-007."""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
import os

from backend.document.services.processing_job_service import ProcessingJobService
from backend.tasks.celery_app import celery_app


class TestArch001MetadataSyncWorker:
    """ARCH-001: metadata_sync.py worker session parameter and queue routing."""

    def test_metadata_sync_queue_and_include_registration(self):
        """Verify metadata_sync module is included and routes to 'indexing' queue."""
        assert "backend.document.workers.metadata_sync" in celery_app.conf.include

        from backend.document.workers.metadata_sync import (
            sync_document_metadata_to_vectors_job,
        )

        assert sync_document_metadata_to_vectors_job.queue == "indexing"

        # Check router table configuration
        route = celery_app.amqp.router.route(
            {}, "document.sync_document_metadata_to_vectors_job"
        )
        assert route is not None
        queue_obj = route.get("queue")
        queue_name = queue_obj.name if hasattr(queue_obj, "name") else str(queue_obj)
        assert queue_name == "indexing"

    @pytest.mark.asyncio
    async def test_metadata_sync_instantiates_vector_service_with_session(self):
        """Verify _async_sync_metadata supplies session to VectorStorageService without TypeError."""
        from backend.document.workers.metadata_sync import _async_sync_metadata

        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.tenant_id = "test-tenant"

        mock_session = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        mock_session_factory.return_value.__aexit__.return_value = None

        with (
            patch(
                "backend.document.workers.metadata_sync.get_session_factory",
                return_value=mock_session_factory,
            ),
            patch(
                "backend.document.workers.metadata_sync.DocumentRepository"
            ) as mock_doc_repo_cls,
            patch(
                "backend.document.workers.metadata_sync.VectorStorageService"
            ) as mock_vec_service_cls,
        ):
            mock_doc_repo = mock_doc_repo_cls.return_value
            mock_doc_repo.get_by_id_with_versions = AsyncMock(return_value=mock_doc)

            mock_vec_service = mock_vec_service_cls.return_value
            mock_vec_service.sync_metadata = AsyncMock()

            # Call execution
            await _async_sync_metadata(mock_doc.id, mock_doc.tenant_id)

            # Assertions
            mock_doc_repo.get_by_id_with_versions.assert_awaited_once_with(
                mock_doc.id, mock_doc.tenant_id, mock_session
            )
            # Verify session was passed to VectorStorageService
            mock_vec_service_cls.assert_called_once_with(session=mock_session)
            mock_vec_service.sync_metadata.assert_awaited_once_with(mock_doc)


class TestArch002VectorSyncEventDeduplication:
    """ARCH-002: Verify duplicate VECTORS_INDEXED event is eliminated in worker task."""

    @pytest.mark.asyncio
    async def test_sync_vectors_task_does_not_publish_duplicate_event(self):
        """Verify tasks.py relies solely on VectorStorageService for event publication."""
        from backend.modules.vector.workers.tasks import _async_sync_vectors_task

        doc_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        tenant_id = "tenant-arch-test"

        mock_session = AsyncMock()
        mock_session_factory = MagicMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        mock_session_factory.return_value.__aexit__.return_value = None

        mock_acquire_lock = MagicMock()
        mock_acquire_lock.return_value.__aenter__.return_value = None
        mock_acquire_lock.return_value.__aexit__.return_value = None

        with (
            patch(
                "backend.modules.vector.workers.tasks.get_session_factory",
                return_value=mock_session_factory,
            ),
            patch(
                "backend.cache.locks.acquire_lock",
                mock_acquire_lock,
            ),
            patch(
                "backend.modules.vector.workers.tasks.VectorStorageService"
            ) as mock_vec_service_cls,
            patch("backend.core.events.dispatcher.get_dispatcher") as mock_get_dispatcher,
        ):
            mock_vec_service = mock_vec_service_cls.return_value
            mock_vec_service.sync_document_vectors = AsyncMock(return_value=42)

            res = await _async_sync_vectors_task(
                task_instance=MagicMock(),
                tenant_id=tenant_id,
                document_id=doc_id,
                document_version_id=version_id,
                collection_name=None,
            )

            assert res["status"] == "COMPLETED"
            assert res["upserted_points"] == 42
            # The worker task itself should NOT call get_dispatcher or publish an event
            mock_get_dispatcher.assert_not_called()


class TestArch006DeadCodeRemoval:
    """ARCH-006: ProcessingJobService.mark_job_completed removal."""

    def test_mark_job_completed_does_not_exist(self):
        """Verify mark_job_completed method has been permanently removed."""
        assert not hasattr(ProcessingJobService, "mark_job_completed")


class TestIng007ExtractionWorkerRemoval:
    """ING-007: Legacy extraction_worker removal."""

    def test_extraction_worker_file_removed(self):
        """Verify extraction_worker.py file is deleted from repository."""
        legacy_path = os.path.join(
            "backend", "document", "workers", "extraction_worker.py"
        )
        assert not os.path.exists(legacy_path)

    def test_extraction_worker_not_in_celery_include(self):
        """Verify extraction_worker is removed from Celery include list."""
        assert "backend.document.workers.extraction_worker" not in celery_app.conf.include
