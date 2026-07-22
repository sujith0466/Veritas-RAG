import os

from backend.modules.validation.repositories.validation_repository import \
    ValidationRepository
from backend.modules.validation.schemas.validation_dto import (
    EntailmentVerdict, ValidationRequestDTO, ValidationResultDTO)
from backend.modules.validation.services.citation_checker import \
    CitationIntegrityChecker
from backend.modules.validation.services.claim_extractor import ClaimExtractor
from backend.modules.validation.services.nli_engine import NLIValidationEngine


class ValidationEngine:
    def __init__(
        self, repository: ValidationRepository, nli_engine: NLIValidationEngine
    ):
        self.repository = repository
        self.nli_engine = nli_engine
        self.claim_extractor = ClaimExtractor()
        self.citation_checker = CitationIntegrityChecker()

        self.entailment_threshold = float(
            os.getenv("RAGUARD_VALIDATION_ENTAILMENT_THRESHOLD", "0.8")
        )

    async def validate(self, request: ValidationRequestDTO) -> ValidationResultDTO:
        answer = request.grounded_answer

        # 1. Extract claims
        extracted = self.claim_extractor.extract_atomic_claims(answer.answer_text)

        # 2. Check citations
        used_indices = [idx for _, idx in extracted]
        invalid_citations = self.citation_checker.verify_integrity(
            answer.citations, used_indices
        )

        # 3. NLI Entailment
        claim_details = await self.nli_engine.validate_claims(
            extracted, answer.citations
        )

        # 4. Aggregation
        total_claims = len(claim_details)
        entailed_count = sum(
            1 for c in claim_details if c.verdict == EntailmentVerdict.ENTAILED
        )
        unsupported_count = total_claims - entailed_count
        contradicted_count = sum(
            1 for c in claim_details if c.verdict == EntailmentVerdict.CONTRADICTED
        )

        entailment_ratio = (entailed_count / total_claims) if total_claims > 0 else 1.0

        overall_verdict = EntailmentVerdict.ENTAILED
        if contradicted_count > 0:
            overall_verdict = EntailmentVerdict.CONTRADICTED
        elif unsupported_count > 0:
            overall_verdict = EntailmentVerdict.NEUTRAL

        is_valid = (
            contradicted_count == 0
            and entailment_ratio >= self.entailment_threshold
            and len(invalid_citations) == 0
        )

        result = ValidationResultDTO(
            correlation_id=request.correlation_id,
            tenant_id=request.tenant_id,
            overall_verdict=overall_verdict,
            entailment_ratio=entailment_ratio,
            unsupported_claim_count=unsupported_count,
            invalid_citation_count=len(invalid_citations),
            claim_details=claim_details,
            is_valid=is_valid,
        )

        # 5. Save Telemetry
        await self.repository.save_log(result)

        return result
