import os
import subprocess
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 13.4: Unit Tests & Verification
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 13.4 Implementation (Tests)...")
    os.makedirs("tests/unit/backend/modules/scoring", exist_ok=True)

    # 1. test_base_scorer.py
    t_scorer_path = "tests/unit/backend/modules/scoring/test_base_scorer.py"
    with open(t_scorer_path, "w") as f:
        f.write("""import pytest
from backend.modules.scoring.services.base_scorer import BaseReliabilityScorer
from backend.modules.scoring.schemas.scoring_dto import ScoringInputsDTO

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
    assert score2 == 87.5  # 100 - (0.5 * 0.25 * 100) = 87.5
""")

    # 2. test_penalty_calculator.py
    t_penalty_path = "tests/unit/backend/modules/scoring/test_penalty_calculator.py"
    with open(t_penalty_path, "w") as f:
        f.write("""import pytest
from backend.modules.scoring.services.penalty_calculator import PenaltyCalculator
from backend.modules.scoring.schemas.scoring_dto import ScoringInputsDTO

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
""")

    # 3. test_scoring_engine.py
    t_engine_path = "tests/unit/backend/modules/scoring/test_scoring_engine.py"
    with open(t_engine_path, "w") as f:
        f.write("""import pytest
from unittest.mock import AsyncMock
from backend.modules.scoring.services.scoring_engine import ScoringEngine
from backend.modules.scoring.schemas.scoring_dto import ScoringRequestDTO, ScoringInputsDTO

@pytest.mark.asyncio
async def test_scoring_engine_success():
    mock_repo = AsyncMock()
    engine = ScoringEngine(repository=mock_repo)
    
    request = ScoringRequestDTO(
        correlation_id="corr-1",
        tenant_id="tenant-1",
        inputs=ScoringInputsDTO(
            retrieval_relevance_score=1.0,
            validation_entailment_ratio=1.0,
            confidence_evidence_strength=1.0,
            reflection_completeness=1.0,
            unsupported_claim_count=0,
            invalid_citation_count=0
        )
    )
    
    result = await engine.calculate_score(request)
    
    assert result.final_score == 100.0
    assert result.base_score == 100.0
    assert result.penalty_deduction == 0.0
    assert result.is_trusted is True
    assert mock_repo.save_log.called
""")

    print("Created test files.")

    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/backend/modules/scoring"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    print("Milestone 13.4 completed.")

if __name__ == "__main__":
    main()
