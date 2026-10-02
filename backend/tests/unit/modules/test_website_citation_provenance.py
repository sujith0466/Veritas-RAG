"""Unit tests for D4.9 Citation Provenance."""

import json
from unittest.mock import MagicMock
import uuid

import pytest

from backend.modules.generation.schemas.generation_dto import (
    CitationDTO,
    GenerationRequestDTOv2,
    StreamingGenerationChunkDTO,
)
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.streaming_generation_service import (
    StreamingGroundedGenerationService,
)
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO


def _create_mock_web_evidence(
    index: int,
    content: str,
    source_url: str = "https://docs.example.com/guide",
    canonical_url: str = "https://docs.example.com/guide/v2",
    final_url: str = "https://docs.example.com/guide/v2/overview",
    title: str = "Example Developer Guide",
    version_id: uuid.UUID | None = None,
) -> RankedEvidenceDTO:
    doc_id = uuid.uuid4()
    ver_id = version_id or uuid.uuid4()
    chunk_id = uuid.uuid4()
    return RankedEvidenceDTO(
        chunk_id=chunk_id,
        document_id=doc_id,
        document_version_id=ver_id,
        tenant_id="tenant_web_citations",
        content=content,
        rrf_score=0.90,
        final_rank=index,
        normalized_relevance_score=0.95,
        metadata={
            "source_type": "website",
            "source_url": source_url,
            "canonical_url": canonical_url,
            "final_url": final_url,
            "title": title,
            "filename": title,
        },
    )


def _create_mock_file_evidence(
    index: int,
    content: str,
    filename: str = "annual_report.pdf",
    version_id: uuid.UUID | None = None,
) -> RankedEvidenceDTO:
    doc_id = uuid.uuid4()
    ver_id = version_id or uuid.uuid4()
    chunk_id = uuid.uuid4()
    return RankedEvidenceDTO(
        chunk_id=chunk_id,
        document_id=doc_id,
        document_version_id=ver_id,
        tenant_id="tenant_file_citations",
        content=content,
        rrf_score=0.88,
        final_rank=index,
        normalized_relevance_score=0.92,
        metadata={
            "source_type": "file_upload",
            "filename": filename,
            "source_name": filename,
        },
    )


def test_d4_9_extract_website_citation_provenance():
    """D4.9-TEST-01: CitationExtractor extracts full website provenance from evidence chunks."""
    extractor = CitationExtractor()
    web_chunk = _create_mock_web_evidence(
        1,
        "Authentication is enforced via JWT bearer tokens and strict tenant namespaces.",
        source_url="https://docs.example.com/auth",
        canonical_url="https://docs.example.com/auth/canonical",
        final_url="https://docs.example.com/auth/final",
        title="Authentication Guide",
    )

    answer_text = "The system enforces security using JWT bearer tokens. [1]"
    citations = extractor.extract(answer_text, [web_chunk])

    assert len(citations) == 1
    cit: CitationDTO = citations[0]

    assert cit.citation_index == 1
    assert cit.chunk_id == str(web_chunk.chunk_id)
    assert cit.document_id == str(web_chunk.document_id)
    assert cit.document_version_id == str(web_chunk.document_version_id)
    assert cit.source_type == "website"
    assert cit.source_url == "https://docs.example.com/auth"
    assert cit.canonical_url == "https://docs.example.com/auth/canonical"
    assert cit.final_url == "https://docs.example.com/auth/final"
    assert cit.title == "Authentication Guide"
    assert "JWT bearer tokens" in cit.excerpt
    assert cit.relevance_score == 0.95


def test_d4_9_extract_single_website_citation():
    """D4.9-TEST-02: extract_single extracts website provenance for progressive streaming."""
    extractor = CitationExtractor()
    web_chunk = _create_mock_web_evidence(
        1,
        "Vector search is performed in Qdrant with HNSW cosine distance.",
        source_url="https://docs.example.com/vector",
        title="Vector Guide",
    )

    seen = set()
    cit = extractor.extract_single(1, [web_chunk], seen)

    assert cit is not None
    assert cit.citation_index == 1
    assert cit.source_type == "website"
    assert cit.source_url == "https://docs.example.com/vector"
    assert cit.title == "Vector Guide"
    assert cit.document_version_id == str(web_chunk.document_version_id)
    assert cit.id is not None
    assert 1 in seen


