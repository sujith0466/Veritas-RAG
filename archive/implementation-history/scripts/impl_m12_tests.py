import os
import sys
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 12.4: Unit Tests & Verification
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 12.4 Implementation (Tests)...")
    os.makedirs("tests/unit/backend/modules/validation", exist_ok=True)
    
    # 1. test_claim_extractor.py
    t_extractor_path = "tests/unit/backend/modules/validation/test_claim_extractor.py"
    with open(t_extractor_path, "w") as f:
        f.write("""import pytest
from backend.modules.validation.services.claim_extractor import ClaimExtractor

def test_extract_atomic_claims():
    extractor = ClaimExtractor()
    text = "The sky is blue [1]. Water is wet."
    results = extractor.extract_atomic_claims(text)
    
    assert len(results) == 2
    assert results[0][0] == "The sky is blue [1]."
    assert results[0][1] == 1
    assert results[1][0] == "Water is wet."
    assert results[1][1] is None
""")

    # 2. test_citation_checker.py
    t_checker_path = "tests/unit/backend/modules/validation/test_citation_checker.py"
    with open(t_checker_path, "w") as f:
        f.write("""import pytest
from backend.modules.validation.services.citation_checker import CitationIntegrityChecker
from backend.modules.generation.schemas.generation_dto import CitationDTO

def test_citation_integrity():
    checker = CitationIntegrityChecker()
    citations = [
        CitationDTO(citation_index=1, excerpt="ex1", chunk_id="c1", document_id="d1"),
        CitationDTO(citation_index=3, excerpt="ex3", chunk_id="c3", document_id="d3")
    ]
    
    invalid = checker.verify_integrity(citations, [1, 2, 3])
    assert invalid == [2]
""")

    # 3. test_validation_engine.py
    t_engine_path = "tests/unit/backend/modules/validation/test_validation_engine.py"
    with open(t_engine_path, "w") as f:
        f.write("""import pytest
from unittest.mock import AsyncMock
from backend.modules.validation.services.validation_engine import ValidationEngine
from backend.modules.validation.services.nli_engine import NLIValidationEngine
from backend.modules.validation.providers.cross_encoder_provider import MockCrossEncoderProvider
from backend.modules.validation.schemas.validation_dto import ValidationRequestDTO, EntailmentVerdict
from backend.modules.generation.schemas.generation_dto import GroundedAnswerDTO, CitationDTO

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
""")

    print("Created test files.")
    
    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/backend/modules/validation"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    print("Milestone 12.4 completed.")

if __name__ == "__main__":
    main()
