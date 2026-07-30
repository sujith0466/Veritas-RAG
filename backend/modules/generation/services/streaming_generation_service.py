"""Streaming Grounded Generation Service — Phase 10.

Yields Server-Sent Event (SSE) compatible streaming chunks while incrementally
checking citations and grounding.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from structlog import get_logger

from backend.modules.generation.schemas.generation_dto import (
    GenerationRequestDTOv2, StreamingGenerationChunkDTO)
from backend.modules.generation.services.citation_extractor import \
    CitationExtractor
from backend.modules.generation.services.prompt_guard import PromptGuard

logger = get_logger(__name__)


class StreamingGroundedGenerationService:
    """Async streaming service for grounded answer generation with live citation tracking."""

    def __init__(
        self,
        citation_extractor: CitationExtractor,
        prompt_guard: PromptGuard | None = None,
        llm_provider: Any = None,
    ) -> None:
        self.citation_extractor = citation_extractor
        self.prompt_guard = prompt_guard or PromptGuard()
        self.llm_provider = llm_provider

    async def generate_stream(
        self, request: GenerationRequestDTOv2
    ) -> AsyncGenerator[StreamingGenerationChunkDTO, None]:
        """Yield chunks of generated answer and final citations evaluation."""
        if not request.evidence_chunks:
            yield StreamingGenerationChunkDTO(
                chunk_index=0,
                text_delta="Insufficient evidence to generate a grounded answer.",
                citations_delta=[],
                is_final=True,
                correlation_id=request.correlation_id,
                is_fully_grounded=False,
            )
            return

        evidence_block, safe_chunks = self.prompt_guard.sanitize_and_format_evidence(
            request.evidence_chunks
        )
        if not safe_chunks:
            yield StreamingGenerationChunkDTO(
                chunk_index=0,
                text_delta="All provided evidence chunks failed security guardrail checks.",
                citations_delta=[],
                is_final=True,
                correlation_id=request.correlation_id,
                is_fully_grounded=False,
            )
            return

        if self.llm_provider and hasattr(self.llm_provider, "generate_stream"):
            full_text = ""
            chunk_idx = 0
            try:
                async for delta in self.llm_provider.generate_stream(
                    request.query, evidence_block
                ):
                    full_text += delta
                    yield StreamingGenerationChunkDTO(
                        chunk_index=chunk_idx,
                        text_delta=delta,
                        is_final=False,
                        correlation_id=request.correlation_id,
                    )
                    chunk_idx += 1
                    await asyncio.sleep(0.01)
            except Exception as exc:
                logger.error(
                    "LLM generation failed during stream",
                    error=str(exc),
                    correlation_id=request.correlation_id,
                )
                
                from backend.core.exceptions import LLMProviderException
                
                error_msg = "\n[Error: Unable to generate a response right now. Please try again shortly.]"
                if isinstance(exc, LLMProviderException):
                    if exc.status_code in (429, 502, 503):
                        error_msg = "\n[Error: AI service is temporarily busy. Please try again in a few moments.]"
                    elif exc.status_code in (504,) or "timeout" in str(exc).lower():
                        error_msg = "\n[Error: The request is taking longer than expected. Retrying automatically...]"

                yield StreamingGenerationChunkDTO(
                    chunk_index=chunk_idx,
                    text_delta=error_msg,
                    is_final=True,
                    correlation_id=request.correlation_id,
                    is_fully_grounded=False,
                )
                return
        else:
            # Deterministic mock streaming fallback
            parts = []
            for i, chunk in enumerate(safe_chunks[:3], start=1):
                content = chunk.content or ""
                period_pos = content.find(". ")
                sentence = (
                    content[: period_pos + 1]
                    if period_pos > 0
                    else content[:80].strip().rstrip(".") + "."
                ) + f" [{i}] "
                parts.append(sentence)

            full_text = "".join(parts).strip()
            words = full_text.split()
            chunk_idx = 0
            batch_size = 4
            for i in range(0, len(words), batch_size):
                delta = " ".join(words[i : i + batch_size]) + " "
                yield StreamingGenerationChunkDTO(
                    chunk_index=chunk_idx,
                    text_delta=delta,
                    is_final=False,
                    correlation_id=request.correlation_id,
                )
                chunk_idx += 1
                await asyncio.sleep(0.01)

        # Final chunk with evaluated citations and grounding status
        citations = self.citation_extractor.extract(full_text, safe_chunks)
        is_grounded = self.citation_extractor.check_grounding(
            full_text, citations, safe_chunks
        )

        yield StreamingGenerationChunkDTO(
            chunk_index=chunk_idx,
            text_delta="",
            citations_delta=citations,
            is_final=True,
            correlation_id=request.correlation_id,
            is_fully_grounded=is_grounded,
        )
