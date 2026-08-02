"""Missing Entity Recovery Strategy — Phase 8.

Resolves pronoun references (it, they, this, he, she) and implicit entity
references by leveraging conversation history or LLM co-reference resolution.
"""

import re
from typing import Any

from structlog import get_logger

from backend.modules.query_rewrite.schemas.rewrite_dto import (
    EntityResolutionDTO,
    RewriteRequestDTOv2,
    RewriteResultDTO,
    RewriteStrategy,
)
from backend.modules.query_rewrite.strategies.base import BaseRewriteStrategy

logger = get_logger(__name__)

_PRONOUNS = {
    "it",
    "its",
    "they",
    "them",
    "their",
    "this",
    "that",
    "these",
    "those",
    "he",
    "she",
    "him",
    "her",
}
_IMPLICIT_REFS = {
    "the policy",
    "the contract",
    "the document",
    "the above",
    "the agreement",
    "the report",
}


class MissingEntityRecoveryStrategy(BaseRewriteStrategy):
    """Resolves ambiguous pronouns and implicit entity references."""

    def __init__(self, llm_provider: Any = None, timeout_ms: int = 2000) -> None:
        self.llm_provider = llm_provider
        self.timeout_ms = timeout_ms

    def get_strategy_name(self) -> RewriteStrategy:
        return RewriteStrategy.ENTITY_RECOVERY

    def rewrite(self, request: RewriteRequestDTOv2) -> RewriteResultDTO:
        query = request.original_query
        detected_pronouns = self._detect_pronouns(query)
        implicit_refs = self._detect_implicit_references(query)

        if not detected_pronouns and not implicit_refs:
            return RewriteResultDTO(
                original_query=query,
                rewritten_query=query,
                strategy=RewriteStrategy.ENTITY_RECOVERY,
                rationale="No pronouns or implicit references detected.",
                confidence_improvement_estimate=0.0,
            )

        resolved_query = query
        resolutions: list[EntityResolutionDTO] = []

        # Resolve from conversation history first
        for pronoun in detected_pronouns:
            entity = self._resolve_from_context(pronoun, request.conversation_history)
            if entity:
                resolved_query = re.sub(
                    rf"\b{re.escape(pronoun)}\b",
                    entity,
                    resolved_query,
                    flags=re.IGNORECASE,
                )
                resolutions.append(
                    EntityResolutionDTO(
                        pronoun=pronoun, resolved_entity=entity, is_resolved=True
                    )
                )
            else:
                resolutions.append(
                    EntityResolutionDTO(
                        pronoun=pronoun,
                        resolved_entity="[UNRESOLVED]",
                        is_resolved=False,
                    )
                )

        return RewriteResultDTO(
            original_query=query,
            rewritten_query=resolved_query,
            strategy=RewriteStrategy.ENTITY_RECOVERY,
            rationale=f"Resolved {len([r for r in resolutions if r.is_resolved])} of {len(resolutions)} pronouns.",
            resolved_entities=resolutions,
            confidence_improvement_estimate=(
                0.12 if any(r.is_resolved for r in resolutions) else 0.0
            ),
        )

    def _detect_pronouns(self, query: str) -> list[str]:
        tokens = set(re.findall(r"\b\w+\b", query.lower()))
        return list(tokens & _PRONOUNS)

    def _detect_implicit_references(self, query: str) -> list[str]:
        query_lower = query.lower()
        return [ref for ref in _IMPLICIT_REFS if ref in query_lower]

    def _resolve_from_context(self, pronoun: str, history: list[str]) -> str | None:
        """Extract most recent noun phrase from conversation history."""
        if not history:
            return None
        # Simple heuristic: look for capitalized noun phrases in the last 2 turns
        noun_re = re.compile(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b")
        for turn in reversed(history[-2:]):
            match = noun_re.search(turn)
            if match:
                return match.group(1)
        return None
