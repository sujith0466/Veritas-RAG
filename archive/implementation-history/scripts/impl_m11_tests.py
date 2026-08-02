import os
import sys
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 11.4: Unit Tests & Verification
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 11.4 Implementation (Tests)...")
    os.makedirs("tests/unit/backend/modules/reflection", exist_ok=True)
    
    # 1. test_completeness_evaluator.py
    t_comp_path = "tests/unit/backend/modules/reflection/test_completeness_evaluator.py"
    with open(t_comp_path, "w") as f:
        f.write("""import pytest
import pytest_asyncio
from backend.modules.reflection.services.completeness_evaluator import CompletenessEvaluator

@pytest.mark.asyncio
async def test_completeness_perfect_match():
    evaluator = CompletenessEvaluator()
    query = "What is the capital of France and what is the population?"
    answer = "The capital of France is Paris and its population is 2 million."
    
    score, unaddressed = await evaluator.evaluate(query, answer)
    assert score == 1.0
    assert len(unaddressed) == 0

@pytest.mark.asyncio
async def test_completeness_partial_match():
    evaluator = CompletenessEvaluator()
    query = "What is the capital of France and what is the population?"
    answer = "The capital of France is Paris."
    
    score, unaddressed = await evaluator.evaluate(query, answer)
    assert score == 0.5
    assert len(unaddressed) == 1
    assert "population" in unaddressed[0]
""")

    # 2. test_logical_reviewer.py
    t_logic_path = "tests/unit/backend/modules/reflection/test_logical_reviewer.py"
    with open(t_logic_path, "w") as f:
        f.write("""import pytest
from backend.modules.reflection.services.logical_reviewer import LogicalConsistencyReviewer
from backend.modules.reflection.schemas.reflection_dto import ClaimValidationResultDTO, ClaimVerdict

@pytest.mark.asyncio
async def test_logical_reviewer_no_contradictions():
    reviewer = LogicalConsistencyReviewer()
    claims = [
        ClaimValidationResultDTO(claim_text="The company made $1B.", verdict=ClaimVerdict.SUPPORTED, citation_index=1),
        ClaimValidationResultDTO(claim_text="The CEO is John Doe.", verdict=ClaimVerdict.SUPPORTED, citation_index=2)
    ]
    
    score, contradictions = await reviewer.review(claims, ["excerpt 1", "excerpt 2"])
    assert score == 1.0
    assert len(contradictions) == 0

@pytest.mark.asyncio
async def test_logical_reviewer_with_contradictions():
    reviewer = LogicalConsistencyReviewer()
    claims = [
        ClaimValidationResultDTO(claim_text="The policy is valid.", verdict=ClaimVerdict.SUPPORTED, citation_index=1),
        ClaimValidationResultDTO(claim_text="The policy is not valid.", verdict=ClaimVerdict.SUPPORTED, citation_index=2)
    ]
    
    score, contradictions = await reviewer.review(claims, ["excerpt 1", "excerpt 2"])
    assert score == 0.0
    assert len(contradictions) == 1
""")

    # 3. test_reflection_engine_v2.py
    t_engine_path = "tests/unit/backend/modules/reflection/test_reflection_engine_v2.py"
    with open(t_engine_path, "w") as f:
        f.write("""import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.modules.reflection.services.reflection_engine import ReflectionEngineV2
from backend.modules.reflection.schemas.reflection_dto import ReflectionRequestDTOv2, ClaimVerdict
from backend.modules.generation.schemas.generation_dto import GroundedAnswerDTO, CitationDTO

@pytest.mark.asyncio
async def test_reflection_engine_v2_success():
    mock_repo = AsyncMock()
    engine = ReflectionEngineV2(repository=mock_repo)
    
    request = ReflectionRequestDTOv2(
        grounded_answer=GroundedAnswerDTO(
            citations=[CitationDTO(citation_index=1, excerpt="The sky is blue.", chunk_id="chunk1", document_id="doc1")],
            is_fully_grounded=True,
            correlation_id="corr-1",
            evidence_used_count=1,
            answer_text="The sky is blue. [1]"
        ),
        original_query="What color is the sky?",
        correlation_id="corr-1",
        tenant_id="tenant-1"
    )
    
    # We run the real engine, which uses the naive Completeness/Logical classes
    result = await engine.reflect_async(request)
    
    assert result.overall_verdict == ClaimVerdict.SUPPORTED
    assert result.is_safe_to_serve is True
    assert result.scores.completeness_score == 1.0
    assert result.scores.consistency_score == 1.0
    assert mock_repo.save_log.called
""")

    print("Created test files.")
    
    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/backend/modules/reflection"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    print("Milestone 11.4 completed.")

if __name__ == "__main__":
    main()
