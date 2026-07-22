import re

from backend.modules.health.schemas.health_dto import (DocumentIssueDTO,
                                                       IssueType)


class ContradictionDetector:
    def __init__(self):
        self.negation_pattern = re.compile(
            r"\b(not|never|no|none|false|fake|invalid)\b", re.IGNORECASE
        )

    async def detect(self, documents: list[dict]) -> list[DocumentIssueDTO]:
        """
        Detects potential contradictions across documents in the corpus.
        """
        issues = []
        n = len(documents)

        for i in range(n):
            doc1 = documents[i]
            c1_words = set(re.findall(r"\w+", doc1["content"].lower()))
            c1_core = c1_words - {
                "not",
                "never",
                "no",
                "none",
                "is",
                "are",
                "was",
                "were",
                "the",
                "a",
                "to",
                "in",
            }
            c1_neg = bool(self.negation_pattern.search(doc1["content"]))

            conflicts = []
            for j in range(i + 1, n):
                doc2 = documents[j]
                c2_words = set(re.findall(r"\w+", doc2["content"].lower()))
                c2_core = c2_words - {
                    "not",
                    "never",
                    "no",
                    "none",
                    "is",
                    "are",
                    "was",
                    "were",
                    "the",
                    "a",
                    "to",
                    "in",
                }
                c2_neg = bool(self.negation_pattern.search(doc2["content"]))

                if not c1_core or not c2_core:
                    continue

                overlap = len(c1_core.intersection(c2_core)) / max(
                    len(c1_core), len(c2_core)
                )

                if overlap > 0.8 and c1_neg != c2_neg:
                    conflicts.append(doc2["id"])

            if conflicts:
                issues.append(
                    DocumentIssueDTO(
                        document_id=doc1["id"],
                        issue_type=IssueType.CONTRADICTORY,
                        description=f"Potential contradiction with {len(conflicts)} documents",
                        severity=0.9,
                        related_document_ids=conflicts,
                    )
                )

        return issues
