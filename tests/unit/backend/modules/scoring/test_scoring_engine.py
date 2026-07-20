import pytest
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
