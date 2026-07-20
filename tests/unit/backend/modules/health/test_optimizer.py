import pytest
from backend.modules.health.services.optimizer import KnowledgeOptimizer
from backend.modules.health.schemas.health_dto import DocumentIssueDTO, IssueType, QuarantineAction

def test_generate_optimization_plan():
    optimizer = KnowledgeOptimizer(auto_quarantine_threshold=0.8)
    
    issues = [
        DocumentIssueDTO(
            document_id="doc1",
            issue_type=IssueType.CONTRADICTORY,
            description="Contradicts doc2",
            severity=0.9,
            related_document_ids=["doc2"]
        ),
        DocumentIssueDTO(
            document_id="doc3",
            issue_type=IssueType.REDUNDANT,
            description="Duplicate of doc4",
            severity=0.85,
            related_document_ids=["doc4"]
        )
    ]
    
    actions = optimizer.generate_optimization_plan(issues)
    assert len(actions) == 2
    assert actions[0].document_id == "doc1"
    assert actions[0].action == QuarantineAction.FLAG
    assert actions[1].document_id == "doc4"
    assert actions[1].action == QuarantineAction.ARCHIVE
