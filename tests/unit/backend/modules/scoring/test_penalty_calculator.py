from backend.modules.scoring.schemas.scoring_dto import ScoringInputsDTO
from backend.modules.scoring.services.penalty_calculator import PenaltyCalculator


def test_calculate_penalty():
    calculator = PenaltyCalculator()
    inputs = ScoringInputsDTO(
        retrieval_relevance_score=1.0,
        validation_entailment_ratio=1.0,
        confidence_evidence_strength=1.0,
        reflection_completeness=1.0,
        unsupported_claim_count=1,
        invalid_citation_count=2
    )

    deduction, breakdown = calculator.calculate_penalty(inputs)

    assert deduction == 35.0  # 15 + 20
    assert breakdown["unsupported_claim_deduction"] == 15.0
    assert breakdown["invalid_citation_deduction"] == 20.0
