from backend.modules.health.repositories.health_repository import \
    HealthRepository
from backend.modules.health.schemas.health_dto import HealthReportDTO
from backend.modules.health.services.contradiction_detector import \
    ContradictionDetector
from backend.modules.health.services.optimizer import KnowledgeOptimizer
from backend.modules.health.services.redundancy_detector import \
    RedundancyDetector


class HealthAnalysisTask:
    def __init__(self, repository: HealthRepository):
        self.repository = repository
        self.redundancy_detector = RedundancyDetector()
        self.contradiction_detector = ContradictionDetector()
        self.optimizer = KnowledgeOptimizer()

    async def run_analysis(
        self, tenant_id: str, documents: list[dict]
    ) -> HealthReportDTO:
        """
        Runs health analysis on a batch of documents for a tenant.
        """
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
            health_score=health_score,
        )

        await self.repository.save_health_report(report)
        return report
