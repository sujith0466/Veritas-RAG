import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 12.3: Orchestrator (ValidationEngine) and APIs
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 12.3 Implementation...")

    # 1. validation_engine.py
    engine_path = "backend/modules/validation/services/validation_engine.py"
    if not os.path.exists(engine_path):
        with open(engine_path, "w") as f:
            f.write("""import os
from backend.modules.validation.schemas.validation_dto import (
    ValidationRequestDTO, ValidationResultDTO, EntailmentVerdict
)
from backend.modules.validation.services.claim_extractor import ClaimExtractor
from backend.modules.validation.services.citation_checker import CitationIntegrityChecker
from backend.modules.validation.services.nli_engine import NLIValidationEngine
from backend.modules.validation.repositories.validation_repository import ValidationRepository

class ValidationEngine:
    def __init__(
        self,
        repository: ValidationRepository,
        nli_engine: NLIValidationEngine
    ):
        self.repository = repository
        self.nli_engine = nli_engine
        self.claim_extractor = ClaimExtractor()
        self.citation_checker = CitationIntegrityChecker()
        
        self.entailment_threshold = float(os.getenv("RAGUARD_VALIDATION_ENTAILMENT_THRESHOLD", "0.8"))

    async def validate(self, request: ValidationRequestDTO) -> ValidationResultDTO:
        answer = request.grounded_answer
        
        # 1. Extract claims
        extracted = self.claim_extractor.extract_atomic_claims(answer.answer_text)
        
        # 2. Check citations
        used_indices = [idx for _, idx in extracted]
        invalid_citations = self.citation_checker.verify_integrity(answer.citations, used_indices)
        
        # 3. NLI Entailment
        claim_details = await self.nli_engine.validate_claims(extracted, answer.citations)
        
        # 4. Aggregation
        total_claims = len(claim_details)
        entailed_count = sum(1 for c in claim_details if c.verdict == EntailmentVerdict.ENTAILED)
        unsupported_count = total_claims - entailed_count
        contradicted_count = sum(1 for c in claim_details if c.verdict == EntailmentVerdict.CONTRADICTED)
        
        entailment_ratio = (entailed_count / total_claims) if total_claims > 0 else 1.0
        
        overall_verdict = EntailmentVerdict.ENTAILED
        if contradicted_count > 0:
            overall_verdict = EntailmentVerdict.CONTRADICTED
        elif unsupported_count > 0:
            overall_verdict = EntailmentVerdict.NEUTRAL
            
        is_valid = (
            contradicted_count == 0 and 
            entailment_ratio >= self.entailment_threshold and
            len(invalid_citations) == 0
        )
        
        result = ValidationResultDTO(
            correlation_id=request.correlation_id,
            tenant_id=request.tenant_id,
            overall_verdict=overall_verdict,
            entailment_ratio=entailment_ratio,
            unsupported_claim_count=unsupported_count,
            invalid_citation_count=len(invalid_citations),
            claim_details=claim_details,
            is_valid=is_valid
        )
        
        # 5. Save Telemetry
        await self.repository.save_log(result)
        
        return result
""")
        print("Created validation_engine.py")

    # 2. api/routes.py
    with open("backend/modules/validation/api/__init__.py", "w") as f:
        f.write('"""Validation API routes."""\n')

    routes_path = "backend/modules/validation/api/routes.py"
    if not os.path.exists(routes_path):
        with open(routes_path, "w") as f:
            f.write("""from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.engine import get_db_session
from backend.modules.validation.schemas.validation_dto import ValidationRequestDTO, ValidationResultDTO
from backend.modules.validation.services.validation_engine import ValidationEngine
from backend.modules.validation.services.nli_engine import NLIValidationEngine
from backend.modules.validation.providers.cross_encoder_provider import MockCrossEncoderProvider
from backend.modules.validation.repositories.validation_repository import ValidationRepository

router = APIRouter(prefix="/validation/v1", tags=["Validation"])

def get_validation_engine(session: AsyncSession = Depends(get_db_session)) -> ValidationEngine:
    repo = ValidationRepository(session)
    # Using mock provider for now
    provider = MockCrossEncoderProvider()
    nli = NLIValidationEngine(provider)
    return ValidationEngine(repo, nli)

@router.post("/verify", response_model=ValidationResultDTO)
async def verify_answer(
    request: ValidationRequestDTO,
    engine: ValidationEngine = Depends(get_validation_engine)
):
    try:
        return await engine.validate(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
""")
        print("Created api/routes.py")

    print("Milestone 12.3 completed.")

if __name__ == "__main__":
    main()
