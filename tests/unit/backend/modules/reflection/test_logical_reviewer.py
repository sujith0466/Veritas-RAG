import pytest
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