def test_d4_9_file_upload_citation_regression():
    """D4.9-TEST-03: File upload citations maintain source_type='file_upload' and null URL provenance."""
    extractor = CitationExtractor()
    file_chunk = _create_mock_file_evidence(
        1,
        "Q3 financial results indicate 25% year-over-year revenue growth.",
        filename="q3_financials.pdf",
    )

    answer_text = "Revenue grew by 25% year-over-year in Q3. [1]"
    citations = extractor.extract(answer_text, [file_chunk])

    assert len(citations) == 1
    cit = citations[0]

    assert cit.source_type == "file_upload"
    assert cit.source_url is None
    assert cit.canonical_url is None
    assert cit.final_url is None
    assert cit.source_name == "q3_financials.pdf"
    assert cit.document_version_id == str(file_chunk.document_version_id)


@pytest.mark.asyncio
async def test_d4_9_streaming_generation_website_citations_progressive():
    """D4.9-TEST-04: Streaming generation progressively emits website citations with full provenance."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    async def mock_stream(req):
        yield "Web knowledge source provides "
        yield "comprehensive API documentation. [1] "
        yield "All endpoints are strictly authenticated."

    mock_llm.stream = mock_stream
    service = StreamingGroundedGenerationService(citation_extractor=extractor, llm_provider=mock_llm)

    web_chunk = _create_mock_web_evidence(
        1,
        "Comprehensive API documentation and endpoints.",
        source_url="https://example.com/api",
        canonical_url="https://example.com/api/v1",
        final_url="https://example.com/api/v1/endpoints",
        title="API Reference",
    )

    req = GenerationRequestDTOv2(
        query="Tell me about the API endpoints",
        evidence_chunks=[web_chunk],
        correlation_id="corr-web-cit-1",
        tenant_id="tenant_web_citations",
        stream=True,
    )

    chunks: list[StreamingGenerationChunkDTO] = []
    async for chunk in service.generate_stream(req):
        chunks.append(chunk)

    intermediate_with_citations = [c for c in chunks if not c.is_final and c.citations_delta]
    assert len(intermediate_with_citations) == 1
    cit_delta = intermediate_with_citations[0].citations_delta[0]

    assert cit_delta.source_type == "website"
    assert cit_delta.source_url == "https://example.com/api"
    assert cit_delta.final_url == "https://example.com/api/v1/endpoints"
    assert cit_delta.title == "API Reference"

    # Terminal chunk
    final_chunk = chunks[-1]
    assert final_chunk.is_final is True
    assert len(final_chunk.citations_delta) == 1
    final_cit = final_chunk.citations_delta[0]
    assert final_cit.source_type == "website"
    assert final_cit.source_url == "https://example.com/api"


def test_d4_9_citation_json_serialization_compatibility():
    """D4.9-TEST-05: CitationDTO with website provenance serializes cleanly to JSON and dictionary."""
    ver_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    cit = CitationDTO(
        id="det-cit-id-123",
        citation_index=1,
        chunk_id=str(chunk_id),
        document_id=str(doc_id),
        document_version_id=str(ver_id),
        source_type="website",
        source_url="https://veritas.ai/docs",
        canonical_url="https://veritas.ai/docs/v1",
        final_url="https://veritas.ai/docs/v1/rag",
        title="Veritas RAG Overview",
        source_name="Veritas RAG Overview",
        document_name="Veritas RAG Overview",
        excerpt="Veritas provides deterministic RAG reliability scoring.",
        relevance_score=0.98,
    )

    dumped = cit.model_dump()
    assert dumped["source_type"] == "website"
    assert dumped["source_url"] == "https://veritas.ai/docs"
    assert dumped["canonical_url"] == "https://veritas.ai/docs/v1"
    assert dumped["final_url"] == "https://veritas.ai/docs/v1/rag"
    assert dumped["document_version_id"] == str(ver_id)

    raw_json = cit.model_dump_json()
    parsed = json.loads(raw_json)
    assert parsed["source_type"] == "website"
    assert parsed["source_url"] == "https://veritas.ai/docs"
    assert parsed["final_url"] == "https://veritas.ai/docs/v1/rag"
