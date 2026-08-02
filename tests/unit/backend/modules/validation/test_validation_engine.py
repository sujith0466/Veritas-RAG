from unittest.mock import AsyncMock

import pytest

from backend.modules.generation.schemas.generation_dto import CitationDTO, GroundedAnswerDTO
from backend.modules.validation.providers.cross_encoder_provider import MockCrossEncoderProvider
from backend.modules.validation.schemas.validation_dto import (
    EntailmentVerdict,
    ValidationRequestDTO,
)
from backend.modules.validation.services.nli_engine import NLIValidationEngine
from backend.modules.validation.services.validation_engine import ValidationEngine


@pytest.mark.asyncio
async def test_validation_engine_success():
    mock_repo = AsyncMock()
    nli_engine = NLIValidationEngine(MockCrossEncoderProvider())
    engine = ValidationEngine(repository=mock_repo, nli_engine=nli_engine)

    request = ValidationRequestDTO(
        grounded_answer=GroundedAnswerDTO(
            answer_text="The sky is blue [1].",
            citations=[CitationDTO(citation_index=1, excerpt="The sky is blue.", chunk_id="c1", document_id="d1")],
            is_fully_grounded=True,
            correlation_id="corr-1",
            evidence_used_count=1
        ),
        correlation_id="corr-1",
        tenant_id="tenant-1"
    )

    result = await engine.validate(request)

    assert result.overall_verdict == EntailmentVerdict.ENTAILED
    assert result.is_valid is True
    assert result.entailment_ratio == 1.0
    assert result.invalid_citation_count == 0
    assert mock_repo.save_log.called
