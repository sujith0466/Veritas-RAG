import pytest

from backend.modules.confidence.services.confidence_engine import ConfidenceEngine
from backend.modules.confidence.services.contradiction_detector import ContradictionDetector
from backend.modules.confidence.services.coverage_analyzer import CoverageAnalyzer
from backend.modules.confidence.services.freshness_scorer import FreshnessScorer
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.generation_service import GroundedGenerationService
from backend.modules.query_rewrite.services.clarification_engine import ClarificationEngine
from backend.modules.query_rewrite.strategies.decomposition import DecompositionRewriter
from backend.modules.query_rewrite.strategies.disambiguation import DisambiguationRewriter
from backend.modules.query_rewrite.strategies.hyde import HyDERewriter
from backend.modules.reflection.services.claim_validator import ClaimValidator
from backend.modules.reflection.services.reflection_engine import ReflectionEngine
from backend.modules.reliability.schemas.reliability_dto import (
    ReliableCandidateDTO,
    ReliableRetrievalResultDTO,
)
from backend.modules.scoring.schemas.scoring_dto import GatewayOutcome, GatewayRequestDTO
from backend.modules.scoring.services.execution_gateway import ExecutionGateway
from backend.modules.scoring.services.reliability_scorer import ReliabilityScorer


@pytest.fixture
def gateway():
    confidence_engine = ConfidenceEngine(
        coverage_analyzer=CoverageAnalyzer(),
        contradiction_detector=ContradictionDetector(),
        freshness_scorer=FreshnessScorer()
    )
    clarification_engine = ClarificationEngine(
        decomposition=DecompositionRewriter(),
        hyde=HyDERewriter(),
        disambiguation=DisambiguationRewriter()
    )
    generation_service = GroundedGenerationService(
        citation_extractor=CitationExtractor(),
        llm_provider=None
    )
    reflection_engine = ReflectionEngine(claim_validator=ClaimValidator())
    scorer = ReliabilityScorer()

    return ExecutionGateway(
        confidence_engine=confidence_engine,
        clarification_engine=clarification_engine,
        generation_service=generation_service,
        reflection_engine=reflection_engine,
        reliability_scorer=scorer,
        max_retries=2
    )


def _make_retrieval(query: str, candidates_count: int = 3) -> ReliableRetrievalResultDTO:
    # Use clean, static factual content that does NOT embed the query string.
    # This prevents sentence-splitter issues from ? marks inside chunk content.
    contents = [
        "FastAPI is an async Python web framework built on Starlette with native Pydantic v2 validation. "
        "It provides automatic OpenAPI documentation for every endpoint without manual configuration.",

        "FastAPI supports dependency injection natively and runs on the ASGI standard for async workloads. "
        "Its performance benchmarks consistently place it among the fastest Python frameworks available.",

        "FastAPI uses type annotations for request validation and response serialization at runtime. "
        "This ensures strict schema enforcement and enables IDE autocompletion across the entire codebase.",
    ]
    candidates = [
        ReliableCandidateDTO(
            chunk_id=f"chk_{i}",
            document_id="doc_1",
            document_version_id="v1",
            tenant_id="t1",
            content=contents[i % len(contents)],
            score=0.9 - (i * 0.05),
            metadata={"created_at": "2026-07-01T00:00:00Z"}
        )
        for i in range(candidates_count)
    ]
    return ReliableRetrievalResultDTO(
        query_text=query,
        tenant_id="t1",
        correlation_id="corr_gw_test",
        candidates=candidates,
        duration_ms=120.0
    )


def test_gateway_success_path(gateway):
    request = GatewayRequestDTO(
        query="What is FastAPI and how does it work?",
        tenant_id="t1",
        correlation_id="corr_gw_1"
    )
    retrieval = _make_retrieval("What is FastAPI and how does it work?", candidates_count=3)
    response = gateway.process(request, retrieval)

    assert response.outcome == GatewayOutcome.SUCCESS
    assert response.answer is not None
    assert response.reliability_score is not None
    assert response.reliability_score.final_score > 0


def test_gateway_low_evidence_aborts(gateway):
    request = GatewayRequestDTO(
        query="What is the quantum flux capacitor timeout?",
        tenant_id="t1",
        correlation_id="corr_gw_2"
    )
    # Zero candidates → should result in abort or degraded outcome
    retrieval = _make_retrieval("quantum flux", candidates_count=0)
    response = gateway.process(request, retrieval)

    # With no candidates, confidence score will be very low → ABORT or max retries
    assert response.outcome in [
        GatewayOutcome.ABORTED_LOW_CONFIDENCE,
        GatewayOutcome.ABORTED_MAX_RETRIES,
        GatewayOutcome.ABORTED_HALLUCINATION
    ]


def test_reliability_scorer_computes_correctly():
    from backend.modules.confidence.schemas.confidence_dto import (
        ConfidenceAction,
        ConfidenceResultDTO,
        ContradictionReportDTO,
        CoverageMetricsDTO,
        FreshnessReportDTO,
    )
    from backend.modules.reflection.schemas.reflection_dto import ClaimVerdict, ReflectionResultDTO
    from backend.modules.retry.schemas.retry_dto import RetryContextDTO

    scorer = ReliabilityScorer()

    confidence = ConfidenceResultDTO(
        score=80.0, action=ConfidenceAction.PROCEED,
        coverage_metrics=CoverageMetricsDTO(coverage_score=0.9, clauses_covered=3, total_clauses=3),
        contradiction_report=ContradictionReportDTO(contradiction_score=0.0, contradictory_pairs=[]),
        freshness_report=FreshnessReportDTO(freshness_score=0.95, oldest_chunk_age_days=30.0),
        is_degraded=False
    )
    reflection = ReflectionResultDTO(
        correlation_id="corr_score_1",
        overall_verdict=ClaimVerdict.SUPPORTED,
        hallucination_score=0.0,
        claim_results=[],
        is_safe_to_serve=True
    )
    retry_ctx = RetryContextDTO(correlation_id="corr_score_1", original_query="test", max_retries=2)

    result = scorer.compute(confidence, reflection, retry_ctx, is_fully_grounded=True)
    # confidence=80*0.4=32, hallucination=1.0*100*0.4=40, retry_efficiency=1.0*100*0.2=20 → 92
    assert result.final_score == pytest.approx(92.0, abs=0.5)
    assert result.is_safe_to_serve is True
    assert result.retry_attempts == 0
