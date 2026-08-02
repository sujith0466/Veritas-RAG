import re

from typing import Any

from backend.modules.generation.schemas.generation_dto import CitationDTO
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "uses",
    "use",
    "using",
    "with",
}


class CitationExtractor:
    """Extracts and builds citation objects from inline citation markers in generated text.

    Expects generated text to contain markers like [1], [2], and a reference map
    that associates each index to a source chunk.
    """

    def extract(
        self, answer_text: str, evidence_chunks: list[RankedEvidenceDTO]
    ) -> list[CitationDTO]:
        """Build an ordered CitationDTO list from the answer's inline markers.

        Args:
            answer_text: The generated answer containing [N] citation markers.
            evidence_chunks: Ordered list of canonical evidence chunk objects.

        Returns:
            An ordered list of CitationDTO objects (1-indexed to match [N] markers).
        """
        # Find all unique citation indices referenced in the answer
        marker_pattern = re.compile(r"\[(\d+)\]")
        found_indices = sorted(set(int(m) for m in marker_pattern.findall(answer_text)))

        citations = []
        for idx in found_indices:
            # Citation markers are 1-based; evidence_chunks is 0-based
            chunk_pos = idx - 1
            if chunk_pos < 0 or chunk_pos >= len(evidence_chunks):
                continue

            chunk = evidence_chunks[chunk_pos]
            # Use first 200 chars of content as the supporting excerpt
            excerpt = (chunk.content if hasattr(chunk, "content") else chunk.get("content", ""))[:200].strip()

            metadata = chunk.metadata if hasattr(chunk, "metadata") else chunk.get("metadata", {})
            source_name = metadata.get("source_name") or metadata.get("filename")
            document_name = metadata.get("document_name")

            citations.append(
                CitationDTO(
                    citation_index=idx,
                    chunk_id=str((chunk.chunk_id if hasattr(chunk, "chunk_id") else chunk.get("chunk_id", ""))),
                    document_id=str(chunk.document_id if hasattr(chunk, "document_id") else chunk.get("document_id", "")),
                    source_name=source_name,
                    document_name=document_name,
                    excerpt=excerpt,
                    relevance_score=(chunk.normalized_relevance_score if hasattr(chunk, "normalized_relevance_score") and chunk.normalized_relevance_score is not None else chunk.get("normalized_relevance_score", 1.0) if not hasattr(chunk, "normalized_relevance_score") else 1.0),
                )
            )

        return citations

    def check_grounding(
        self,
        answer_text: str,
        citations: list[CitationDTO],
        evidence_chunks: list[RankedEvidenceDTO] | None = None,
    ) -> bool:
        """Return True if every meaningful sentence in the answer is followed by or contains
        at least one citation marker [N].

        Strategy: extract "claim units" as sentence + optional trailing citation(s).
        A sentence that has no marker attached (inline or trailing) is flagged as
        ungrounded. When evidence chunks are provided, each citation must also
        map to non-empty evidence that supports the cited claim.
        """
        # Match a sentence (ending with . ! ?) optionally followed by [N] markers
        # This handles both "claim. [1]" and "claim [1]." styles
        claim_pattern = re.compile(
            r"([A-Z0-9][^.!?]*[.!?])\s*(\[\d+\](?:\s*\[\d+\])*)?", re.IGNORECASE | re.DOTALL
        )
        marker_pattern = re.compile(r"\[(\d+)\]")

        if not citations:
            if evidence_chunks is not None and marker_pattern.search(answer_text):
                return False
            return len(answer_text.split()) <= 5

        matches = claim_pattern.findall(answer_text)
        if not matches:
            # Couldn't parse sentences — fall back to checking total marker count
            return len(marker_pattern.findall(answer_text)) > 0

        for sentence, trailing_markers in matches:
            words = sentence.split()
            if len(words) <= 2:
                continue  # Skip very short connective clauses

            marker_text = f"{sentence} {trailing_markers or ''}"
            marker_indices = [int(m) for m in marker_pattern.findall(marker_text)]
            if marker_indices and (
                evidence_chunks is None
                or self._citations_supported_by_evidence(
                    sentence, marker_indices, citations, evidence_chunks
                )
            ):
                continue  # This sentence is cited

            return False  # Found a meaningful uncited sentence

        return True

    def _citations_supported_by_evidence(
        self,
        sentence: str,
        marker_indices: list[int],
        citations: list[CitationDTO],
        evidence_chunks: list[RankedEvidenceDTO],
    ) -> bool:
        citation_indices = {citation.citation_index for citation in citations}
        has_supporting_evidence = False

        for idx in marker_indices:
            if idx not in citation_indices:
                return False
            chunk_pos = idx - 1
            if chunk_pos < 0 or chunk_pos >= len(evidence_chunks):
                return False

            chunk_item = evidence_chunks[chunk_pos]
            content = chunk_item.content if hasattr(chunk_item, "content") else chunk_item.get("content", "")
            if not str(content).strip():
                return False
            if self._evidence_supports_claim(sentence, str(content)):
                has_supporting_evidence = True

        return has_supporting_evidence

    def _evidence_supports_claim(self, sentence: str, evidence: str) -> bool:
        claim_terms = self._meaningful_terms(sentence)
        if not claim_terms:
            return False

        evidence_terms = self._meaningful_terms(evidence)
        if not evidence_terms:
            return False

        overlap = claim_terms & evidence_terms
        coverage = len(overlap) / len(claim_terms)
        return coverage >= 0.55 or claim_terms.issubset(evidence_terms)

    def _meaningful_terms(self, text: str) -> set[str]:
        text = re.sub(r"\[\d+\]", " ", text.lower())
        raw_terms = re.findall(r"\b[a-z0-9][a-z0-9-]*\b", text)
        terms: set[str] = set()
        for term in raw_terms:
            normalized = self._normalize_term(term)
            if normalized and normalized not in _STOPWORDS:
                terms.add(normalized)
        return terms

    def _normalize_term(self, term: str) -> str:
        if len(term) > 4 and term.endswith("ies"):
            return f"{term[:-3]}y"
        if len(term) > 3 and term.endswith("s"):
            return term[:-1]
        return term
