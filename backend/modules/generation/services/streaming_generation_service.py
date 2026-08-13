"""Streaming Grounded Generation Service — Phase 10.

Yields Server-Sent Event (SSE) compatible streaming chunks while incrementally
checking citations and grounding.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from structlog import get_logger

from backend.modules.generation.schemas.generation_dto import (
    GenerationRequestDTOv2,
    StreamingGenerationChunkDTO,
)
from backend.modules.generation.services.citation_extractor import CitationExtractor
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

        from backend.core.config import get_settings
        settings = get_settings()
        enable_citations = settings.features.enable_streaming_citations
        enable_reliability = settings.features.enable_streaming_reliability

        window_buffer = ""
        reliability_engine = None
        if enable_reliability:
            from backend.modules.reliability.services.reliability_engine import ReliabilityEngine
            reliability_engine = ReliabilityEngine()

        reliability_version = 0
        sentence_count = 0
        update_interval = 2 # Configurable update interval

        import re
        citation_pattern = re.compile(r'\[(\d+)\]')
        sentence_pattern = re.compile(r'[.!?]\s')

        if self.llm_provider and hasattr(self.llm_provider, "generate_stream"):
            full_text = ""
            chunk_idx = 0
            try:
                async for delta in self.llm_provider.generate_stream(
                    request.query, evidence_block
                ):
                    full_text += delta
                    window_buffer += delta

                    citations_delta = []
                    metadata = None

                    # F8.8 Progressive Citation Extraction
                    if enable_citations:
                        markers = citation_pattern.findall(window_buffer)
                        for marker_str in markers:
                            marker = int(marker_str)
                            cit = self.citation_extractor.extract_single(marker, safe_chunks)
                            if cit:
                                citations_delta.append(cit)
                        # Clear buffer up to last marker to avoid rescanning
                        if markers:
                            last_match = list(citation_pattern.finditer(window_buffer))[-1]
                            window_buffer = window_buffer[last_match.end():]

                    # F8.7 Reliability Score Extraction
                    if enable_reliability and reliability_engine and sentence_pattern.search(delta):
                        sentence_count += 1
                        if sentence_count >= update_interval:
                                # In a real implementation this would be asyncio.create_task and a callback
                                # to not block the stream. Here we simulate it async.
                                score = await reliability_engine.evaluate_incremental(window_buffer, safe_chunks)
                                reliability_version += 1
                                metadata = {
                                    "reliability_score_update": score,
                                    "reliability_version": reliability_version
                                }
                                sentence_count = 0
                                window_buffer = "" # Reset for next sentence

                    yield StreamingGenerationChunkDTO(
                        chunk_index=chunk_idx,
                        text_delta=delta,
                        citations_delta=citations_delta,
                        is_final=False,
                        correlation_id=request.correlation_id,
                        wrapper_metadata=metadata
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
            from backend.core.exceptions import ApplicationException
            raise ApplicationException(
                "No LLM provider configured. Deterministic mock generation is disabled in production.",
                status_code=500
            )

        # Final chunk with evaluated citations and grounding status
        citations = self.citation_extractor.extract(full_text, safe_chunks)
        is_grounded = self.citation_extractor.check_grounding(
            full_text, citations, safe_chunks
        )

        final_metadata = None
        if enable_reliability and reliability_engine:
            final_metadata = {
                "reliability_score": reliability_engine.current_score
            }

        yield StreamingGenerationChunkDTO(
            chunk_index=chunk_idx,
            text_delta="",
            citations_delta=citations,
            is_final=True,
            correlation_id=request.correlation_id,
            is_fully_grounded=is_grounded,
            wrapper_metadata=final_metadata
        )
