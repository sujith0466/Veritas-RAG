"""Unit tests for PipelineFailureSynchronizer (Phase D2.5)."""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.document.models.document import Document
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
async def test_failure_synchronizer_document_and_job(mock_session):
    """Test failure synchronizer transitions document and processing job to FAILED."""
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        status=DocumentStatus.CHUNKING,
        filename="doc.txt",
    )
    mock_job = ProcessingJob(
        id=job_id,
        document_id=doc_id,
        status="PROCESSING",
        current_step="chunking",
    )

    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        if model == ProcessingJob and entity_id == job_id:
            return mock_job
        return None

    mock_session.get.side_effect = mock_get

    test_exc = ValueError("Fatal chunking syntax error")

    await PipelineFailureSynchronizer.record_pipeline_failure(
        session=mock_session,
        document_id=doc_id,
        failing_stage="chunking",
        error_code="CHK_001",
        error_message="Syntax error in chunking",
        exception=test_exc,
        job_id=job_id,
        tenant_id="test-tenant",
    )

    assert mock_doc.status == DocumentStatus.FAILED
    assert mock_job.status == "FAILED"
    assert mock_job.error_code == "CHK_001"
    assert mock_job.error_message == "Syntax error in chunking"
    assert mock_job.completed_at is not None

    mock_session.add.assert_called()
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_failure_synchronizer_embedding_stage(mock_session):
    """Test failure synchronizer transitions EmbeddingJob when embedding stage fails."""
    doc_id = uuid.uuid4()
    emb_job_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        status=DocumentStatus.EMBEDDING,
        filename="doc.txt",
    )
    mock_emb_job = EmbeddingJob(
        id=emb_job_id,
        document_id=doc_id,
        tenant_id="test-tenant",
        status="RUNNING",
    )

    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        if model == EmbeddingJob and entity_id == emb_job_id:
            return mock_emb_job
        return None

    mock_session.get.side_effect = mock_get

    # Mock execute for find_processing_job
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_execute_result

    await PipelineFailureSynchronizer.record_pipeline_failure(
        session=mock_session,
        document_id=doc_id,
        failing_stage="embedding",
        error_code="EMB_004",
        error_message="Embedding model quota exhausted",
        embedding_job_id=emb_job_id,
        tenant_id="test-tenant",
    )

    assert mock_doc.status == DocumentStatus.FAILED
    assert mock_emb_job.status == "FAILED"
    assert mock_emb_job.error_message == "Embedding model quota exhausted"
    assert mock_emb_job.completed_at is not None
    mock_session.commit.assert_called()


@pytest.mark.asyncio
async def test_failure_synchronizer_vector_sync_stage(mock_session):
    """Test failure synchronizer sets FAILED on vector sync failure."""
    doc_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="test-tenant",
        status=DocumentStatus.VECTOR_SYNC,
        filename="doc.txt",
    )

    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        return None

    mock_session.get.side_effect = mock_get

    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_execute_result

    await PipelineFailureSynchronizer.record_pipeline_failure(
        session=mock_session,
        document_id=doc_id,
        failing_stage="vector_sync",
        error_code="VEC_003",
        error_message="Qdrant cluster unavailable",
        tenant_id="test-tenant",
    )

    assert mock_doc.status == DocumentStatus.FAILED
    mock_session.commit.assert_called()
