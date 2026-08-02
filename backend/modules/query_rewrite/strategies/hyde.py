"""HyDE (Hypothetical Document Embeddings) Strategy — Phase 8 production version.

Generates a hypothetical answer document to use as a dense retrieval query,
improving semantic coverage for low-coverage queries.
"""

from typing import Any

from structlog import get_logger

from backend.modules.query_rewrite.schemas.rewrite_dto import (
    RewriteRequestDTOv2,
    RewriteResultDTO,
    RewriteStrategy,
)
from backend.modules.query_rewrite.strategies.base import BaseRewriteStrategy

logger = get_logger(__name__)

_HYDE_PROMPT_TEMPLATE = (
    "Generate a short factual document that would answer the following question. "
    "Use formal, factual language. 2-3 sentences maximum. "
    "Do not start with 'I' or 'This document'.\n\n"
    "Question: {query}\n\n"
    "Factual document:"
)


class HyDEStrategy(BaseRewriteStrategy):
    """HyDE: use a hypothetical answer document as the retrieval embedding."""

    def __init__(self, llm_provider: Any = None, timeout_ms: int = 2000) -> None:
        self.llm_provider = llm_provider
        self.timeout_ms = timeout_ms

    def get_strategy_name(self) -> RewriteStrategy:
        return RewriteStrategy.HYDE

    def rewrite(self, request: RewriteRequestDTOv2) -> RewriteResultDTO:
        hypothetical_doc = self._generate_hypothetical_doc(request.original_query)
        embedding_query = f"{request.original_query}\n\n{hypothetical_doc}"

        return RewriteResultDTO(
            original_query=request.original_query,
            rewritten_query=embedding_query,
            strategy=RewriteStrategy.HYDE,
            rationale="HyDE: hypothetical document improves dense retrieval coverage.",
            hypothetical_document=hypothetical_doc,
            confidence_improvement_estimate=0.15,
        )

    def _generate_hypothetical_doc(self, query: str) -> str:
        """Generate via LLM or fall back to template synthesis."""
        if self.llm_provider:
            try:
                prompt = _HYDE_PROMPT_TEMPLATE.format(query=query)
                result = self.llm_provider.generate(prompt, max_tokens=150)
                if result and len(result.strip()) > 10:
                    return result.strip()
            except Exception as exc:
                logger.warning(
                    "HyDE LLM generation failed, using template fallback",
                    error=str(exc),
                )
        return self._template_synthesis_fallback(query)

    def _template_synthesis_fallback(self, query: str) -> str:
        """Heuristic fallback when LLM is unavailable."""
        # Strip question words to form declarative form
        clean = query.strip().rstrip("?")
        for prefix in (
            "what is",
            "what are",
            "how does",
            "how do",
            "why does",
            "explain",
        ):
            if clean.lower().startswith(prefix):
                clean = clean[len(prefix) :].strip()
                break
        return (
            f"This is a hypothetical technical explanation regarding {query}. "
            f"It discusses the core concepts, mechanisms, and examples of {clean} in detail."
        )


# Phase 3 backward-compatible alias
class HyDERewriter(HyDEStrategy):
    """Backward-compatible alias for Phase 3 HyDERewriter."""

    def rewrite(self, query: str) -> object:  # type: ignore[override]
        from backend.modules.query_rewrite.schemas.rewrite_dto import HyDEResponseDTO

        doc = self._generate_hypothetical_doc(query)
        return HyDEResponseDTO(
            original_query=query,
            hypothetical_document=doc,
            embedding_query=f"{query}\n\n{doc}",
        )
