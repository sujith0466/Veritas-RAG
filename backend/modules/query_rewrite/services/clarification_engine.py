import logging
from backend.modules.query_rewrite.schemas.rewrite_dto import (
    RewriteRequestDTO,
    DecomposedQueriesDTO,
    HyDEResponseDTO,
    ClarificationQuestionDTO
)
from backend.modules.query_rewrite.strategies.decomposition import DecompositionRewriter
from backend.modules.query_rewrite.strategies.hyde import HyDERewriter
from backend.modules.query_rewrite.strategies.disambiguation import DisambiguationRewriter

logger = logging.getLogger(__name__)


class ClarificationEngine:
    """Orchestrates query rewrite strategies to resolve ambiguity and optimize retrieval."""

    def __init__(
        self,
        decomposition: DecompositionRewriter,
        hyde: HyDERewriter,
        disambiguation: DisambiguationRewriter
    ):
        self.decomposition = decomposition
        self.hyde = hyde
        self.disambiguation = disambiguation

    def rewrite_query(self, request: RewriteRequestDTO) -> dict:
        """Apply rewrite strategies and return a comprehensive rewrite package."""
        logger.info(f"ClarificationEngine processing query: {request.original_query}")
        
        # 1. Disambiguation Check
        clarification = self.disambiguation.generate_clarification(request.original_query)
        if clarification:
            logger.info("Query flagged as ambiguous; clarification required.")
            return {
                "status": "CLARIFICATION_REQUIRED",
                "clarification": clarification
            }

        # 2. Decomposition
        decomposed = self.decomposition.decompose(request.original_query)
        
        # 3. HyDE (Hypothetical Document Embeddings)
        # For multi-hop, we might do HyDE on each, but for this baseline we do it on the original
        hyde_resp = self.hyde.rewrite(request.original_query)

        return {
            "status": "REWRITTEN",
            "decomposed": decomposed,
            "hyde": hyde_resp
        }
