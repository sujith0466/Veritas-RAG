"""Rewrite Orchestrator — Phase 8.

Coordinates strategy selection, execution, and audit logging.
Acts as the main entry point for Phase 8 query rewriting.
"""

from typing import Any

from structlog import get_logger

from backend.modules.query_rewrite.schemas.rewrite_dto import (
    RewriteRequestDTOv2,
    RewriteResultDTO,
    RewriteStrategy,
)
from backend.modules.query_rewrite.services.strategy_selector import StrategySelector
from backend.modules.query_rewrite.strategies.decomposition import QueryDecompositionStrategy
from backend.modules.query_rewrite.strategies.entity_recovery import MissingEntityRecoveryStrategy
from backend.modules.query_rewrite.strategies.expansion import QueryExpansionStrategy
from backend.modules.query_rewrite.strategies.hyde import HyDEStrategy

logger = get_logger(__name__)


class RewriteOrchestrator:
    """Orchestrates multi-strategy query rewriting and maintains history."""

    def __init__(
        self,
        strategy_selector: StrategySelector | None = None,
        llm_provider: Any = None,
    ) -> None:
        if not strategy_selector:
            strategies = {
                RewriteStrategy.HYDE: HyDEStrategy(llm_provider=llm_provider),
                RewriteStrategy.EXPANSION: QueryExpansionStrategy(),
                RewriteStrategy.DECOMPOSITION: QueryDecompositionStrategy(
                    llm_provider=llm_provider
                ),
                RewriteStrategy.ENTITY_RECOVERY: MissingEntityRecoveryStrategy(
                    llm_provider=llm_provider
                ),
            }
            self.strategy_selector = StrategySelector(strategies)
        else:
            self.strategy_selector = strategy_selector

        # In-memory audit trail of rewrites (query_id -> list[RewriteResultDTO])
        self._audit_log: list[RewriteResultDTO] = []

    def rewrite(self, request: RewriteRequestDTOv2) -> RewriteResultDTO:
        """Select optimal strategy and rewrite query."""
        logger.info(
            "RewriteOrchestrator processing rewrite request",
            query=request.original_query,
            hint=request.strategy_hint,
        )
        strategy = self.strategy_selector.select(request)

        result = strategy.rewrite(request)
        self._audit_log.append(result)
        logger.info(
            "Rewrite complete",
            strategy=result.strategy,
            rewritten=result.rewritten_query,
        )
        return result

    def get_history(self, limit: int = 50) -> list[RewriteResultDTO]:
        """Return recent rewrite audit logs."""
        return self._audit_log[-limit:]

    def get_available_strategies(self) -> list[str]:
        """Return list of registered strategy names."""
        return [s.value for s in self.strategy_selector.strategies.keys()]
