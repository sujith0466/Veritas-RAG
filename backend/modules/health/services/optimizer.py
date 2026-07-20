from backend.modules.health.schemas.health_dto import DocumentIssueDTO, QuarantineRequestDTO, QuarantineAction, IssueType

class KnowledgeOptimizer:
    def __init__(self, auto_quarantine_threshold: float = 0.8):
        self.auto_quarantine_threshold = auto_quarantine_threshold

    def generate_optimization_plan(self, issues: list[DocumentIssueDTO]) -> list[QuarantineRequestDTO]:
        """
        Determines which issues should trigger automatic quarantine or flags.
        """
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
