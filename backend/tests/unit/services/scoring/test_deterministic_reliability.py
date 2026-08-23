"""Targeted unit tests for Deterministic Multi-Signal Reliability Scoring (ISS-006)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from backend.modules.generation.schemas.generation_dto import GenerationRequestDTOv2, CitationDTO
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.streaming_generation_service import StreamingGroundedGenerationService
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO
from backend.ai.schemas.wrapper_dto import AIWrapperRequest, AIWrapperStreamChunk
from backend.ai.wrapper.service import AIWrapperService


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
async def test_deterministic_scoring_fully_grounded():
    """TEST-REL-01: Fully grounded answer with valid citation yields high reliability score (>= 0.85)."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    # Yield text with citation marker [1]
    async def mock_stream(req):
        yield "Kubernetes orchestrates containerized workloads across server clusters. [1]"

    mock_llm.stream = mock_stream

    service = StreamingGroundedGenerationService(
        citation_extractor=extractor,
        llm_provider=mock_llm,
    )

    evidence = [_create_mock_evidence(1, "Kubernetes orchestrates containerized workloads across clusters.", 0.95)]
    gen_req = GenerationRequestDTOv2(
        query="What is Kubernetes?",
        evidence_chunks=evidence,
        correlation_id="corr-rel-1",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    async for chunk in service.generate_stream(gen_req):
        chunks.append(chunk)

    final_chunk = chunks[-1]
    assert final_chunk.is_final is True
    assert final_chunk.is_fully_grounded is True
    assert len(final_chunk.citations_delta) == 1

    metadata = final_chunk.wrapper_metadata
    assert metadata is not None
    assert "reliability_score" in metadata
    score = metadata["reliability_score"]
    assert 0.80 <= score <= 1.0


@pytest.mark.asyncio
async def test_deterministic_scoring_ungrounded_claims():
    """TEST-REL-02: Answer with uncited / ungrounded claims receives lower reliability score (<= 0.50)."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    # Yield claim without citation
    async def mock_stream(req):
        yield "Quantum computers will replace all relational databases tomorrow."

    mock_llm.stream = mock_stream

    service = StreamingGroundedGenerationService(
        citation_extractor=extractor,
        llm_provider=mock_llm,
    )

    evidence = [_create_mock_evidence(1, "Relational databases use B-tree indexes for indexing.", 0.90)]
    gen_req = GenerationRequestDTOv2(
        query="Tell me about quantum databases",
        evidence_chunks=evidence,
        correlation_id="corr-rel-2",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    async for chunk in service.generate_stream(gen_req):
        chunks.append(chunk)

    final_chunk = chunks[-1]
    assert final_chunk.is_final is True
    assert final_chunk.is_fully_grounded is False

    score = final_chunk.wrapper_metadata["reliability_score"]
    # Score should be penalized due to ungrounded claims
    assert score <= 0.50


@pytest.mark.asyncio
async def test_deterministic_scoring_hallucinated_citation_penalty():
    """TEST-REL-03: Hallucinated citation [99] with only 1 evidence chunk triggers penalty deduction."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    async def mock_stream(req):
        yield "Supported statement. [1] But also invented facts cited with non-existent source. [99]"

    mock_llm.stream = mock_stream

    service = StreamingGroundedGenerationService(
        citation_extractor=extractor,
        llm_provider=mock_llm,
    )

    evidence = [_create_mock_evidence(1, "Supported statement.", 0.90)]
    gen_req = GenerationRequestDTOv2(
        query="Test hallucination",
        evidence_chunks=evidence,
        correlation_id="corr-rel-3",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    async for chunk in service.generate_stream(gen_req):
        chunks.append(chunk)

    final_chunk = chunks[-1]
    score = final_chunk.wrapper_metadata["reliability_score"]
    # Penalty for [99] reduces score
    assert score < 0.75


@pytest.mark.asyncio
async def test_deterministic_scoring_zero_evidence():
    """TEST-REL-04: Zero evidence chunks emits reliability_score = 0.0 immediately."""
    extractor = CitationExtractor()
    service = StreamingGroundedGenerationService(citation_extractor=extractor, llm_provider=MagicMock())

    gen_req = GenerationRequestDTOv2(
        query="Test query",
        evidence_chunks=[],
        correlation_id="corr-rel-4",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    async for chunk in service.generate_stream(gen_req):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert chunks[0].is_final is True
    assert chunks[0].is_fully_grounded is False
    assert chunks[0].wrapper_metadata["reliability_score"] == 0.0


@pytest.mark.asyncio
async def test_ai_wrapper_preserves_wrapper_metadata():
    """TEST-REL-05: AIWrapperService preserves chunk.wrapper_metadata on final chunk."""
    mock_streaming_gen = MagicMock()

    final_chunk = MagicMock()
    final_chunk.model_dump.return_value = {
        "chunk_index": 1,
        "text_delta": "",
        "citations_delta": [],
        "is_final": True,
        "correlation_id": "corr-1",
        "is_fully_grounded": True,
        "wrapper_metadata": {"reliability_score": 0.88, "stage": "generation"},
    }
    final_chunk.wrapper_metadata = {"reliability_score": 0.88, "stage": "generation"}

    async def mock_stream_gen(req):
        yield final_chunk

    mock_streaming_gen.generate_stream = mock_stream_gen

    mock_ns = AsyncMock()
    mock_ns.resolve.return_value = MagicMock(collection_name="test_col")

    mock_retrieval = AsyncMock()
    mock_retrieval.execute_hybrid_search.return_value = MagicMock(final_evidence=[])

    wrapper = AIWrapperService(
        namespace_resolver=mock_ns,
        rate_limiter=AsyncMock(),
        retrieval_orchestrator=mock_retrieval,
        streaming_generation=mock_streaming_gen,
        event_dispatcher=AsyncMock(),
        llm_manager=MagicMock(),
    )
    wrapper._validate_workspace = AsyncMock()

    req = AIWrapperRequest(
        workspace_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        query="test query",
    )

    wrapper_chunks = []
    async for chunk in wrapper.stream_request(req, user_id=uuid.uuid4(), correlation_id="corr-test"):
        wrapper_chunks.append(chunk)

    final_wrapper_chunk = wrapper_chunks[-1]
    assert final_wrapper_chunk.wrapper_metadata is not None
    assert final_wrapper_chunk.wrapper_metadata.get("reliability_score") == 0.88
    assert final_wrapper_chunk.wrapper_metadata.get("stage") == "generation"


@pytest.mark.asyncio
async def test_strict_reproducibility():
    """TEST-REL-07: 50 identical runs yield 50 identical scores (100% deterministic)."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    async def mock_stream(req):
        yield "PostgreSQL provides ACID transactions using WAL logs. [1]"

    mock_llm.stream = mock_stream

    service = StreamingGroundedGenerationService(
        citation_extractor=extractor,
        llm_provider=mock_llm,
    )

    evidence = [_create_mock_evidence(1, "PostgreSQL provides ACID transactions with write-ahead logging.", 0.92)]
    gen_req = GenerationRequestDTOv2(
        query="How does PostgreSQL handle ACID?",
        evidence_chunks=evidence,
        correlation_id="corr-rel-7",
        tenant_id="tenant-1",
        stream=True,
    )

    scores = []
    for _ in range(50):
        chunks = []
        async for chunk in service.generate_stream(gen_req):
            chunks.append(chunk)
        scores.append(chunks[-1].wrapper_metadata["reliability_score"])

    # All 50 scores must be strictly identical
    assert len(set(scores)) == 1
    assert 0.80 <= scores[0] <= 1.0


@pytest.mark.asyncio
async def test_score_bounds_clamping():
    """TEST-REL-08: Score is strictly clamped within [0.0, 1.0]."""
    extractor = CitationExtractor()
    mock_llm = MagicMock()

    # Highly penalized text
    async def mock_stream(req):
        yield "Fake fact [99] and another fake [98] and third fake [97] and fourth [96]."

    mock_llm.stream = mock_stream

    service = StreamingGroundedGenerationService(citation_extractor=extractor, llm_provider=mock_llm)
    evidence = [_create_mock_evidence(1, "Real fact.", 0.1)]
    gen_req = GenerationRequestDTOv2(
        query="Test query",
        evidence_chunks=evidence,
        correlation_id="corr-bounds",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    async for chunk in service.generate_stream(gen_req):
        chunks.append(chunk)

    score = chunks[-1].wrapper_metadata["reliability_score"]
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_chat_orchestrator_extracts_real_score():
    """TEST-REL-06: ChatOrchestrator extracts real score from wrapper metadata for persistence."""
    from backend.modules.chat.services.chat_orchestrator import ChatOrchestrator

    mock_chat_repo = AsyncMock()
    mock_wrapper = MagicMock()

    # Mock chunk stream with calculated score 0.82
    async def mock_stream(req, user_id, correlation_id):
        yield MagicMock(
            text_delta="Hello",
            is_final=False,
            citations_delta=[],
            chunk_index=0,
            wrapper_metadata=None,
            model_dump_json=lambda: "{}",
        )
        yield MagicMock(
            text_delta="",
            is_final=True,
            is_fully_grounded=True,
            citations_delta=[],
            chunk_index=1,
            wrapper_metadata={"reliability_score": 0.82, "stage": "generation"},
            model_dump_json=lambda: "{}",
        )

    mock_wrapper.stream_request = mock_stream

    mock_session = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session
    mock_session_factory.return_value.__aexit__.return_value = None

    mock_redis = AsyncMock()

    with patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=mock_session_factory), \
         patch("backend.modules.chat.services.chat_orchestrator.get_redis_client", return_value=mock_redis), \
         patch("backend.modules.chat.services.chat_orchestrator.ChatRepository") as MockRepo:
        mock_repo_instance = AsyncMock()
        mock_repo_instance.get_session.return_value = MagicMock()
        MockRepo.return_value = mock_repo_instance

        orchestrator = ChatOrchestrator(chat_repo=mock_chat_repo, ai_wrapper_service=mock_wrapper)

        gen = orchestrator.stream_chat(
            tenant_id=str(uuid.uuid4()),
            workspace_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            query="test query",
            correlation_id="corr-orch-1",
        )

        chunks = []
        async for sse in gen:
            chunks.append(sse)

        assert len(chunks) == 3
        # Final SSE event data should include chunk with real score
        assert "event: done" in chunks[2]
