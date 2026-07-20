import re
from backend.modules.generation.schemas.generation_dto import CitationDTO
from backend.modules.reflection.schemas.reflection_dto import ClaimValidationResultDTO, ClaimVerdict


class ClaimValidator:
    """Validates each claim in an answer against its cited evidence excerpts.

    For the M5 baseline this uses heuristic token-overlap NLI.
    In a production system, this calls a cross-encoder or NLI model.
    """

    def __init__(self, support_threshold: float = 0.3, contradiction_threshold: float = 0.15):
        # Minimum token overlap ratio to consider a claim SUPPORTED by an excerpt
        self.support_threshold = support_threshold
        # Maximum overlap ratio below which a claim with opposing numerics is CONTRADICTED
        self.contradiction_threshold = contradiction_threshold

    def _tokenize(self, text: str) -> set[str]:
        """Lowercase word tokenizer stripping stopwords."""
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "it", "its", "of", "in",
                     "on", "at", "to", "and", "or", "but", "not", "for", "with", "by", "from"}
        return {w for w in re.findall(r'\b\w+\b', text.lower()) if w not in stopwords}

    def _overlap_ratio(self, claim_tokens: set[str], excerpt_tokens: set[str]) -> float:
        if not claim_tokens:
            return 0.0
        return len(claim_tokens.intersection(excerpt_tokens)) / len(claim_tokens)

    def _extract_numbers(self, text: str) -> set[str]:
        return set(re.findall(r'\b\d+(?:[.,]\d+)?\b', text))

    def validate_claim(
        self,
        claim_text: str,
        citation_index: int | None,
        citations: list[CitationDTO]
    ) -> ClaimValidationResultDTO:
        """Validate a single claim against its referenced citation."""
        if not citations or citation_index is None:
            return ClaimValidationResultDTO(
                claim_text=claim_text,
                verdict=ClaimVerdict.UNSUPPORTED,
                citation_index=None,
                supporting_excerpt=None
            )

        # Find the referenced citation (1-indexed)
        citation = next((c for c in citations if c.citation_index == citation_index), None)
        if not citation:
            return ClaimValidationResultDTO(
                claim_text=claim_text,
                verdict=ClaimVerdict.UNSUPPORTED,
                citation_index=citation_index,
                supporting_excerpt=None
            )

        claim_tokens = self._tokenize(claim_text)
        excerpt_tokens = self._tokenize(citation.excerpt)
        overlap = self._overlap_ratio(claim_tokens, excerpt_tokens)

        # Check for numeric contradiction
        claim_nums = self._extract_numbers(claim_text)
        excerpt_nums = self._extract_numbers(citation.excerpt)

        # Numbers exclusive to each side (shared numbers like years don't indicate conflict)
        claim_only_nums = claim_nums - excerpt_nums
        excerpt_only_nums = excerpt_nums - claim_nums

        # Non-numeric tokens for context similarity check
        num_pattern = re.compile(r'^\d')
        non_num_claim = {t for t in claim_tokens if not num_pattern.match(t)}
        non_num_excerpt = {t for t in excerpt_tokens if not num_pattern.match(t)}
        non_num_overlap = self._overlap_ratio(non_num_claim, non_num_excerpt)

        # Conflict = both sides have exclusive numbers AND they're discussing the same topic
        has_numeric_conflict = (
            bool(claim_only_nums) and bool(excerpt_only_nums) and non_num_overlap >= 0.4
        )

        # Numeric conflict is a hard signal: the key fact is wrong.
        if has_numeric_conflict:
            verdict = ClaimVerdict.CONTRADICTED
        elif overlap >= self.support_threshold:
            verdict = ClaimVerdict.SUPPORTED
        else:
            verdict = ClaimVerdict.UNSUPPORTED

        return ClaimValidationResultDTO(
            claim_text=claim_text,
            verdict=verdict,
            citation_index=citation_index,
            supporting_excerpt=citation.excerpt
        )
