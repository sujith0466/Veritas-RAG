import re
import logging
from backend.modules.reflection.schemas.reflection_dto import (
    ReflectionRequestDTO,
    ReflectionResultDTO,
    ClaimVerdict,
    ClaimValidationResultDTO
)
from backend.modules.reflection.services.claim_validator import ClaimValidator

logger = logging.getLogger(__name__)

# Sentence extraction pattern for claim splitting
_SENTENCE_PATTERN = re.compile(r'([A-Z][^.!?]*[.!?])', re.DOTALL)
_CITATION_MARKER_PATTERN = re.compile(r'\[(\d+)\]')

# Threshold: if hallucination_score > this, answer is not safe to serve
HALLUCINATION_THRESHOLD = 0.3


import time
from backend.observability.metrics import (
    record_reflection_metric,
    record_stage_duration,
)
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

        after_sentence = remaining[pos + len(sentence):]
        remaining = after_sentence

        # Look for a citation marker immediately following this sentence
        marker_match = re.match(r'\s*(\[\d+\])', after_sentence)
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

            result = self.claim_validator.validate_claim(claim_text, citation_index, citations)
            validation_results.append(result)

        if not validation_results:
            logger.info(f"[{request.correlation_id}] No meaningful claims to reflect on.")
            return ReflectionResultDTO(
                correlation_id=request.correlation_id,
                overall_verdict=ClaimVerdict.SUPPORTED,
                hallucination_score=0.0,
                claim_results=[],
                is_safe_to_serve=True
            )

        # Compute hallucination score
        unsupported_count = sum(
            1 for r in validation_results
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
            hallucination_score < HALLUCINATION_THRESHOLD and
            overall_verdict != ClaimVerdict.CONTRADICTED
        )

        logger.info(
            f"[{request.correlation_id}] Reflection complete: hallucination={hallucination_score:.2f} "
            f"verdict={overall_verdict} safe={is_safe}"
        )

        duration = time.perf_counter() - start_time
        record_stage_duration("reflection", duration)
        record_reflection_metric(
            failed=not is_safe,
            hallucination_detected=hallucination_score > 0.0 or overall_verdict == ClaimVerdict.CONTRADICTED,
            reason=str(overall_verdict),
        )

        with trace_reflection(claim_count=len(validation_results), entailment_ratio=1.0 - hallucination_score):
            return ReflectionResultDTO(
                correlation_id=request.correlation_id,
                overall_verdict=overall_verdict,
                hallucination_score=hallucination_score,
                claim_results=validation_results,
                is_safe_to_serve=is_safe
            )

