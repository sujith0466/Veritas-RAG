import structlog

from backend.modules.generation.schemas.generation_dto import (
    GenerationRequestDTO,
    GroundedAnswerDTO,
)
from backend.modules.generation.services.citation_extractor import CitationExtractor

logger = structlog.get_logger(__name__)

# Grounded generation prompt template.
# In production this is sent to the LLM provider. For M4 baseline it creates
# a structured mock response with proper citation markers.
_ANSWER_PROMPT_TEMPLATE = """You are a grounded answer engine. Answer the question using ONLY the evidence provided.
For every factual claim in your answer, include an inline citation marker [N] where N is the evidence number.
Do NOT include any information not found in the evidence.

Question: {query}

Evidence:
{evidence_block}

Answer (with citations):"""


import time

from backend.observability.metrics import record_stage_duration
from backend.observability.tracing import trace_generation


def _build_evidence_block(evidence_chunks: list[dict]) -> str:
    lines = []
    for i, chunk in enumerate(evidence_chunks, start=1):
        content = chunk.get("content", "").replace("\n", " ").strip()
        lines.append(f"[{i}] {content}")
    return "\n".join(lines)


class GroundedGenerationService:
    """Generates grounded answers with inline citations from retrieved evidence.

    Design contract:
    - Every factual sentence MUST have a [N] citation marker.
    - The citation list MUST trace each marker to a specific chunk + document.
    - If is_fully_grounded=False, the caller (Retry/Reflection engine) must flag for review.
    """

    def __init__(self, citation_extractor: CitationExtractor, llm_provider=None):
        self.citation_extractor = citation_extractor
        self.llm_provider = llm_provider

    def generate(self, request: GenerationRequestDTO) -> GroundedAnswerDTO:
        """Generate a grounded answer from evidence chunks.

        If an LLM provider is injected, it will be called for real generation.
        Otherwise, a structured deterministic mock answer is produced for testing.
        """
        start_time = time.perf_counter()
        evidence_chunks = request.evidence_chunks
        if not evidence_chunks:
            logger.warning(
                f"[{request.correlation_id}] No evidence chunks provided for generation"
            )
            return GroundedAnswerDTO(
                answer_text="Insufficient evidence to generate an answer.",
                citations=[],
                is_fully_grounded=False,
                correlation_id=request.correlation_id,
                evidence_used_count=0,
            )

        evidence_block = _build_evidence_block(evidence_chunks)
        model_name = getattr(self.llm_provider, "model_name", "unknown_provider_model")

        with trace_generation(
            model=model_name, prompt_tokens=len(evidence_block.split())
        ):
            if self.llm_provider:
                prompt = _ANSWER_PROMPT_TEMPLATE.format(
                    query=request.query, evidence_block=evidence_block
                )
                answer_text = self.llm_provider.generate(
                    prompt, max_tokens=request.max_answer_tokens
                )
            else:
                # Deterministic mock: use first complete sentence from each evidence chunk
                # so citation markers follow cleanly after each period (no mid-sentence truncation).
                parts = []
                for i, chunk in enumerate(evidence_chunks[:3], start=1):
                    content = chunk.get("content", "")
                    # Extract first complete sentence (up to first '. ')
                    period_pos = content.find(". ")
                    if period_pos > 0:
                        sentence = content[: period_pos + 1]
                    else:
                        sentence = content[:80].strip().rstrip(".") + "."
                    parts.append(f"{sentence} [{i}]")
                answer_text = " ".join(parts) if parts else "Insufficient evidence."

            # Extract citations from answer markers
            citations = self.citation_extractor.extract(answer_text, evidence_chunks)
            is_grounded = self.citation_extractor.check_grounding(
                answer_text, citations, evidence_chunks
            )

            logger.info(
                f"[{request.correlation_id}] Generation complete. "
                f"is_grounded={is_grounded} citations={len(citations)} chunks_used={len(evidence_chunks)}"
            )

            duration = time.perf_counter() - start_time
            record_stage_duration("generation", duration)

            return GroundedAnswerDTO(
                answer_text=answer_text,
                citations=citations,
                is_fully_grounded=is_grounded,
                correlation_id=request.correlation_id,
                evidence_used_count=len(evidence_chunks),
            )
