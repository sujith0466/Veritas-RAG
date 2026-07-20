"""Query Decomposition Strategy — Phase 8.

Breaks complex, multi-part queries into simpler independent sub-queries
for parallel retrieval, improving coverage of compound questions.
"""

import re
from typing import Any

from structlog import get_logger

from backend.modules.query_rewrite.schemas.rewrite_dto import (
    RewriteRequestDTOv2,
    RewriteResultDTO,
    RewriteStrategy,
)
from backend.modules.query_rewrite.strategies.base import BaseRewriteStrategy

logger = get_logger(__name__)

_COMPLEXITY_PATTERNS = [
    r"\band\b.+\?",
    r"\bcompare\b",
    r"\bdifference between\b",
    r"\bvs\.?\b",
    r"\bboth\b.+\band\b",
]
_WORD_COUNT_THRESHOLD = 20
_MULTI_QUESTION_RE = re.compile(r"\?")


class QueryDecompositionStrategy(BaseRewriteStrategy):
    """Decomposes complex queries into simpler, independently retrievable sub-queries."""

    def __init__(self, llm_provider: Any = None, timeout_ms: int = 3000) -> None:
        self.llm_provider = llm_provider
        self.timeout_ms = timeout_ms

    def get_strategy_name(self) -> RewriteStrategy:
        return RewriteStrategy.DECOMPOSITION

    def rewrite(self, request: RewriteRequestDTOv2) -> RewriteResultDTO:
        query = request.original_query
        is_complex = self._detect_complexity(query)

        if not is_complex:
            return RewriteResultDTO(
                original_query=query,
                rewritten_query=query,
                strategy=RewriteStrategy.DECOMPOSITION,
                rationale="Query is simple — no decomposition needed.",
                sub_queries=[query],
                confidence_improvement_estimate=0.0,
            )

        sub_queries = self._decompose(query)
        return RewriteResultDTO(
            original_query=query,
            rewritten_query=" | ".join(sub_queries),
            strategy=RewriteStrategy.DECOMPOSITION,
            rationale=f"Decomposed into {len(sub_queries)} independent sub-queries.",
            sub_queries=sub_queries,
            confidence_improvement_estimate=0.20,
        )

    def _detect_complexity(self, query: str) -> bool:
        if len(query.split()) > _WORD_COUNT_THRESHOLD:
            return True
        if len(_MULTI_QUESTION_RE.findall(query)) > 1:
            return True
        for pattern in _COMPLEXITY_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return True
        return False

    def _decompose(self, query: str) -> list[str]:
        if self.llm_provider:
            try:
                result = self._llm_decompose(query)
                if result and len(result) >= 2:
                    return result
            except Exception as exc:
                logger.warning("LLM decomposition failed, using heuristics", error=str(exc))
        return self._heuristic_decompose(query)

    def _llm_decompose(self, query: str) -> list[str]:
        import json
        prompt = (
            f"Decompose this question into 2-3 independent simpler questions. "
            f"Return ONLY a JSON array of strings.\nQuestion: {query}"
        )
        raw = self.llm_provider.generate(prompt, max_tokens=200)
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        return []

    def _heuristic_decompose(self, query: str) -> list[str]:
        and_split = re.split(r"\s+and\s+", query, flags=re.IGNORECASE)
        if len(and_split) > 1:
            return [p.strip().rstrip("?") + "?" for p in and_split if p.strip()]
        q_split = [p.strip() for p in query.split("?") if p.strip()]
        return [p + "?" for p in q_split] if q_split else [query]

# ---------------------------------------------------------------------------
# Phase 3 backward-compatible class
# ---------------------------------------------------------------------------
from backend.modules.query_rewrite.schemas.rewrite_dto import DecomposedQueriesDTO

class DecompositionRewriter:
    """Phase 3 backward-compatible DecompositionRewriter."""

    def __init__(self, llm_provider: Any = None) -> None:
        self.strategy = QueryDecompositionStrategy(llm_provider=llm_provider)

    def decompose(self, query: str) -> DecomposedQueriesDTO:
        is_complex = self.strategy._detect_complexity(query)
        if not is_complex:
            return DecomposedQueriesDTO(
                original_query=query,
                sub_queries=[query],
                is_complex=False,
            )
        sub_queries = self.strategy._decompose(query)
        return DecomposedQueriesDTO(
            original_query=query,
            sub_queries=sub_queries,
            is_complex=True,
        )
