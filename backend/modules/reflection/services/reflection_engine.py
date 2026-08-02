import logging
import re

from backend.modules.reflection.schemas.reflection_dto import (
    ClaimValidationResultDTO,
    ClaimVerdict,
    ReflectionRequestDTO,
    ReflectionResultDTO,
)
from backend.modules.reflection.services.claim_validator import ClaimValidator

logger = logging.getLogger(__name__)

# Sentence extraction pattern for claim splitting
_SENTENCE_PATTERN = re.compile(r"([A-Z][^.!?]*[.!?])", re.DOTALL)
_CITATION_MARKER_PATTERN = re.compile(r"\[(\d+)\]")

# Threshold: if hallucination_score > this, answer is not safe to serve
HALLUCINATION_THRESHOLD = 0.3


import time

from backend.observability.metrics import record_reflection_metric, record_stage_duration
from backend.observability.tracing import trace_reflection


def _extract_claims_with_citations(answer_text: str) -> list[tuple[str, int | None]]:
    """Extract (sentence, citation_index) pairs from the answer text.

    For each sentence we record the first [N] marker found in or immediately after it.
    """
    # Split into sentences
    sentences = _SENTENCE_PATTERN.findall(answer_text)
    if not sentences:
        sentences = [answer_text]

    result = []
    remaining = answer_text
    for sentence in sentences:
        # Find where this sentence ends in remaining text
        pos = remaining.find(sentence)
        if pos == -1:
            result.append((sentence, None))
            continue

        after_sentence = remaining[pos + len(sentence) :]
        remaining = after_sentence

        # Look for a citation marker immediately following this sentence
        marker_match = re.match(r"\s*(\[\d+\])", after_sentence)
        citation_index = None
        if marker_match:
            marker_text = marker_match.group(1)
            citation_index = int(marker_text.strip("[]"))
        else:
            # Or check inline in the sentence itself
            inline = _CITATION_MARKER_PATTERN.search(sentence)
            if inline:
                citation_index = int(inline.group(1))

        result.append((sentence.strip(), citation_index))

    return result


class ReflectionEngine:
    """Post-generation reflection engine that audits each claim against cited evidence."""

    def __init__(self, claim_validator: ClaimValidator):
        self.claim_validator = claim_validator

    def reflect(self, request: ReflectionRequestDTO) -> ReflectionResultDTO:
        """Validate every claim in the grounded answer against citations."""
        start_time = time.perf_counter()
        answer = request.grounded_answer
        citations = answer.citations

        claim_pairs = _extract_claims_with_citations(answer.answer_text)
        validation_results: list[ClaimValidationResultDTO] = []

        for claim_text, citation_index in claim_pairs:
            words = claim_text.split()
            if len(words) < 4:
                continue  # Skip trivially short fragments

            result = self.claim_validator.validate_claim(
                claim_text, citation_index, citations
            )
            validation_results.append(result)

        if not validation_results:
            logger.info(
                f"[{request.correlation_id}] No meaningful claims to reflect on."
            )
            return ReflectionResultDTO(
                correlation_id=request.correlation_id,
                overall_verdict=ClaimVerdict.SUPPORTED,
                hallucination_score=0.0,
                claim_results=[],
                is_safe_to_serve=True,
            )

        # Compute hallucination score
        unsupported_count = sum(
            1
            for r in validation_results
            if r.verdict in (ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTED)
        )
        hallucination_score = unsupported_count / len(validation_results)

        # Worst-case verdict
        if any(r.verdict == ClaimVerdict.CONTRADICTED for r in validation_results):
            overall_verdict = ClaimVerdict.CONTRADICTED
        elif hallucination_score > 0:
            overall_verdict = ClaimVerdict.UNSUPPORTED
        else:
            overall_verdict = ClaimVerdict.SUPPORTED

        is_safe = (
            hallucination_score < HALLUCINATION_THRESHOLD
            and overall_verdict != ClaimVerdict.CONTRADICTED
        )

        logger.info(
            f"[{request.correlation_id}] Reflection complete: hallucination={hallucination_score:.2f} "
            f"verdict={overall_verdict} safe={is_safe}"
        )

        duration = time.perf_counter() - start_time
        record_stage_duration("reflection", duration)
        record_reflection_metric(
            failed=not is_safe,
            hallucination_detected=hallucination_score > 0.0
            or overall_verdict == ClaimVerdict.CONTRADICTED,
            reason=str(overall_verdict),
        )

        with trace_reflection(
            claim_count=len(validation_results),
            entailment_ratio=1.0 - hallucination_score,
        ):
            return ReflectionResultDTO(
                correlation_id=request.correlation_id,
                overall_verdict=overall_verdict,
                hallucination_score=hallucination_score,
                claim_results=validation_results,
                is_safe_to_serve=is_safe,
            )


