from unittest.mock import AsyncMock

import pytest

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
