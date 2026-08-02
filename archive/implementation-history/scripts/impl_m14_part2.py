import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 14.2: Detectors & Optimizer
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 14.2 Implementation...")
    
    # 1. redundancy_detector.py
    redundancy_path = "backend/modules/health/services/redundancy_detector.py"
    if not os.path.exists(redundancy_path):
        with open(redundancy_path, "w") as f:
            f.write("""from backend.modules.health.schemas.health_dto import DocumentIssueDTO, IssueType
import re

class RedundancyDetector:
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def _overlap_ratio(self, text1: str, text2: str) -> float:
        words1 = set(re.findall(r'\\w+', text1.lower()))
        words2 = set(re.findall(r'\\w+', text2.lower()))
        if not words1 or not words2:
            return 0.0
        return len(words1.intersection(words2)) / max(len(words1), len(words2))

    async def detect(self, documents: list[dict]) -> list[DocumentIssueDTO]:
        \"\"\"
        Detects redundant documents based on high word overlap.
        Expects documents with 'id' and 'content' keys.
        \"\"\"
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
                
                overlap = self._overlap_ratio(doc1['content'], doc2['content'])
                if overlap >= self.threshold:
                    duplicates.append(doc2['id'])
                    processed.add(j)
                    
            if duplicates:
                issues.append(DocumentIssueDTO(
                    document_id=doc1['id'],
                    issue_type=IssueType.REDUNDANT,
                    description=f"High redundancy ({len(duplicates)} duplicates found)",
                    severity=0.6,
                    related_document_ids=duplicates
                ))
                
        return issues
""")
        print("Created redundancy_detector.py")

    # 2. contradiction_detector.py
    contradiction_path = "backend/modules/health/services/contradiction_detector.py"
    if not os.path.exists(contradiction_path):
        with open(contradiction_path, "w") as f:
            f.write("""from backend.modules.health.schemas.health_dto import DocumentIssueDTO, IssueType
import re

class ContradictionDetector:
    def __init__(self):
        self.negation_pattern = re.compile(r'\\b(not|never|no|none|false|fake|invalid)\\b', re.IGNORECASE)

    async def detect(self, documents: list[dict]) -> list[DocumentIssueDTO]:
        \"\"\"
        Detects potential contradictions across documents in the corpus.
        \"\"\"
        issues = []
        n = len(documents)
        
        for i in range(n):
            doc1 = documents[i]
            c1_words = set(re.findall(r'\\w+', doc1['content'].lower()))
            c1_core = c1_words - {'not', 'never', 'no', 'none', 'is', 'are', 'was', 'were', 'the', 'a', 'to', 'in'}
            c1_neg = bool(self.negation_pattern.search(doc1['content']))
            
            conflicts = []
            for j in range(i + 1, n):
                doc2 = documents[j]
                c2_words = set(re.findall(r'\\w+', doc2['content'].lower()))
                c2_core = c2_words - {'not', 'never', 'no', 'none', 'is', 'are', 'was', 'were', 'the', 'a', 'to', 'in'}
                c2_neg = bool(self.negation_pattern.search(doc2['content']))
                
                if not c1_core or not c2_core:
                    continue
                    
                overlap = len(c1_core.intersection(c2_core)) / max(len(c1_core), len(c2_core))
                
                if overlap > 0.8 and c1_neg != c2_neg:
                    conflicts.append(doc2['id'])
                    
            if conflicts:
                issues.append(DocumentIssueDTO(
                    document_id=doc1['id'],
                    issue_type=IssueType.CONTRADICTORY,
                    description=f"Potential contradiction with {len(conflicts)} documents",
                    severity=0.9,
                    related_document_ids=conflicts
                ))
                
        return issues
""")
        print("Created contradiction_detector.py")

    # 3. optimizer.py
    optimizer_path = "backend/modules/health/services/optimizer.py"
    if not os.path.exists(optimizer_path):
        with open(optimizer_path, "w") as f:
            f.write("""from backend.modules.health.schemas.health_dto import DocumentIssueDTO, QuarantineRequestDTO, QuarantineAction, IssueType

class KnowledgeOptimizer:
    def __init__(self, auto_quarantine_threshold: float = 0.8):
        self.auto_quarantine_threshold = auto_quarantine_threshold

    def generate_optimization_plan(self, issues: list[DocumentIssueDTO]) -> list[QuarantineRequestDTO]:
        \"\"\"
        Determines which issues should trigger automatic quarantine or flags.
        \"\"\"
        actions = []
        for issue in issues:
            if issue.severity >= self.auto_quarantine_threshold:
                if issue.issue_type == IssueType.CONTRADICTORY:
                    # Contradictions are severe, soft delete or flag for manual review
                    actions.append(QuarantineRequestDTO(
                        document_id=issue.document_id,
                        action=QuarantineAction.FLAG,
                        reason=f"Severe contradiction detected: {issue.description}"
                    ))
                elif issue.issue_type == IssueType.REDUNDANT:
                    # Redundant docs can be archived
                    for related_id in issue.related_document_ids:
                        actions.append(QuarantineRequestDTO(
                            document_id=related_id,
                            action=QuarantineAction.ARCHIVE,
                            reason=f"Duplicate of {issue.document_id}"
                        ))
            else:
                actions.append(QuarantineRequestDTO(
                    document_id=issue.document_id,
                    action=QuarantineAction.FLAG,
                    reason=f"Low severity issue flagged: {issue.description}"
                ))
        return actions
""")
        print("Created optimizer.py")

    print("Milestone 14.2 completed.")

if __name__ == "__main__":
    main()
