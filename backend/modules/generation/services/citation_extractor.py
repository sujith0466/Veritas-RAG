import re

from backend.modules.generation.schemas.generation_dto import CitationDTO


class CitationExtractor:
    """Extracts and builds citation objects from inline citation markers in generated text.

    Expects generated text to contain markers like [1], [2], and a reference map
    that associates each index to a source chunk.
    """

    def extract(
        self, answer_text: str, evidence_chunks: list[dict]
    ) -> list[CitationDTO]:
        """Build an ordered CitationDTO list from the answer's inline markers.

        Args:
            answer_text: The generated answer containing [N] citation markers.
            evidence_chunks: Ordered list of dicts with keys: chunk_id, document_id, content.

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
            excerpt = chunk.get("content", "")[:200].strip()

            citations.append(
                CitationDTO(
                    citation_index=idx,
                    chunk_id=chunk.get("chunk_id", f"chunk_{idx}"),
                    document_id=chunk.get("document_id", "unknown"),
                    excerpt=excerpt,
                    relevance_score=chunk.get("score", 1.0),
                )
            )

        return citations

    def check_grounding(self, answer_text: str, citations: list[CitationDTO]) -> bool:
        """Return True if every meaningful sentence in the answer is followed by or contains
        at least one citation marker [N].

        Strategy: extract "claim units" as sentence + optional trailing citation(s).
        A sentence that has no marker attached (inline or trailing) is flagged as ungrounded.
        """
        if not citations:
            return len(answer_text.split()) <= 5

        # Match a sentence (ending with . ! ?) optionally followed by [N] markers
        # This handles both "claim. [1]" and "claim [1]." styles
        claim_pattern = re.compile(
            r"([A-Z][^.!?]*[.!?])\s*(\[\d+\](?:\s*\[\d+\])*)?", re.DOTALL
        )
        marker_pattern = re.compile(r"\[\d+\]")

        matches = claim_pattern.findall(answer_text)
        if not matches:
            # Couldn't parse sentences — fall back to checking total marker count
            return len(marker_pattern.findall(answer_text)) > 0

        for sentence, trailing_markers in matches:
            words = sentence.split()
            if len(words) <= 4:
                continue  # Skip very short connective clauses

            # Check trailing marker OR inline marker within the sentence itself
            if trailing_markers or marker_pattern.search(sentence):
                continue  # This sentence is cited

            return False  # Found a meaningful uncited sentence

        return True