import asyncio
import os

from backend.modules.reflection.repositories.reflection_repository import ReflectionRepository
from backend.modules.reflection.schemas.reflection_dto import (
    CompletenessReportDTO,
    LogicalReviewReportDTO,
    ReflectionRequestDTOv2,
    ReflectionResultDTOv2,
    ReflectionScoreDTO,
)
from backend.modules.reflection.services.completeness_evaluator import CompletenessEvaluator
from backend.modules.reflection.services.logical_reviewer import LogicalConsistencyReviewer


class ReflectionEngineV2:
    def __init__(self, repository: ReflectionRepository):
        self.claim_validator = ClaimValidator()
        self.completeness_evaluator = CompletenessEvaluator()
        self.logical_reviewer = LogicalConsistencyReviewer()
        self.repository = repository
        self.max_passes = int(os.getenv("RAGUARD_REFLECTION_MAX_PASSES", "2"))
        self.timeout_ms = int(os.getenv("RAGUARD_REFLECTION_TIMEOUT_MS", "350"))

    async def reflect_async(
        self, request: ReflectionRequestDTOv2
    ) -> ReflectionResultDTOv2:
        attempt = 1
        return await self._execute_pass(request, attempt)

    async def _execute_pass(
        self, request: ReflectionRequestDTOv2, attempt: int
    ) -> ReflectionResultDTOv2:
        answer_text = request.grounded_answer.answer_text
        citations = request.grounded_answer.citations

        # 1. Claim extraction
        extracted_claims = _extract_claims_with_citations(answer_text)

        # 2. Async evaluation gathering
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    self.claim_validator.validate_claims_async(
                        extracted_claims, citations
                    ),
                    self.completeness_evaluator.evaluate(
                        request.original_query, answer_text
                    ),
                ),
                timeout=self.timeout_ms / 1000.0,
            )
            claim_results, (completeness_score, unaddressed) = results
        except TimeoutError:
            # Fallback to basic claim validation on timeout
            claim_results = self.claim_validator.validate_claims(
                extracted_claims, citations
            )
            completeness_score = 1.0
            unaddressed = []

        # 3. Logical Consistency
        consistency_score, contradictions = await self.logical_reviewer.review(
            claim_results, citations
        )

        # 4. Aggregation
        overall_verdict = ClaimVerdict.SUPPORTED
        hallucination_score = 0.0

        if claim_results:
            unsupported_count = sum(
                1 for c in claim_results if c.verdict == ClaimVerdict.UNSUPPORTED
            )
            contradicted_count = sum(
                1 for c in claim_results if c.verdict == ClaimVerdict.CONTRADICTED
            )

            if contradicted_count > 0 or contradictions:
                overall_verdict = ClaimVerdict.CONTRADICTED
            elif unsupported_count > 0:
                overall_verdict = ClaimVerdict.UNSUPPORTED

            hallucination_score = (unsupported_count + contradicted_count) / len(
                claim_results
            )

        is_safe = (
            hallucination_score <= HALLUCINATION_THRESHOLD
            and overall_verdict != ClaimVerdict.CONTRADICTED
            and consistency_score >= 0.85
            and completeness_score >= 0.75
        )

        result = ReflectionResultDTOv2(
            correlation_id=request.correlation_id,
            tenant_id=request.tenant_id,
            overall_verdict=overall_verdict,
            scores=ReflectionScoreDTO(
                hallucination_score=hallucination_score,
                completeness_score=completeness_score,
                consistency_score=consistency_score,
            ),
            claim_results=claim_results,
            completeness_report=CompletenessReportDTO(
                score=completeness_score,
                unaddressed_clauses=unaddressed,
                addressed_clauses=[],
            ),
            logical_report=LogicalReviewReportDTO(
                consistency_score=consistency_score, contradictions_found=contradictions
            ),
            is_safe_to_serve=is_safe,
            attempt_number=attempt,
        )

        # Multi-pass loop placeholder logic
        # If not safe and attempt < max_passes, we could trigger self-correction
        # For now, we return the result and let upstream handle retry (Phase 7/11 hook)

        # Save telemetry
        await self.repository.save_log(result)

        return result
