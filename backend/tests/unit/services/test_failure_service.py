"""Unit tests for PipelineFailureSynchronizer (Phase D2.5 / P0-3 LFC-001)."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.document.models.document import Document, DocumentVersion
from backend.document.models.event_log import DocumentEventLog
from backend.document.models.failed_job import FailedJobDiagnostics
from backend.document.models.job import ProcessingJob
from backend.document.models.status import DocumentStatus
from backend.document.services.failure_service import PipelineFailureSynchronizer
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.embedding_job import EmbeddingJob


@pytest.fixture
def mock_session():
    session = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_failure_synchronizer_active_v1_retained_on_v2_chunking_failure(mock_session):
    """Scenario 1: Active V1 is preserved when V2 fails during chunking."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()
    job2_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        status=DocumentStatus.READY,
        latest_version_id=v1_id,
        filename="doc.txt",
    )
    mock_job2 = ProcessingJob(
        id=job2_id,
        document_id=doc_id,
        version_id=v2_id,
        status="PROCESSING",
        current_step="chunking",
    )
    v1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        is_active_vector=True,
        is_deleted=False,
    )
    v2 = DocumentVersion(
        id=v2_id,
        document_id=doc_id,
        is_active_vector=False,
        is_deleted=False,
    )

    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        if model == ProcessingJob and entity_id == job2_id:
            return mock_job2
        return None

    mock_session.get.side_effect = mock_get

    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.all.return_value = [v1, v2]
    mock_session.execute.return_value = mock_exec_res

    test_exc = ValueError("Chunking syntax error on V2")

    await PipelineFailureSynchronizer.record_pipeline_failure(
        session=mock_session,
        document_id=doc_id,
        failing_stage="chunking",
        error_code="CHK_001",
        error_message="Chunking syntax error on V2",
        exception=test_exc,
        job_id=job2_id,
        tenant_id="test-tenant",
    )

    # Document must remain READY because V1 is active
    assert mock_doc.status == DocumentStatus.READY
    assert mock_job2.status == "FAILED"
    assert mock_job2.error_code == "CHK_001"
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_failure_synchronizer_active_v1_retained_on_v2_embedding_failure(mock_session):
    """Scenario 2: Active V1 is preserved when V2 fails during embedding."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()
    emb_job2_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        status=DocumentStatus.READY,
        latest_version_id=v1_id,
        filename="doc.txt",
    )
    mock_emb_job2 = EmbeddingJob(
        id=emb_job2_id,
        document_id=doc_id,
        document_version_id=v2_id,
        tenant_id="test-tenant",
        status="RUNNING",
    )
    v1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        is_active_vector=True,
        is_deleted=False,
    )
    v2 = DocumentVersion(
        id=v2_id,
        document_id=doc_id,
        is_active_vector=False,
        is_deleted=False,
    )

    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        if model == EmbeddingJob and entity_id == emb_job2_id:
            return mock_emb_job2
        return None

    mock_session.get.side_effect = mock_get

    mock_exec_res = MagicMock()
    mock_exec_res.scalar_one_or_none.return_value = None
    mock_exec_res.scalars.return_value.all.return_value = [v1, v2]
    mock_session.execute.return_value = mock_exec_res

    await PipelineFailureSynchronizer.record_pipeline_failure(
        session=mock_session,
        document_id=doc_id,
        failing_stage="embedding",
        error_code="EMB_004",
        error_message="Embedding provider quota exceeded",
        embedding_job_id=emb_job2_id,
        tenant_id="test-tenant",
    )

    assert mock_doc.status == DocumentStatus.READY
    assert mock_emb_job2.status == "FAILED"
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_failure_synchronizer_active_v1_retained_on_v2_vector_sync_failure(mock_session):
    """Scenario 3: Active V1 is preserved when V2 fails during vector sync."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()
    job2_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        status=DocumentStatus.READY,
        latest_version_id=v1_id,
        filename="doc.txt",
    )
    mock_job2 = ProcessingJob(
        id=job2_id,
        document_id=doc_id,
        version_id=v2_id,
        status="PROCESSING",
        current_step="vector_sync",
    )
    v1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        is_active_vector=True,
        is_deleted=False,
    )
    v2 = DocumentVersion(
        id=v2_id,
        document_id=doc_id,
        is_active_vector=False,
        is_deleted=False,
    )

    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        if model == ProcessingJob and entity_id == job2_id:
            return mock_job2
        return None

    mock_session.get.side_effect = mock_get

    mock_exec_res = MagicMock()
    mock_exec_res.scalar_one_or_none.return_value = None
    mock_exec_res.scalars.return_value.all.return_value = [v1, v2]
    mock_session.execute.return_value = mock_exec_res

    await PipelineFailureSynchronizer.record_pipeline_failure(
        session=mock_session,
        document_id=doc_id,
        failing_stage="vector_sync",
        error_code="VEC_003",
        error_message="Qdrant cluster timeout",
        job_id=job2_id,
        tenant_id="test-tenant",
    )

    assert mock_doc.status == DocumentStatus.READY
    assert mock_job2.status == "FAILED"
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_failure_synchronizer_initial_v1_failure_sets_failed(mock_session):
    """Scenario 4: Initial upload failure (no active version) transitions document to FAILED."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    job1_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        status=DocumentStatus.CHUNKING,
        filename="doc.txt",
    )
    mock_job1 = ProcessingJob(
        id=job1_id,
        document_id=doc_id,
        version_id=v1_id,
        status="PROCESSING",
        current_step="chunking",
    )
    v1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        is_active_vector=False,  # Initial version is not active yet
        is_deleted=False,
    )

    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        if model == ProcessingJob and entity_id == job1_id:
            return mock_job1
        return None

    mock_session.get.side_effect = mock_get

    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.all.return_value = [v1]
    mock_session.execute.return_value = mock_exec_res

    await PipelineFailureSynchronizer.record_pipeline_failure(
        session=mock_session,
        document_id=doc_id,
        failing_stage="chunking",
        error_code="CHK_001",
        error_message="Fatal syntax error",
        job_id=job1_id,
        tenant_id="test-tenant",
    )

    assert mock_doc.status == DocumentStatus.FAILED
    assert mock_job1.status == "FAILED"
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_failure_synchronizer_missing_job_metadata_fallback(mock_session):
    """Scenario 5: Missing job and version metadata falls back safely to DocumentStatus.FAILED."""
    doc_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        status=DocumentStatus.PENDING,
        filename="doc.txt",
    )

    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        return None

    mock_session.get.side_effect = mock_get

    mock_exec_res = MagicMock()
    mock_exec_res.scalar_one_or_none.return_value = None
    mock_exec_res.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_exec_res

    await PipelineFailureSynchronizer.record_pipeline_failure(
        session=mock_session,
        document_id=doc_id,
        failing_stage="extraction",
        error_code="EXT_001",
        error_message="No parser available",
        tenant_id="test-tenant",
    )

    assert mock_doc.status == DocumentStatus.FAILED
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_failure_synchronizer_ignores_soft_deleted_active_version(mock_session):
    """Scenario 6: Soft-deleted version (is_deleted=True) is not considered active."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()
    job2_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        status=DocumentStatus.CHUNKING,
        filename="doc.txt",
    )
    mock_job2 = ProcessingJob(
        id=job2_id,
        document_id=doc_id,
        version_id=v2_id,
        status="PROCESSING",
    )

    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        if model == ProcessingJob and entity_id == job2_id:
            return mock_job2
        return None

    mock_session.get.side_effect = mock_get

    # Database query filtered by is_deleted=False returns no non-deleted active versions
    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_exec_res

    await PipelineFailureSynchronizer.record_pipeline_failure(
        session=mock_session,
        document_id=doc_id,
        failing_stage="chunking",
        error_code="CHK_002",
        error_message="Corrupted chunk payload",
        job_id=job2_id,
        tenant_id="test-tenant",
    )

    assert mock_doc.status == DocumentStatus.FAILED


