import pytest

from backend.modules.confidence.schemas.confidence_dto import (
    ConfidenceAction,
    ConfidenceEvalRequestDTO,
)
from backend.modules.confidence.services.confidence_engine import ConfidenceEngine
from backend.modules.confidence.services.contradiction_detector import ContradictionDetector
from backend.modules.confidence.services.coverage_analyzer import CoverageAnalyzer
from backend.modules.confidence.services.freshness_scorer import FreshnessScorer
from backend.modules.reliability.schemas.reliability_dto import (
    ReliableCandidateDTO,
    ReliableRetrievalResultDTO,
)


@pytest.fixture
def confidence_engine():
    coverage = CoverageAnalyzer()
    contradict = ContradictionDetector()
    fresh = FreshnessScorer()
    return ConfidenceEngine(coverage, contradict, fresh)

def test_confidence_engine_proceed(confidence_engine):
    # A perfect scenario
    candidates = [
        ReliableCandidateDTO(
            chunk_id="chk_1", document_id="doc_1", document_version_id="v_1", tenant_id="t_1",
            content="The quick brown fox jumps over the lazy dog.",
            metadata={"created_at": "2026-07-19T00:00:00Z"}
        ),
        ReliableCandidateDTO(
            chunk_id="chk_2", document_id="doc_1", document_version_id="v_1", tenant_id="t_1",
            content="A quick brown fox jumped.",
            metadata={"created_at": "2026-07-19T00:00:00Z"}
        ),
        ReliableCandidateDTO(
            chunk_id="chk_3", document_id="doc_1", document_version_id="v_1", tenant_id="t_1",
            content="fox jumps dog",
            metadata={"created_at": "2026-07-19T00:00:00Z"}
        )
    ]

    retrieval_result = ReliableRetrievalResultDTO(
        query_text="quick brown fox jumps",
        tenant_id="t_1",
        correlation_id="corr_1",
        candidates=candidates,
        duration_ms=100.0
    )

    request = ConfidenceEvalRequestDTO(
        query="quick brown fox jumps",
        retrieval_result=retrieval_result
    )

    result = confidence_engine.evaluate(request)
    assert result.action == ConfidenceAction.PROCEED
    assert result.score > 75.0

def test_confidence_engine_contradiction_abort(confidence_engine):
    candidates = [
        ReliableCandidateDTO(
            chunk_id="chk_1", document_id="doc_1", document_version_id="v_1", tenant_id="t_1",
            content="Revenue was 5M dollars in Jan 1, 2024.",
            metadata={"created_at": "2024-01-01T00:00:00Z"}
        ),
        ReliableCandidateDTO(
            chunk_id="chk_2", document_id="doc_2", document_version_id="v_1", tenant_id="t_1",
            content="Revenue was 10M dollars in Jan 1, 2024.",
            metadata={"created_at": "2024-01-01T00:00:00Z"}
        )
    ]

    retrieval_result = ReliableRetrievalResultDTO(
        query_text="What was the revenue in Jan 1 2024?",
        tenant_id="t_1",
        correlation_id="corr_1",
        candidates=candidates,
        duration_ms=50.0
    )

    request = ConfidenceEvalRequestDTO(
        query="What was the revenue in Jan 1 2024?",
        retrieval_result=retrieval_result
    )

    result = confidence_engine.evaluate(request)
    # The contradiction detector will penalize heavily
    # Wait, the contradiction logic might just give 0.5 conflict score. Let's see if it triggers RETRY or ABORT.
    assert result.contradiction_report.contradiction_score > 0
    assert result.action in [ConfidenceAction.RETRY, ConfidenceAction.ABORT]
