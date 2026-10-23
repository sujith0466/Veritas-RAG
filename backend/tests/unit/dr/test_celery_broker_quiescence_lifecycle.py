"""Unit tests for Celery Broker Quiescence Lifecycle (`WP-3C Phase 2`, `TSK-3C-06`, `FND-REL-01`).

Verifies:
1. Cancellation broadcasts across all 17 authoritative Celery queues.
2. Consumer restoration broadcasts across all 17 queues upon completion or timeout.
3. Active and reserved task count aggregation across worker nodes.
4. Clean quiescence when worker tasks drain to zero before timeout.
5. Fail-closed timeout behavior: re-adds consumers and raises CeleryQuiescenceTimeoutError when tasks linger.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from celery import Celery
import pytest

from backend.tasks.quiescence import (
    ALL_CELERY_QUEUES,
    CeleryInspectionError,
    CeleryQuiescenceTimeoutError,
    cancel_all_consumers,
    get_worker_task_counts,
    quiesce_celery,
    restore_all_consumers,
)


@pytest.fixture
def mock_celery_app():
    app = MagicMock(spec=Celery)
    app.control = MagicMock()
    app.control.cancel_consumer = MagicMock(return_value={"celery@worker1": "ok"})
    app.control.add_consumer = MagicMock(return_value={"celery@worker1": "ok"})
    return app


def test_cancel_all_consumers_broadcasts_all_17_queues(mock_celery_app):
    results = cancel_all_consumers(mock_celery_app)
    assert len(results) == 17
    assert mock_celery_app.control.cancel_consumer.call_count == 17
    for q in ALL_CELERY_QUEUES:
        assert q in results


def test_restore_all_consumers_broadcasts_all_17_queues(mock_celery_app):
    results = restore_all_consumers(mock_celery_app)
    assert len(results) == 17
    assert mock_celery_app.control.add_consumer.call_count == 17
    for q in ALL_CELERY_QUEUES:
        assert q in results


def test_get_worker_task_counts_aggregates_multiple_workers(mock_celery_app):
    inspector = MagicMock()
    inspector.active.return_value = {
        "celery@worker1": [{"id": "t1"}],
        "celery@worker2": [{"id": "t2"}, {"id": "t3"}],
    }
    inspector.reserved.return_value = {
        "celery@worker1": [{"id": "t4"}],
        "celery@worker2": [],
    }
    mock_celery_app.control.inspect.return_value = inspector

    active, reserved = get_worker_task_counts(mock_celery_app)
    assert active == 3
    assert reserved == 1


def test_get_worker_task_counts_raises_on_unreachable_broker(mock_celery_app):
    mock_celery_app.control.inspect.return_value = None
    with pytest.raises(CeleryInspectionError):
        get_worker_task_counts(mock_celery_app)


def test_quiesce_celery_succeeds_when_tasks_drain_to_zero(mock_celery_app):
    inspector = MagicMock()
    # First call: active=1; second call: active=0
    inspector.active.side_effect = [
        {"celery@worker1": [{"id": "t1"}]},
        {"celery@worker1": []},
    ]
    inspector.reserved.return_value = {"celery@worker1": []}
    mock_celery_app.control.inspect.return_value = inspector

    res = quiesce_celery(mock_celery_app, timeout_seconds=5.0, poll_interval_seconds=0.01)
    assert res["status"] == "quiesced"
    assert res["active_tasks"] == 0
    assert res["reserved_tasks"] == 0


def test_quiesce_celery_fails_closed_and_restores_consumers_on_timeout(mock_celery_app):
    inspector = MagicMock()
    inspector.active.return_value = {"celery@worker1": [{"id": "lingering_task"}]}
    inspector.reserved.return_value = {"celery@worker1": []}
    mock_celery_app.control.inspect.return_value = inspector

    with pytest.raises(CeleryQuiescenceTimeoutError):
        quiesce_celery(mock_celery_app, timeout_seconds=0.05, poll_interval_seconds=0.01)

    # Must have restored consumers when timeout occurred
    assert mock_celery_app.control.add_consumer.call_count == 17
