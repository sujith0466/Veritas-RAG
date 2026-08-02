"""Strategy Selector — Phase 8.

Routes queries to the optimal rewrite strategy based on confidence signals
from ConfidenceResultDTOv2 or explicit hints from Phase 7 RetryDecision.
"""

from structlog import get_logger

from backend.modules.query_rewrite.schemas.rewrite_dto import RewriteRequestDTOv2, RewriteStrategy
from backend.modules.query_rewrite.strategies.base import BaseRewriteStrategy

logger = get_logger(__name__)


class StrategySelector:
    """Selects the best BaseRewriteStrategy based on request signals."""

    def __init__(self, strategies: dict[RewriteStrategy, BaseRewriteStrategy]) -> None:
        self.strategies = strategies

    def select(self, request: RewriteRequestDTOv2) -> BaseRewriteStrategy:
        """Return the appropriate strategy instance."""
        # 1. Explicit hint override (if not AUTO)
        if request.strategy_hint and request.strategy_hint != RewriteStrategy.AUTO:
            if request.strategy_hint in self.strategies:
                logger.info("Selecting strategy from hint", hint=request.strategy_hint)
                return self.strategies[request.strategy_hint]
            logger.warning(
                "Requested strategy hint not registered, falling back to signal routing",
                hint=request.strategy_hint,
            )

        # 2. Signal-based routing from ConfidenceResult / request context
        # Check for pronoun / co-reference indicators first
        query_lower = request.original_query.lower()
        pronouns = {"it", "its", "they", "them", "this", "he", "she", "these", "those"}
        tokens = set(query_lower.split())
        if (
            tokens & pronouns or "the above" in query_lower
        ) and request.conversation_history:
            if RewriteStrategy.ENTITY_RECOVERY in self.strategies:
                logger.info(
                    "Selecting ENTITY_RECOVERY based on pronoun/reference detection"
                )
                return self.strategies[RewriteStrategy.ENTITY_RECOVERY]

        # Check for complex/multi-part query signals
        if (
            len(query_lower.split()) > 20
            or "?" in query_lower[:-1]
            or " and " in query_lower
            or "compare" in query_lower
        ):
            if RewriteStrategy.DECOMPOSITION in self.strategies:
                logger.info("Selecting DECOMPOSITION based on query complexity")
                return self.strategies[RewriteStrategy.DECOMPOSITION]

        # Check for specific uncovered clauses / low term coverage
        if request.uncovered_clauses or (
            request.coverage_score is not None and 0.2 < request.coverage_score < 0.6
        ):
            if RewriteStrategy.EXPANSION in self.strategies:
                logger.info(
                    "Selecting EXPANSION based on uncovered clauses / partial coverage"
                )
                return self.strategies[RewriteStrategy.EXPANSION]

        # Default fallback: HyDE (semantic breadth for low/unknown coverage)
        if RewriteStrategy.HYDE in self.strategies:
            logger.info("Selecting HYDE as default semantic breadth strategy")
            return self.strategies[RewriteStrategy.HYDE]

        # Ultimate fallback if registered map is incomplete
        first_strategy = next(iter(self.strategies.values()), None)
        if not first_strategy:
            raise RuntimeError("No rewrite strategies registered in StrategySelector.")
        return first_strategy
