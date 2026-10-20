from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.modules.vector.services.vector_service import VectorStorageService

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_session():
    return AsyncMock()

@pytest.fixture
def service(mock_session):
    with patch("backend.modules.vector.services.vector_service.VectorProviderFactory") as factory_cls, \
         patch("backend.modules.vector.services.vector_service.VectorMetadataRepository") as repo_cls, \
         patch("backend.modules.vector.services.vector_service.get_dispatcher") as get_dispatcher_mock:

        mock_provider = AsyncMock()
        factory_cls.get_provider.return_value = mock_provider
        repo_cls.return_value = AsyncMock()
        mock_execute = MagicMock()
        mock_scalars = MagicMock()
        mock_rec = MagicMock()
        mock_rec.id = uuid.uuid4()
        mock_rec.collection_name = "col_tenant-1_default"
        # Make the mock act as a string when iterated or used as col name
        mock_rec.__str__.return_value = "col_tenant-1_default"
        mock_scalars.all.return_value = [mock_rec]
        mock_execute.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_execute

        yield VectorStorageService(session=mock_session)

async def test_remove_archived_document_vectors(service):
    doc_id = str(uuid.uuid4())
    tenant_id = "tenant-1"

    # Mock finding collections
    service.provider.list_collections = AsyncMock(return_value=[f"col_{tenant_id}_1", "col_other_1"])
    service.provider.delete_points_by_filter.return_value = 5

    deleted_count = await service.remove_archived_document_vectors(doc_id, tenant_id)

    assert deleted_count == 5
    service.provider.delete_points_by_filter.assert_called_once()

async def test_cleanup_old_versions_vectors(service, mock_session):
    doc_id = uuid.uuid4()
    current_ver = uuid.uuid4()
    tenant_id = "tenant-1"
    col_name = "test_collection"

    # Mock old versions returned by repo
    service.repo.get_old_versions_for_document = AsyncMock(return_value=[uuid.uuid4(), uuid.uuid4()])
    service.provider.delete_points_by_filter.return_value = 5
    service.repo.mark_vectors_deleted = AsyncMock()

    # Setup two mock metadata records
    mock_rec1 = MagicMock()
    mock_rec1.id = uuid.uuid4()
    mock_rec1.collection_name = "col_1"
    mock_rec1.document_version_id = uuid.uuid4()

    mock_rec2 = MagicMock()
    mock_rec2.id = uuid.uuid4()
    mock_rec2.collection_name = "col_2"
    mock_rec2.document_version_id = uuid.uuid4()

    mock_execute = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_rec1, mock_rec2]
    mock_execute.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_execute

    await service.cleanup_old_versions_vectors(doc_id, current_ver, tenant_id, col_name)

    assert service.provider.delete_points_by_filter.call_count == 2
    assert service.repo.update_sync_status.call_count == 2


async def test_cleanup_failure_transitions_to_cleanup_pending(service, mock_session):
    doc_id = uuid.uuid4()
    current_ver = uuid.uuid4()
    tenant_id = "tenant-fail"

    mock_rec = MagicMock()
    mock_rec.id = uuid.uuid4()
    mock_rec.collection_name = "col_retry"
    mock_rec.document_version_id = uuid.uuid4()

    mock_execute = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_rec]
    mock_execute.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_execute

    # Simulate Qdrant delete failing on all attempts
    service.provider.delete_points_by_filter.side_effect = RuntimeError("Qdrant 503 Service Unavailable")

    await service.cleanup_old_versions_vectors(doc_id, current_ver, tenant_id)

    # Must retry 3 times
    assert service.provider.delete_points_by_filter.call_count == 3
    # Must record CLEANUP_PENDING and keep is_deleted False
    service.repo.update_sync_status.assert_called_with(
        mock_rec.id, status="CLEANUP_PENDING", error_message="Qdrant purge failed: Qdrant 503 Service Unavailable"
    )
    assert mock_rec.is_deleted is False


async def test_reconcile_superseded_vectors_success(service, mock_session):
    tenant_id = "tenant-reconcile"

    mock_rec = MagicMock()
    mock_rec.id = uuid.uuid4()
    mock_rec.tenant_id = tenant_id
    mock_rec.collection_name = "col_reconcile"
    mock_rec.document_version_id = uuid.uuid4()

    mock_execute = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_rec]
    mock_execute.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_execute

    service.provider.delete_points_by_filter.return_value = 10
    service.provider.delete_points_by_filter.side_effect = None

    with patch("backend.modules.vector.services.vector_service.acquire_lock") as mock_lock:
        mock_lock.return_value.__aenter__.return_value = "token"
        reconciled = await service.reconcile_superseded_vectors(tenant_id=tenant_id)
        mock_lock.assert_called_once_with("cleanup:reconciliation:tenant-reconcile", timeout=120, acquire_timeout=2)

    assert reconciled == 10
    service.provider.delete_points_by_filter.assert_called_once()
    service.repo.update_sync_status.assert_called_with(
        mock_rec.id, status="FAILED", error_message="Superseded by newer version"
    )
    assert mock_rec.is_deleted is True


