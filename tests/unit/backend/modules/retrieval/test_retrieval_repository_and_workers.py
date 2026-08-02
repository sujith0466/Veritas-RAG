"""Unit tests for Phase 2 Milestone 4 (Hybrid Retrieval Engine) - Phase 3: Repository, Domain Events & Celery Workers."""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.core.events.types import EventType
from backend.modules.retrieval.events.payloads import (
    RetrievalDomainEvent,
    create_query_retrieved_payload,
)
from backend.modules.retrieval.models.retrieval_log import RetrievalQueryLog
from backend.modules.retrieval.repositories.retrieval_repository import (
    RetrievalRepository,
)
from backend.modules.retrieval.schemas.errors import (
    ErrorSeverity,
    RerankerTimeoutError,
)
from backend.modules.retrieval.schemas.retrieval_dto import (
    RetrievalQueryLogDTO,
)
from backend.modules.retrieval.workers.tasks import (
    _async_execute_batch_search,
    execute_async_batch_search_task,
)


def test_query_retrieved_payload_and_event() -> None:
    payload = create_query_retrieved_payload(
        tenant_id="org_audit",
        correlation_id="req_test_123",
        query_text="What are the TLS policies?",
        top_k=5,
        dense_count=15,
        sparse_count=12,
        merged_count=20,
        reranker_model="BAAI/bge-reranker-large",
        duration_ms=45.2,
        stage_latencies={"dense_ms": 10.0, "sparse_ms": 8.0, "rerank_ms": 25.0},
    )

    assert payload.schema_version == "1.0.0"
    assert payload.event_type == str(EventType.QUERY_RETRIEVED)
    assert payload.tenant_id == "org_audit"
    assert payload.correlation_id == "req_test_123"
    assert payload.unique_merged_candidates == 20
    assert payload.stage_latencies["dense_ms"] == 10.0

    event = RetrievalDomainEvent(payload=payload)
    assert event.payload == payload


def test_retrieval_query_log_orm_model() -> None:
    log_entry = RetrievalQueryLog(
        id=uuid.uuid4(),
        tenant_id="org_audit",
        correlation_id="corr_999",
        query_text="ORM model representation check",
        dense_candidate_count=20,
        sparse_candidate_count=15,
        merged_unique_count=25,
        final_top_k=5,
        total_duration_ms=112.5,
        stage_breakdown_json={"dense_ms": 30.0},
    )

    assert log_entry.tenant_id == "org_audit"
    assert "ORM model" in repr(log_entry)
    assert log_entry.total_duration_ms == 112.5


@pytest.mark.asyncio
class TestRetrievalRepository:
    async def test_log_query_execution_and_get_history(self) -> None:
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [MagicMock(), MagicMock()]
        mock_exec_res = MagicMock()
        mock_exec_res.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_exec_res)

        repo = RetrievalRepository(session=mock_session)

        dto = RetrievalQueryLogDTO(
            id=uuid.uuid4(),
            tenant_id="org_audit",
            correlation_id="corr_1",
            query_text="Verify repository insert",
            dense_candidate_count=10,
            sparse_candidate_count=10,
            merged_unique_count=15,
            final_top_k=5,
            total_duration_ms=50.0,
            stage_breakdown_json={"dense_ms": 15.0},
        )

        returned_id = await repo.log_query_execution(dto)
        assert returned_id == dto.id
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        history = await repo.get_query_history(tenant_id="org_audit", limit=10)
        assert len(history) == 2

    async def test_get_tenant_metrics(self) -> None:
        mock_session = MagicMock()

        # Call sequence of execute:
        # 1. count_stmt -> 2 queries
        # 2. avg_stmt -> (60.0, 15.0, 12.0, 20.0)
        # 3. durations_stmt -> [40.0, 80.0]
        # 4. recent_stmt -> [{"dense_ms": 10.0, "sparse_ms": 5.0, "rrf_fusion_ms": 2.0, "rerank_ms": 20.0}]
        mock_count = MagicMock()
        mock_count.scalar.return_value = 2

        mock_avg = MagicMock()
        mock_avg.first.return_value = (60.0, 15.0, 12.0, 20.0)

        mock_dur = MagicMock()
        mock_dur.scalars.return_value.all.return_value = [40.0, 80.0]

        mock_rec = MagicMock()
        mock_rec.scalars.return_value.all.return_value = [
            {"dense_ms": 10.0, "sparse_ms": 5.0, "rrf_fusion_ms": 2.0, "rerank_ms": 20.0}
        ]

        mock_session.execute = AsyncMock(side_effect=[mock_count, mock_avg, mock_dur, mock_rec])

        repo = RetrievalRepository(session=mock_session)
        metrics = await repo.get_tenant_metrics(tenant_id="org_audit")

        assert metrics.tenant_id == "org_audit"
        assert metrics.total_queries_executed == 2
        assert metrics.avg_total_duration_ms == 60.0
        assert metrics.p95_total_duration_ms == 80.0
        assert metrics.avg_dense_candidates == 15.0
        assert metrics.stage_latencies_avg.dense_ms == 10.0


@pytest.mark.asyncio
class TestCeleryBatchSearchWorker:
    async def test_async_execute_batch_search_success(self) -> None:
        mock_session = MagicMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock()

        with patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=mock_factory):
            with patch(
                "backend.modules.retrieval.workers.tasks.RetrievalOrchestrator.execute_hybrid_search",
                new_callable=AsyncMock,
            ) as mock_hybrid:
                mock_res = MagicMock()
                mock_res.correlation_id = "corr_batch_1"
                mock_res.final_evidence = [MagicMock(), MagicMock()]
                mock_res.stage_latencies.total_ms = 85.0
                mock_hybrid.return_value = mock_res

                result = await _async_execute_batch_search(
                    task=MagicMock(),
                    queries=["Batch query 1", "Batch query 2"],
                    tenant_id="org_batch",
                    top_k=5,
                    webhook_url=None,
                )

                assert result["status"] == "COMPLETED"
                assert result["queries_processed"] == 2
                assert len(result["results"]) == 2
                assert mock_hybrid.call_count == 2

    def test_celery_task_recoverable_error_triggers_retry(self) -> None:
        execute_async_batch_search_task.push_request(retries=1)
        try:
            with patch("backend.modules.retrieval.workers.tasks.asyncio.run") as mock_run:
                rec_exc = RerankerTimeoutError("Timeout on reranker (`RET_003`)")
                assert rec_exc.severity == ErrorSeverity.RECOVERABLE
                mock_run.side_effect = rec_exc

                with patch.object(
                    execute_async_batch_search_task, "retry", side_effect=RuntimeError("RetryTriggered")
                ) as mock_retry:
                    with pytest.raises(RuntimeError, match="RetryTriggered"):
                        execute_async_batch_search_task(["Test retry query"], "org_retry")
                    mock_retry.assert_called_once()
        finally:
            execute_async_batch_search_task.pop_request()
