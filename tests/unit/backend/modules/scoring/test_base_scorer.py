import pytest

from backend.modules.scoring.schemas.scoring_dto import ScoringInputsDTO
from backend.modules.scoring.services.base_scorer import BaseReliabilityScorer


def test_calculate_base_score():
    scorer = BaseReliabilityScorer()
    inputs = ScoringInputsDTO(
        retrieval_relevance_score=1.0,
        validation_entailment_ratio=1.0,
        confidence_evidence_strength=1.0,
        reflection_completeness=1.0
    )
    score = scorer.calculate_base_score(inputs)
    assert score == 100.0

    inputs.retrieval_relevance_score = 0.5
    score2 = scorer.calculate_base_score(inputs)
    assert score2 == pytest.approx(87.5)  # 100 - (0.5 * 0.25 * 100) = 87.5
