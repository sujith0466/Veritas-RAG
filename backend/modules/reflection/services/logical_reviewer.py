import re

from backend.modules.reflection.schemas.reflection_dto import \
    ClaimValidationResultDTO


class LogicalConsistencyReviewer:
    def __init__(self):
        # Naive negation check for contradiction.
        # In a real setup, an NLI (Natural Language Inference) model would do this.
        self._negation_pattern = re.compile(
            r"\b(not|never|no|none|false|fake|invalid)\b", re.IGNORECASE
        )

    async def review(
        self, claim_results: list[ClaimValidationResultDTO], citations: list[str]
    ) -> tuple[float, list[str]]:
        """
        Reviews claim pairs for internal logical contradictions.
        Returns:
            consistency_score (float): 0.0 to 1.0
            contradictions_found (list[str]): Descriptions of conflicts
        """
        if len(claim_results) < 2:
            return 1.0, []

        contradictions = []
        claims = [c.claim_text.lower() for c in claim_results]

        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                c1 = claims[i]
                c2 = claims[j]

                # Simple heuristic: exact same core words, but one is negated
                words1 = set(re.findall(r"\w+", c1))
                words2 = set(re.findall(r"\w+", c2))

                neg1 = bool(self._negation_pattern.search(c1))
                neg2 = bool(self._negation_pattern.search(c2))

                core1 = words1 - {
                    "not",
                    "never",
                    "no",
                    "none",
                    "false",
                    "fake",
                    "invalid",
                    "is",
                    "are",
                    "was",
                    "were",
                }
                core2 = words2 - {
                    "not",
                    "never",
                    "no",
                    "none",
                    "false",
                    "fake",
                    "invalid",
                    "is",
                    "are",
                    "was",
                    "were",
                }

                # If core words are >80% overlapping but negation state differs -> potential contradiction
                if not core1 or not core2:
                    continue

                overlap = len(core1.intersection(core2))
                max_len = max(len(core1), len(core2))

                if overlap / max_len > 0.8 and neg1 != neg2:
                    contradictions.append(
                        f"Contradiction between Claim {i+1} and Claim {j+1}"
                    )

        # Reduce score based on contradictions
        total_pairs = (len(claims) * (len(claims) - 1)) / 2
        inconsistent_pairs = len(contradictions)

        score = 1.0 - (inconsistent_pairs / total_pairs)
        return max(0.0, score), contradictions
