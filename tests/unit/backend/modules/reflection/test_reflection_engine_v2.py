import pytest
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
