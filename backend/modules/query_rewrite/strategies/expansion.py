"""Query Expansion Strategy — Phase 8.

Expands query terms with synonyms, acronym resolution, and domain-specific terminology
to increase token-level recall during BM25 sparse retrieval.
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

# Built-in synonym dictionary (domain-agnostic core terms)
_SYNONYM_DICT: dict[str, list[str]] = {
    "increase": ["rise", "grow", "expand", "escalate"],
    "decrease": ["fall", "drop", "decline", "reduce"],
    "policy": ["regulation", "rule", "guideline", "procedure"],
    "contract": ["agreement", "deal", "arrangement", "accord"],
    "revenue": ["income", "earnings", "sales", "turnover"],
    "employee": ["staff", "worker", "personnel", "team member"],
    "customer": ["client", "user", "consumer", "patron"],
    "document": ["file", "record", "report", "paper"],
    "approve": ["authorize", "sanction", "ratify", "endorse"],
    "reject": ["deny", "refuse", "decline", "dismiss"],
    "require": ["need", "mandate", "demand", "necessitate"],
    "define": ["specify", "describe", "establish", "outline"],
}

# Acronym registry
_ACRONYM_DICT: dict[str, str] = {
    "ML": "Machine Learning",
    "AI": "Artificial Intelligence",
    "NLP": "Natural Language Processing",
    "RAG": "Retrieval Augmented Generation",
    "API": "Application Programming Interface",
    "SLA": "Service Level Agreement",
    "KPI": "Key Performance Indicator",
    "HR": "Human Resources",
    "IP": "Intellectual Property",
    "MOU": "Memorandum of Understanding",
    "NDA": "Non-Disclosure Agreement",
    "SOP": "Standard Operating Procedure",
    "ROI": "Return on Investment",
    "CFO": "Chief Financial Officer",
    "CEO": "Chief Executive Officer",
    "CTO": "Chief Technology Officer",
}


class QueryExpansionStrategy(BaseRewriteStrategy):
    """Expands query using synonyms, acronyms, and domain-specific terms."""

    def __init__(
        self,
        extra_synonyms: dict[str, list[str]] | None = None,
        extra_acronyms: dict[str, str] | None = None,
    ) -> None:
        self.synonyms = {**_SYNONYM_DICT, **(extra_synonyms or {})}
        self.acronyms = {**_ACRONYM_DICT, **(extra_acronyms or {})}

    def get_strategy_name(self) -> RewriteStrategy:
        return RewriteStrategy.EXPANSION

    def rewrite(self, request: RewriteRequestDTOv2) -> RewriteResultDTO:
        tokens = self._tokenize(request.original_query)
        expanded_terms: list[str] = []
        expanded_parts: list[str] = []

        for token in tokens:
            parts = [token]
            # Acronym expansion
            acronym_exp = self._acronym_expand(token)
            if acronym_exp:
                parts.append(acronym_exp)
                expanded_terms.append(acronym_exp)
            # Synonym expansion
            syns = self._synonym_lookup(token)
            if syns:
                parts.extend(syns[:2])
                expanded_terms.extend(syns[:2])
            if len(parts) > 1:
                expanded_parts.append(f"({' OR '.join(parts)})")
            else:
                expanded_parts.append(token)

        expanded_query = " ".join(expanded_parts)

        return RewriteResultDTO(
            original_query=request.original_query,
            rewritten_query=expanded_query,
            strategy=RewriteStrategy.EXPANSION,
            rationale="Term expansion adds synonyms and acronym expansions to improve BM25 recall.",
            expanded_terms=expanded_terms,
            confidence_improvement_estimate=0.10,
        )

    def _tokenize(self, query: str) -> list[str]:
        return re.findall(r"\b\w+\b", query)

    def _synonym_lookup(self, term: str) -> list[str]:
        return self.synonyms.get(term.lower(), [])

    def _acronym_expand(self, term: str) -> str | None:
        return self.acronyms.get(term.upper())