@pytest.mark.asyncio
async def test_failure_synchronizer_tenant_scoping(mock_session):
    """Scenario 7: Cross-tenant failure invocation is rejected and does not mutate document."""
    doc_id = uuid.uuid4()
    v2_id = uuid.uuid4()
    job2_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="tenant-alpha",
        status=DocumentStatus.EMBEDDING,
        filename="doc.txt",
    )
    mock_job2 = ProcessingJob(
        id=job2_id,
        document_id=doc_id,
        version_id=v2_id,
        status="RUNNING",
    )

    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        if model == ProcessingJob and entity_id == job2_id:
            return mock_job2
        return None

    mock_session.get.side_effect = mock_get

    # Attempt cross-tenant failure call targeting tenant-alpha doc with tenant-beta credentials
    await PipelineFailureSynchronizer.record_pipeline_failure(
        session=mock_session,
        document_id=doc_id,
        failing_stage="embedding",
        error_code="EMB_009",
        error_message="Cross-tenant unauthorized error",
        job_id=job2_id,
        tenant_id="tenant-beta",  # Mismatched tenant
    )

    # Document must NOT be mutated by cross-tenant caller
    assert mock_doc.status == DocumentStatus.EMBEDDING
    assert mock_job2.status == "RUNNING"
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_failure_synchronizer_forensic_diagnostics_and_event_log(mock_session):
    """Scenario 8: FailedJobDiagnostics and DocumentEventLog entries are persisted."""
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        status=DocumentStatus.PENDING,
        filename="doc.txt",
    )
    mock_job = ProcessingJob(
        id=job_id,
        document_id=doc_id,
        status="PROCESSING",
    )

    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        if model == ProcessingJob and entity_id == job_id:
            return mock_job
        return None

    mock_session.get.side_effect = mock_get

    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_exec_res

    test_exc = RuntimeError("Fatal OOM crash during chunking")

    await PipelineFailureSynchronizer.record_pipeline_failure(
        session=mock_session,
        document_id=doc_id,
        failing_stage="chunking",
        error_code="MEM_001",
        error_message="Out of memory",
        exception=test_exc,
        job_id=job_id,
        tenant_id="test-tenant",
        worker_context={"worker_id": "celery@node1", "pid": 1234},
    )

    # Verify session.add was called for FailedJobDiagnostics and DocumentEventLog
    added_objects = [call[0][0] for call in mock_session.add.call_args_list]
    diag_objects = [o for o in added_objects if isinstance(o, FailedJobDiagnostics)]
    event_objects = [o for o in added_objects if isinstance(o, DocumentEventLog)]

    assert len(diag_objects) == 1, "FailedJobDiagnostics must be added"
    assert diag_objects[0].job_id == job_id
    assert diag_objects[0].failing_step == "chunking"
    assert diag_objects[0].exception_class == "RuntimeError"

    assert len(event_objects) == 1, "DocumentEventLog must be added"
    assert event_objects[0].document_id == doc_id
    assert event_objects[0].event_type == "DOCUMENT_FAILED"

    mock_session.commit.assert_called()
