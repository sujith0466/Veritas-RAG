import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 14.3: Health Tasks & APIs
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 14.3 Implementation...")
    
    # 1. tasks/health_tasks.py
    with open("backend/modules/health/tasks/__init__.py", "w") as f:
        f.write('"""Health tasks."""\n')

    tasks_path = "backend/modules/health/tasks/health_tasks.py"
    if not os.path.exists(tasks_path):
        with open(tasks_path, "w") as f:
            f.write("""from backend.modules.health.schemas.health_dto import HealthReportDTO
from backend.modules.health.services.redundancy_detector import RedundancyDetector
from backend.modules.health.services.contradiction_detector import ContradictionDetector
from backend.modules.health.services.optimizer import KnowledgeOptimizer
from backend.modules.health.repositories.health_repository import HealthRepository

class HealthAnalysisTask:
    def __init__(self, repository: HealthRepository):
        self.repository = repository
        self.redundancy_detector = RedundancyDetector()
        self.contradiction_detector = ContradictionDetector()
        self.optimizer = KnowledgeOptimizer()

    async def run_analysis(self, tenant_id: str, documents: list[dict]) -> HealthReportDTO:
        \"\"\"
        Runs health analysis on a batch of documents for a tenant.
        \"\"\"
        # Detect issues
        redundancy_issues = await self.redundancy_detector.detect(documents)
        contradiction_issues = await self.contradiction_detector.detect(documents)
        
        all_issues = redundancy_issues + contradiction_issues
        
        # Optimize / Plan Quarantine
        quarantine_actions = self.optimizer.generate_optimization_plan(all_issues)
        quarantined_ids = [q.document_id for q in quarantine_actions]
        
        # Execute quarantines
        for action in quarantine_actions:
            await self.repository.save_quarantine_action(action)
            
        # Compute arbitrary health score for baseline: 100 - (issues * 5)
        health_score = max(100.0 - (len(all_issues) * 5.0), 0.0)
        
        report = HealthReportDTO(
            tenant_id=tenant_id,
            total_documents_analyzed=len(documents),
            issues_found=all_issues,
            quarantined_documents=quarantined_ids,
            health_score=health_score
        )
        
        await self.repository.save_health_report(report)
        return report
""")
        print("Created tasks/health_tasks.py")

    # 2. api/routes.py
    with open("backend/modules/health/api/__init__.py", "w") as f:
        f.write('"""Health API routes."""\n')

    routes_path = "backend/modules/health/api/routes.py"
    if not os.path.exists(routes_path):
        with open(routes_path, "w") as f:
            f.write("""from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.engine import get_db_session
from backend.modules.health.schemas.health_dto import HealthReportDTO
from backend.modules.health.tasks.health_tasks import HealthAnalysisTask
from backend.modules.health.repositories.health_repository import HealthRepository
from pydantic import BaseModel

router = APIRouter(prefix="/health/v1", tags=["KnowledgeHealth"])

class AnalysisRequestDTO(BaseModel):
    tenant_id: str
    documents: list[dict]  # Simplified for M14

def get_health_task(session: AsyncSession = Depends(get_db_session)) -> HealthAnalysisTask:
    repo = HealthRepository(session)
    return HealthAnalysisTask(repo)

@router.post("/analyze", response_model=HealthReportDTO)
async def analyze_corpus(
    request: AnalysisRequestDTO,
    task: HealthAnalysisTask = Depends(get_health_task)
):
    try:
        # In a real system this would be a celery task, but we await it here for M14 tests
        return await task.run_analysis(request.tenant_id, request.documents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
""")
        print("Created api/routes.py")

    print("Milestone 14.3 completed.")

if __name__ == "__main__":
    main()
