import os
import sys
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 14.4: Unit Tests & Verification
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 14.4 Implementation (Tests)...")
    os.makedirs("tests/unit/backend/modules/health", exist_ok=True)
    
    # 1. test_redundancy_detector.py
    t_redundancy_path = "tests/unit/backend/modules/health/test_redundancy_detector.py"
    with open(t_redundancy_path, "w") as f:
        f.write("""import pytest
from backend.modules.health.services.redundancy_detector import RedundancyDetector

@pytest.mark.asyncio
async def test_detect_redundancy():
    detector = RedundancyDetector(threshold=0.8)
    documents = [
        {"id": "doc1", "content": "The quick brown fox jumps over the lazy dog."},
        {"id": "doc2", "content": "The quick brown fox jumps over the lazy dog."},
        {"id": "doc3", "content": "A completely different document here."}
    ]
    
    issues = await detector.detect(documents)
    assert len(issues) == 1
    assert issues[0].document_id == "doc1"
    assert "doc2" in issues[0].related_document_ids
""")

    # 2. test_contradiction_detector.py
    t_contradiction_path = "tests/unit/backend/modules/health/test_contradiction_detector.py"
    with open(t_contradiction_path, "w") as f:
        f.write("""import pytest
from backend.modules.health.services.contradiction_detector import ContradictionDetector

@pytest.mark.asyncio
async def test_detect_contradiction():
    detector = ContradictionDetector()
    documents = [
        {"id": "doc1", "content": "The company revenue was 50 million dollars."},
        {"id": "doc2", "content": "The company revenue was NOT 50 million dollars."}
    ]
    
    issues = await detector.detect(documents)
    assert len(issues) == 1
    assert issues[0].document_id == "doc1"
    assert "doc2" in issues[0].related_document_ids
""")

    # 3. test_optimizer.py
    t_optimizer_path = "tests/unit/backend/modules/health/test_optimizer.py"
    with open(t_optimizer_path, "w") as f:
        f.write("""import pytest
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
""")

    # 4. test_health_tasks.py
    t_task_path = "tests/unit/backend/modules/health/test_health_tasks.py"
    with open(t_task_path, "w") as f:
        f.write("""import pytest
from unittest.mock import AsyncMock
from backend.modules.health.tasks.health_tasks import HealthAnalysisTask

@pytest.mark.asyncio
async def test_health_task():
    mock_repo = AsyncMock()
    task = HealthAnalysisTask(repository=mock_repo)
    
    documents = [
        {"id": "doc1", "content": "Water is wet."},
        {"id": "doc2", "content": "Water is NOT wet."}
    ]
    
    report = await task.run_analysis("tenant1", documents)
    
    assert report.total_documents_analyzed == 2
    assert len(report.issues_found) == 1
    assert mock_repo.save_health_report.called
    assert mock_repo.save_quarantine_action.called
""")

    print("Created test files.")
    
    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/backend/modules/health"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    print("Milestone 14.4 completed.")

if __name__ == "__main__":
    main()
