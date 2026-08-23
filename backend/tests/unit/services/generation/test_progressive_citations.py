"""Targeted unit tests for Progressive Citation Streaming (ISS-007)."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from backend.modules.generation.schemas.generation_dto import (
    GenerationRequestDTOv2,
    CitationDTO,
    StreamingGenerationChunkDTO,
)
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.streaming_generation_service import StreamingGroundedGenerationService
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO
from backend.api.v1.schemas.sse import SSEMessageDTO


def _create_mock_evidence(index: int, content: str, score: float = 0.9) -> RankedEvidenceDTO:
    return RankedEvidenceDTO(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        tenant_id="tenant-1",
        content=content,
        rrf_score=0.85,
        final_rank=index,
        normalized_relevance_score=score,
        metadata={"filename": f"doc_{index}.pdf", "source_name": f"doc_{index}.pdf"},
    )


@pytest.mark.asyncio
async def test_cit_01_single_valid_citation_progressively_emitted():
    """TEST-CIT-01: Single valid citation marker [1] is emitted progressively before the final chunk."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    async def mock_stream(req):
        yield "PostgreSQL is an open-source database "
        yield "with robust JSONB support. [1] "
        yield "It is widely used in enterprise applications."

    mock_llm.stream = mock_stream
    service = StreamingGroundedGenerationService(citation_extractor=extractor, llm_provider=mock_llm)

    evidence = [_create_mock_evidence(1, "PostgreSQL supports advanced JSONB querying and indexing.", 0.95)]
    req = GenerationRequestDTOv2(
        query="Tell me about PostgreSQL JSONB",
        evidence_chunks=evidence,
        correlation_id="corr-cit-1",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks: list[StreamingGenerationChunkDTO] = []
    async for chunk in service.generate_stream(req):
        chunks.append(chunk)

    # intermediate chunks should have the citation on chunk 1 (0-indexed second chunk)
    intermediate_chunks = [c for c in chunks if not c.is_final]
    citations_emitted = [c for c in intermediate_chunks if c.citations_delta]

    assert len(citations_emitted) == 1
    assert citations_emitted[0].citations_delta[0].citation_index == 1
    assert citations_emitted[0].citations_delta[0].relevance_score == 0.95


@pytest.mark.asyncio
async def test_cit_02_multiple_citations_across_chunks():
    """TEST-CIT-02: Multiple citations [1] and [2] are emitted on their respective intermediate chunks."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    async def mock_stream(req):
        yield "First concept is explained here [1]. "
        yield "Second separate concept is detailed here [2]."

    mock_llm.stream = mock_stream
    service = StreamingGroundedGenerationService(citation_extractor=extractor, llm_provider=mock_llm)

    evidence = [
        _create_mock_evidence(1, "First concept source details.", 0.90),
        _create_mock_evidence(2, "Second concept source details.", 0.85),
    ]
    req = GenerationRequestDTOv2(
        query="Concepts query",
        evidence_chunks=evidence,
        correlation_id="corr-cit-2",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    async for chunk in service.generate_stream(req):
        chunks.append(chunk)

    intermediate = [c for c in chunks if not c.is_final and c.citations_delta]
    assert len(intermediate) == 2
    assert intermediate[0].citations_delta[0].citation_index == 1
    assert intermediate[1].citations_delta[0].citation_index == 2


@pytest.mark.asyncio
async def test_cit_03_duplicate_marker_suppressed():
    """TEST-CIT-03: Repeated marker [1] is only emitted once during the stream."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    async def mock_stream(req):
        yield "Initial statement supported by source [1]. "
        yield "Another follow-up statement citing the same source [1]."

    mock_llm.stream = mock_stream
    service = StreamingGroundedGenerationService(citation_extractor=extractor, llm_provider=mock_llm)

    evidence = [_create_mock_evidence(1, "Source details.", 0.90)]
    req = GenerationRequestDTOv2(
        query="Duplicate citation query",
        evidence_chunks=evidence,
        correlation_id="corr-cit-3",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    async for chunk in service.generate_stream(req):
        chunks.append(chunk)

    intermediate_with_citations = [c for c in chunks if not c.is_final and c.citations_delta]
    # Should only be emitted once across all intermediate chunks
    assert len(intermediate_with_citations) == 1
    assert intermediate_with_citations[0].citations_delta[0].citation_index == 1


@pytest.mark.asyncio
async def test_cit_04_split_citation_marker_across_chunks():
    """TEST-CIT-04: Split marker '[' in chunk N and '1]' in chunk N+1 is detected exactly once."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    async def mock_stream(req):
        yield "Statement with split citation ["
        yield "1] finished here."

    mock_llm.stream = mock_stream
    service = StreamingGroundedGenerationService(citation_extractor=extractor, llm_provider=mock_llm)

    evidence = [_create_mock_evidence(1, "Statement source details.", 0.90)]
    req = GenerationRequestDTOv2(
        query="Split marker query",
        evidence_chunks=evidence,
        correlation_id="corr-cit-4",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    async for chunk in service.generate_stream(req):
        chunks.append(chunk)

    intermediate = [c for c in chunks if not c.is_final and c.citations_delta]
    assert len(intermediate) == 1
    assert intermediate[0].citations_delta[0].citation_index == 1


@pytest.mark.asyncio
async def test_cit_05_hallucinated_marker_scrubbed():
    """TEST-CIT-05: Hallucinated marker [99] with only 1 evidence chunk is not emitted and is scrubbed."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    async def mock_stream(req):
        yield "Real fact [1]. Hallucinated source [99]."

    mock_llm.stream = mock_stream
    service = StreamingGroundedGenerationService(citation_extractor=extractor, llm_provider=mock_llm)

    evidence = [_create_mock_evidence(1, "Real fact content.", 0.90)]
    req = GenerationRequestDTOv2(
        query="Hallucination query",
        evidence_chunks=evidence,
        correlation_id="corr-cit-5",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    async for chunk in service.generate_stream(req):
        chunks.append(chunk)

    intermediate = [c for c in chunks if not c.is_final]
    # Chunk containing [99] should have [99] removed from text_delta
    all_text = "".join(c.text_delta for c in intermediate)
    assert "[99]" not in all_text

    # No citation delta for 99
    all_intermediate_citations = [cit for c in intermediate for cit in c.citations_delta]
    assert len(all_intermediate_citations) == 1
    assert all_intermediate_citations[0].citation_index == 1


@pytest.mark.asyncio
async def test_cit_06_final_citation_reconciliation():
    """TEST-CIT-06: Terminal chunk retains the full reconciled citation set."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    async def mock_stream(req):
        yield "Topic A [1]. Topic B [2]."

    mock_llm.stream = mock_stream
    service = StreamingGroundedGenerationService(citation_extractor=extractor, llm_provider=mock_llm)

    evidence = [
        _create_mock_evidence(1, "Topic A content.", 0.90),
        _create_mock_evidence(2, "Topic B content.", 0.88),
    ]
    req = GenerationRequestDTOv2(
        query="Reconciliation query",
        evidence_chunks=evidence,
        correlation_id="corr-cit-6",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    async for chunk in service.generate_stream(req):
        chunks.append(chunk)

    final_chunk = chunks[-1]
    assert final_chunk.is_final is True
    assert len(final_chunk.citations_delta) == 2
    indices = {c.citation_index for c in final_chunk.citations_delta}
    assert indices == {1, 2}


@pytest.mark.asyncio
async def test_cit_07_zero_evidence_produces_no_citations():
    """TEST-CIT-07: Zero evidence chunks produces no citations and reliability_score remains 0.0."""
    extractor = CitationExtractor()
    service = StreamingGroundedGenerationService(citation_extractor=extractor, llm_provider=MagicMock())

    req = GenerationRequestDTOv2(
        query="Zero evidence query",
        evidence_chunks=[],
        correlation_id="corr-cit-7",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    async for chunk in service.generate_stream(req):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert chunks[0].is_final is True
    assert chunks[0].citations_delta == []
    assert chunks[0].wrapper_metadata["reliability_score"] == 0.0


@pytest.mark.asyncio
async def test_cit_08_stream_interruption():
    """TEST-CIT-08: Cancelled stream does not corrupt citation state."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    async def mock_stream(req):
        yield "Fact [1]"
        raise asyncio.CancelledError()

    mock_llm.stream = mock_stream
    service = StreamingGroundedGenerationService(citation_extractor=extractor, llm_provider=mock_llm)

    evidence = [_create_mock_evidence(1, "Fact content.", 0.90)]
    req = GenerationRequestDTOv2(
        query="Interruption query",
        evidence_chunks=evidence,
        correlation_id="corr-cit-8",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    with pytest.raises(asyncio.CancelledError):
        async for chunk in service.generate_stream(req):
            chunks.append(chunk)

    assert len(chunks) == 1
    assert len(chunks[0].citations_delta) == 1


@pytest.mark.asyncio
async def test_cit_09_sse_serialization_compatibility():
    """TEST-CIT-09: citations_delta in SSE message is valid JSON and adheres to SSE format."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    async def mock_stream(req):
        yield "Point [1]"

    mock_llm.stream = mock_stream
    service = StreamingGroundedGenerationService(citation_extractor=extractor, llm_provider=mock_llm)

    evidence = [_create_mock_evidence(1, "Point content.", 0.90)]
    req = GenerationRequestDTOv2(
        query="SSE query",
        evidence_chunks=evidence,
        correlation_id="corr-cit-9",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    async for chunk in service.generate_stream(req):
        chunks.append(chunk)

    # First chunk has citations_delta
    chunk_0 = chunks[0]
    dto = SSEMessageDTO(
        id=SSEMessageDTO.format_id("corr-cit-9", chunk_0.chunk_index),
        event="chunk",
        data=chunk_0.model_dump_json(),
    )
    sse_str = dto.to_sse_string()
    assert "event: chunk" in sse_str
    assert "citations_delta" in sse_str

    parsed = json.loads(dto.data)
    assert len(parsed["citations_delta"]) == 1
    assert parsed["citations_delta"][0]["citation_index"] == 1


@pytest.mark.asyncio
async def test_cit_10_iss_006_deterministic_reliability_isolation():
    """TEST-CIT-10: Progressive citation streaming does not alter ISS-006 deterministic reliability score."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    async def mock_stream(req):
        yield "Kubernetes orchestrates containerized workloads across server clusters. [1]"

    mock_llm.stream = mock_stream

    evidence = [_create_mock_evidence(1, "Kubernetes orchestrates containerized workloads across clusters.", 0.95)]
    req = GenerationRequestDTOv2(
        query="What is Kubernetes?",
        evidence_chunks=evidence,
        correlation_id="corr-cit-10",
        tenant_id="tenant-1",
        stream=True,
    )

    # 1. Run with progressive citations enabled (default True)
    service_enabled = StreamingGroundedGenerationService(citation_extractor=extractor, llm_provider=mock_llm)
    chunks_enabled = []
    async for chunk in service_enabled.generate_stream(req):
        chunks_enabled.append(chunk)

    score_enabled = chunks_enabled[-1].wrapper_metadata["reliability_score"]

    # 2. Run with progressive citations disabled
    with patch("backend.core.config.get_settings") as mock_settings:
        mock_cfg = MagicMock()
        mock_cfg.features.enable_streaming_citations = False
        mock_cfg.features.enable_streaming_reliability = False
        mock_settings.return_value = mock_cfg

        service_disabled = StreamingGroundedGenerationService(citation_extractor=CitationExtractor(), llm_provider=mock_llm)
        chunks_disabled = []
        async for chunk in service_disabled.generate_stream(req):
            chunks_disabled.append(chunk)

        score_disabled = chunks_disabled[-1].wrapper_metadata["reliability_score"]

    # Final scores MUST be strictly identical
    assert score_enabled == score_disabled
    assert 0.80 <= score_enabled <= 1.0
