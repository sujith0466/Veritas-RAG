import re

from backend.modules.health.schemas.health_dto import (DocumentIssueDTO,
                                                       IssueType)


class RedundancyDetector:
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def _overlap_ratio(self, text1: str, text2: str) -> float:
        words1 = set(re.findall(r"\w+", text1.lower()))
        words2 = set(re.findall(r"\w+", text2.lower()))
        if not words1 or not words2:
            return 0.0
        return len(words1.intersection(words2)) / max(len(words1), len(words2))

    async def detect(self, documents: list[dict]) -> list[DocumentIssueDTO]:
        """
        Detects redundant documents based on high word overlap.
        Expects documents with 'id' and 'content' keys.
        """
        issues = []
        n = len(documents)
        processed = set()

        for i in range(n):
            if i in processed:
                continue

            doc1 = documents[i]
            duplicates = []

            for j in range(i + 1, n):
                if j in processed:
                    continue
                doc2 = documents[j]

                overlap = self._overlap_ratio(doc1["content"], doc2["content"])
                if overlap >= self.threshold:
                    duplicates.append(doc2["id"])
                    processed.add(j)

            if duplicates:
                issues.append(
                    DocumentIssueDTO(
                        document_id=doc1["id"],
                        issue_type=IssueType.REDUNDANT,
                        description=f"High redundancy ({len(duplicates)} duplicates found)",
                        severity=0.6,
                        related_document_ids=duplicates,
                    )
                )

        return issues
