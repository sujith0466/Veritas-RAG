"""Unit tests for D4.8 Qdrant Website Provenance & Retrieval Provenance."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.document.models.document import Document
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.retrieval.schemas.retrieval_dto import (
    CandidatePointDTO,
    RankedEvidenceDTO,
)
from backend.modules.retrieval.services.fusion import FusionEngine
from backend.modules.vector.schemas.payload import VectorPointDTO
from backend.modules.vector.services.vector_service import VectorStorageService


@pytest.mark.asyncio
async def test_d4_8_qdrant_payload_website_provenance():
    """D4.8-TEST-01: Website document chunks indexed into Qdrant contain full website provenance."""
    session = AsyncMock()
    provider = AsyncMock()
    dispatcher = AsyncMock()

    doc_id = uuid.uuid4()
    version_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    tenant_id = "tenant_test_123"

    # Mock ChunkEmbedding
    mock_emb = MagicMock(spec=ChunkEmbedding)
    mock_emb.chunk_id = chunk_id
    mock_emb.document_version_id = version_id
    mock_emb.tenant_id = tenant_id
    mock_emb.content_hash = "abc123hash"
    mock_emb.dimension = 384
    mock_emb.provider = "sentence-transformers"
    mock_emb.model_name = "all-MiniLM-L6-v2"
    mock_emb.embedding_vector = [0.1] * 384

    # Mock DocumentChunk
    mock_chunk = MagicMock(spec=DocumentChunk)
    mock_chunk.id = chunk_id
    mock_chunk.document_version_id = version_id
    mock_chunk.tenant_id = tenant_id
    mock_chunk.content = "Extracted web content for testing."
    mock_chunk.strategy_used = "hierarchical"
    mock_chunk.chunk_index = 0
    mock_chunk.token_count = 10
    mock_chunk.character_count = 34
    mock_chunk.section_path = "Main > Article"
    mock_chunk.page_numbers = None

    # Mock Document
    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.tenant_id = tenant_id
    mock_doc.filename = "Veritas Docs - Architecture"
    mock_doc.source_type = "website"
    mock_doc.source_url = "https://example.com/docs"
    mock_doc.canonical_url = "https://example.com/docs/canonical"
    mock_doc.final_url = "https://example.com/docs/final"
    mock_doc.user_metadata = {"custom_tag": "arch_doc"}

    # Mock queries
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

    session.execute = mock_execute

    service = VectorStorageService(session=session, provider=provider, dispatcher=dispatcher)
    # Mock repo
    service.repo.get_or_create_metadata = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))
    service.repo.update_sync_status = AsyncMock()
    service.cleanup_old_versions_vectors = AsyncMock(return_value=0)

    # Mock DocumentRepository.get_by_id
    with pytest.MonkeyPatch.context() as mp:
        mock_doc_repo_class = MagicMock()
        mock_doc_repo_inst = MagicMock()
        mock_doc_repo_inst.get_by_id = AsyncMock(return_value=mock_doc)
        mock_doc_repo_class.return_value = mock_doc_repo_inst
        mp.setattr("backend.document.repositories.document_repository.DocumentRepository", mock_doc_repo_class)

        provider.upsert_points = AsyncMock(return_value=1)

        count = await service.sync_document_vectors(doc_id, version_id, tenant_id)

    assert count == 1
    # Verify create_payload_indexes included source_type
    provider.create_payload_indexes.assert_called_once()
    indexed_fields = provider.create_payload_indexes.call_args[1]["indexed_fields"]
    assert "source_type" in indexed_fields
    assert "tenant_id" in indexed_fields
    assert "document_id" in indexed_fields
    assert "document_version_id" in indexed_fields

    # Verify upserted points
    provider.upsert_points.assert_called_once()
    upserted_points: list[VectorPointDTO] = provider.upsert_points.call_args[0][1]
    assert len(upserted_points) == 1

    pt = upserted_points[0]
    # Point ID MUST strictly be DocumentChunk.id
    assert pt.point_id == str(chunk_id)
    payload = pt.payload

    # Provenance assertions
    assert payload["tenant_id"] == tenant_id
    assert payload["document_id"] == str(doc_id)
    assert payload["document_version_id"] == str(version_id)
    assert payload["content_hash"] == "abc123hash"
    assert payload["source_type"] == "website"
    assert payload["source_url"] == "https://example.com/docs"
    assert payload["canonical_url"] == "https://example.com/docs/canonical"
    assert payload["final_url"] == "https://example.com/docs/final"
    assert payload["title"] == "Veritas Docs - Architecture"
    assert payload["custom_tag"] == "arch_doc"


@pytest.mark.asyncio
async def test_d4_8_qdrant_payload_file_upload_regression():
    """D4.8-TEST-02: Regular file uploads default to source_type='file_upload' and null URL provenance."""
    session = AsyncMock()
    provider = AsyncMock()
    dispatcher = AsyncMock()

    doc_id = uuid.uuid4()
    version_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    tenant_id = "tenant_test_456"

    mock_emb = MagicMock(spec=ChunkEmbedding)
    mock_emb.chunk_id = chunk_id
    mock_emb.document_version_id = version_id
    mock_emb.tenant_id = tenant_id
    mock_emb.content_hash = "def456hash"
    mock_emb.dimension = 384
    mock_emb.provider = "sentence-transformers"
    mock_emb.model_name = "all-MiniLM-L6-v2"
    mock_emb.embedding_vector = [0.2] * 384

    mock_chunk = MagicMock(spec=DocumentChunk)
    mock_chunk.id = chunk_id
    mock_chunk.document_version_id = version_id
    mock_chunk.tenant_id = tenant_id
    mock_chunk.content = "PDF document text."
    mock_chunk.strategy_used = "hierarchical"
    mock_chunk.chunk_index = 0
    mock_chunk.token_count = 5
    mock_chunk.character_count = 18
    mock_chunk.section_path = None
    mock_chunk.page_numbers = [1]

    mock_doc = MagicMock(spec=Document)
    mock_doc.id = doc_id
    mock_doc.tenant_id = tenant_id
    mock_doc.filename = "report.pdf"
    mock_doc.source_type = "file_upload"
    mock_doc.source_url = None
    mock_doc.canonical_url = None
    mock_doc.final_url = None
    mock_doc.user_metadata = {}

    # Mock queries
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

    session.execute = mock_execute

    service = VectorStorageService(session=session, provider=provider, dispatcher=dispatcher)
    service.repo.get_or_create_metadata = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))
    service.repo.update_sync_status = AsyncMock()
    service.cleanup_old_versions_vectors = AsyncMock(return_value=0)

    with pytest.MonkeyPatch.context() as mp:
        mock_doc_repo_class = MagicMock()
        mock_doc_repo_inst = MagicMock()
        mock_doc_repo_inst.get_by_id = AsyncMock(return_value=mock_doc)
        mock_doc_repo_class.return_value = mock_doc_repo_inst
        mp.setattr("backend.document.repositories.document_repository.DocumentRepository", mock_doc_repo_class)

        provider.upsert_points = AsyncMock(return_value=1)

        count = await service.sync_document_vectors(doc_id, version_id, tenant_id)

    assert count == 1
    upserted_points = provider.upsert_points.call_args[0][1]
    payload = upserted_points[0].payload

    assert payload["source_type"] == "file_upload"
    assert payload["source_url"] is None
    assert payload["canonical_url"] is None
    assert payload["final_url"] is None
    assert payload["title"] == "report.pdf"


def test_d4_8_candidate_and_ranked_evidence_provenance_propagation():
    """D4.8-TEST-03: Retrieval candidate and fusion evidence propagate website provenance metadata."""
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    version_id = uuid.uuid4()
    tenant_id = "tenant_test_789"

    raw_payload_metadata = {
        "source_type": "website",
        "source_url": "https://example.com/api",
        "canonical_url": "https://example.com/api/v1",
        "final_url": "https://example.com/api/v1/overview",
        "title": "API Documentation",
        "strategy_used": "hierarchical",
        "chunk_index": 2,
    }

    candidate = CandidatePointDTO(
        chunk_id=chunk_id,
        document_id=doc_id,
        document_version_id=version_id,
        tenant_id=tenant_id,
        content="Overview of API endpoints.",
        score=0.92,
        source="dense",
        rank=1,
        metadata=raw_payload_metadata,
    )

    # Candidate metadata contains website provenance
    assert candidate.metadata["source_type"] == "website"
    assert candidate.metadata["source_url"] == "https://example.com/api"
    assert candidate.metadata["final_url"] == "https://example.com/api/v1/overview"

    # Test FusionEngine passes metadata into RankedEvidenceDTO
    ranked_list = FusionEngine.execute_rrf_fusion(
        dense_candidates=[candidate],
        sparse_candidates=[],
        rrf_k=60,
    )
    assert len(ranked_list) == 1
    evidence: RankedEvidenceDTO = ranked_list[0]

    assert evidence.chunk_id == chunk_id
    assert evidence.document_id == doc_id
    assert evidence.document_version_id == version_id
    assert evidence.metadata["source_type"] == "website"
    assert evidence.metadata["source_url"] == "https://example.com/api"
    assert evidence.metadata["canonical_url"] == "https://example.com/api/v1"
    assert evidence.metadata["final_url"] == "https://example.com/api/v1/overview"
    assert evidence.metadata["title"] == "API Documentation"