async def test_data001_reserved_payload_field_stripping(service, mock_session):
    """DATA-001: User metadata cannot overwrite system reserved fields in Qdrant point payloads."""
    from backend.document.models.document import Document
    from backend.modules.chunking.models.chunk import DocumentChunk
    from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
    from backend.modules.vector.schemas.payload import VectorPointDTO

    doc_id = uuid.uuid4()
    version_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    legitimate_tenant_id = "tenant-legitimate-123"

    # Mock ChunkEmbedding
    mock_emb = MagicMock(spec=ChunkEmbedding)
    mock_emb.chunk_id = chunk_id
    mock_emb.document_version_id = version_id
    mock_emb.tenant_id = legitimate_tenant_id
    mock_emb.content_hash = "legitimate_content_hash"
    mock_emb.dimension = 384
    mock_emb.provider = "openai"
    mock_emb.model_name = "text-embedding-3-small"
    mock_emb.embedding_vector = [0.05] * 384

    # Mock DocumentChunk
    mock_chunk = MagicMock(spec=DocumentChunk)
    mock_chunk.id = chunk_id
    mock_chunk.document_version_id = version_id
    mock_chunk.tenant_id = legitimate_tenant_id
    mock_chunk.content = "Legitimate document content"
    mock_chunk.strategy_used = "hierarchical"
    mock_chunk.chunk_index = 0
    mock_chunk.token_count = 5
    mock_chunk.character_count = 27
    mock_chunk.section_path = "Introduction"
    mock_chunk.page_numbers = [1]

    # Mock Document with adversarial user_metadata attempting payload poisoning
    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.tenant_id = legitimate_tenant_id
    mock_doc.filename = "report.pdf"
    mock_doc.source_type = "file_upload"
    mock_doc.source_url = None
    mock_doc.canonical_url = None
    mock_doc.final_url = None
    mock_doc.user_metadata = {
        "tenant_id": "malicious-attacker-tenant",
        "document_id": "malicious-doc-override",
        "content_hash": "poisoned-hash",
        "content": "spoofed-content",
        "strategy_used": "fake_strategy",
        "chunk_index": 9999,
        "token_count": 0,
        "character_count": 0,
        "section_path": "hacked",
        "page_numbers": [999],
        "provider": "malicious-provider",
        "model_name": "malicious-model",
        "source_type": "spoofed_source",
        "source_url": "http://evil.com",
        "title": "spoofed_title",
        # Legitimate custom metadata tag:
        "custom_department": "finance",
        "project_tag": "q4_audit",
    }

    async def mock_execute(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "chunk_embeddings" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_emb]
        elif "document_chunks" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_chunk]
        elif "documents" in stmt_str:
            mock_result.scalar_one_or_none.return_value = mock_doc
        else:
            mock_result.scalars.return_value.all.return_value = []
            mock_result.scalar_one_or_none.return_value = None
        return mock_result

    mock_session.execute = mock_execute

    service.repo.get_or_create_metadata = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))
    service.repo.update_sync_status = AsyncMock()
    service.cleanup_old_versions_vectors = AsyncMock(return_value=0)
    service.dispatcher = AsyncMock()

    with patch("backend.document.repositories.document_repository.DocumentRepository") as mock_doc_repo_cls:
        mock_doc_repo_inst = MagicMock()
        mock_doc_repo_inst.get_by_id = AsyncMock(return_value=mock_doc)
        mock_doc_repo_cls.return_value = mock_doc_repo_inst

        service.provider.upsert_points = AsyncMock(return_value=1)

        count = await service.sync_document_vectors(doc_id, version_id, legitimate_tenant_id)

    assert count == 1
    service.provider.upsert_points.assert_called_once()
    upserted_points: list[VectorPointDTO] = service.provider.upsert_points.call_args[0][1]
    assert len(upserted_points) == 1

    payload = upserted_points[0].payload

    # Prove system keys CANNOT be poisoned by user_metadata
    assert payload["tenant_id"] == legitimate_tenant_id
    assert payload["document_id"] == str(doc_id)
    assert payload["document_version_id"] == str(version_id)
    assert payload["content_hash"] == "legitimate_content_hash"
    assert payload["content"] == "Legitimate document content"
    assert payload["strategy_used"] == "hierarchical"
    assert payload["chunk_index"] == 0
    assert payload["token_count"] == 5
    assert payload["character_count"] == 27
    assert payload["section_path"] == "Introduction"
    assert payload["page_numbers"] == [1]
    assert payload["provider"] == "openai"
    assert payload["model_name"] == "text-embedding-3-small"
    assert payload["source_type"] == "file_upload"
    assert payload["title"] == "report.pdf"

    # Prove non-reserved metadata tags are safely preserved
    assert payload["custom_department"] == "finance"
    assert payload["project_tag"] == "q4_audit"
