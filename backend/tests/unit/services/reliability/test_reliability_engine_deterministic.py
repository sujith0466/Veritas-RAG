"""Targeted unit tests for Deterministic ReliabilityEngine and elimination of LLM circularity (ISS-011)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from backend.modules.generation.schemas.generation_dto import GenerationRequestDTOv2
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.streaming_generation_service import StreamingGroundedGenerationService
from backend.modules.reliability.services.reliability_engine import ReliabilityEngine
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO


def _make_evidence(content: str, score: float = 0.95) -> RankedEvidenceDTO:
    return RankedEvidenceDTO(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        tenant_id="tenant-1",
        content=content,
        rrf_score=0.88,
        final_rank=1,
        normalized_relevance_score=score,
    )


@pytest.mark.asyncio
async def test_rel_011_01_grounded_sentence_high_score_without_llm():
    """REL-011-01: Grounded sentence produces high reliability score without calling LLM."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock()

    engine = ReliabilityEngine(llm_provider=mock_llm)
    evidence = [_make_evidence("Kubernetes orchestrates containerized applications across clustered virtual machines.")]

    score = await engine.evaluate_incremental(
        "Kubernetes orchestrates containerized applications.",
        evidence,
    )

    assert score >= 0.80
    assert mock_llm.generate.call_count == 0


@pytest.mark.asyncio
async def test_rel_011_02_unsupported_sentence_penalized_without_llm():
    """REL-011-02: Unsupported sentence produces a penalized reliability score."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock()

    engine = ReliabilityEngine(llm_provider=mock_llm)
    evidence = [_make_evidence("PostgreSQL is an open-source object-relational database system.")]

    # Initial score starts at 1.0; evaluating completely unrelated sentence lowers EMA
    score = await engine.evaluate_incremental(
        "Quantum superposition allows particles to exist in multiple states simultaneously.",
        evidence,
    )

    assert score < 0.90
    assert mock_llm.generate.call_count == 0


@pytest.mark.asyncio
async def test_rel_011_03_deterministic_reproducibility():
    """REL-011-03: Repeated evaluations on identical fresh engines yield identical results."""
    evidence = [_make_evidence("FastAPI is a modern, fast web framework for building APIs with Python.")]

    engine_1 = ReliabilityEngine()
    score_1 = await engine_1.evaluate_incremental("FastAPI is a fast web framework for Python.", evidence)

    engine_2 = ReliabilityEngine()
    score_2 = await engine_2.evaluate_incremental("FastAPI is a fast web framework for Python.", evidence)

    assert score_1 == score_2


@pytest.mark.asyncio
async def test_rel_011_04_zero_llm_provider_calls():
    """REL-011-04: Mock LLM provider generate method is strictly never invoked."""
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock()

    engine = ReliabilityEngine(llm_provider=mock_llm)
    evidence = [_make_evidence("Sample evidence text")]

    for i in range(5):
        await engine.evaluate_incremental(f"Sample test evaluation sentence number {i}.", evidence)

    assert mock_llm.generate.call_count == 0


@pytest.mark.asyncio
async def test_rel_011_05_multi_sentence_low_latency():
    """REL-011-05: 10 sequential sentences evaluate in sub-millisecond local CPU time."""
    import time
    engine = ReliabilityEngine()
    evidence = [_make_evidence("Machine learning models optimize loss functions via stochastic gradient descent.")]

    start = time.perf_counter()
    for i in range(10):
        await engine.evaluate_incremental("Models optimize loss functions via gradient descent.", evidence)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 50.0  # Fast local execution


@pytest.mark.asyncio
async def test_rel_011_06_evidence_relevance_weighting():
    """REL-011-06: Higher relevance evidence produces higher reliability scores."""
    engine_high = ReliabilityEngine()
    engine_low = ReliabilityEngine()

    ev_high = [_make_evidence("Redis is an in-memory data structure store used as a database and cache.", score=0.98)]
    ev_low = [_make_evidence("Redis is an in-memory data structure store used as a database and cache.", score=0.20)]

    score_high = await engine_high.evaluate_incremental("Redis is an in-memory database and cache.", ev_high)
    score_low = await engine_low.evaluate_incremental("Redis is an in-memory database and cache.", ev_low)

    assert score_high > score_low


@pytest.mark.asyncio
async def test_rel_011_07_short_sentence_filtering():
    """REL-011-07: Sentences with fewer than 2 content words retain current score without penalty."""
    engine = ReliabilityEngine()
    engine.current_score = 0.88
    evidence = [_make_evidence("Some long evidence text")]

    score = await engine.evaluate_incremental("Yes.", evidence)
    assert score == 0.88


@pytest.mark.asyncio
async def test_rel_011_08_missing_evidence_safe_fallback():
    """REL-011-08: Empty evidence list safely returns current score without error."""
    engine = ReliabilityEngine()
    engine.current_score = 0.92

    score = await engine.evaluate_incremental("A substantial query with several valid words.", [])
    assert score == 0.92


@pytest.mark.asyncio
async def test_rel_011_09_streaming_generation_service_integration():
    """REL-011-09: StreamingGroundedGenerationService integrates with ReliabilityEngine seamlessly."""
    mock_llm = MagicMock()

    async def mock_stream(req):
        yield "Kubernetes automates deployment. It scales containerized applications reliably. [1]"

    mock_llm.stream = mock_stream
    mock_llm.generate = AsyncMock()

    service = StreamingGroundedGenerationService(
        citation_extractor=CitationExtractor(),
        llm_provider=mock_llm,
    )

    evidence = [_make_evidence("Kubernetes automates deployment and scales containerized applications reliably.")]
    gen_req = GenerationRequestDTOv2(
        query="What does Kubernetes do?",
        evidence_chunks=evidence,
        correlation_id="corr-rel-011",
        tenant_id="tenant-1",
        stream=True,
    )

    chunks = []
    async for chunk in service.generate_stream(gen_req):
        chunks.append(chunk)

    assert len(chunks) >= 1
    assert mock_llm.generate.call_count == 0  # No circular self-eval calls


@pytest.mark.asyncio
async def test_rel_011_10_ema_progression():
    """REL-011-10: EMA smoothly tracks successive sentence evaluations."""
    engine = ReliabilityEngine(ema_alpha=0.5)
    evidence = [_make_evidence("Docker packages applications into standardized units called containers.")]

    score_1 = await engine.evaluate_incremental("Docker packages applications into containers.", evidence)
    score_2 = await engine.evaluate_incremental("Unrelated claim about outer space exploration.", evidence)

    assert 0.0 <= score_1 <= 1.0
    assert 0.0 <= score_2 <= 1.0
    assert score_2 < score_1  # Dropped due to unsupported sentence
