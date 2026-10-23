"""Celery Consumer Quiescence & Drain Helper (`WP-3C Phase 2`, `TSK-3C-06`, `FND-REL-01`).

Implements clean consumer cancellation across all 17 Veritas-RAG Celery queues,
bounds active and reserved task draining, and guarantees consumer restoration
upon completion or timeout.
"""

from __future__ import annotations

import time
from typing import Any

from celery import Celery
import structlog

logger = structlog.get_logger(__name__)

# All 17 authoritative Celery queues from celery_app.py
ALL_CELERY_QUEUES = [
    "high",
    "medium",
    "folders.critical",
    "folders.purge",
    "default",
    "ingestion",
    "indexing",
    "embeddings",
    "retrieval",
    "evaluation",
    "health",
    "ai",
    "jobs.high",
    "jobs.default",
    "jobs.dlq",
    "webhooks",
    "retention",
]


class CeleryQuiescenceTimeoutError(Exception):
    """Raised when Celery workers fail to drain active and reserved tasks within timeout."""


class CeleryInspectionError(Exception):
    """Raised when Celery worker inspect() call returns None or times out."""


def cancel_all_consumers(app: Celery) -> dict[str, Any]:
    """Broadcast cancel_consumer across all 17 queues to halt ingress off broker socket."""
    results: dict[str, Any] = {}
    for q in ALL_CELERY_QUEUES:
        try:
            res = app.control.cancel_consumer(q, reply=True)
            results[q] = res
        except Exception as exc:
            logger.warning("Error canceling consumer for queue", queue=q, error=str(exc))
            results[q] = str(exc)
    logger.info("Canceled consumers across all queues", queue_count=len(ALL_CELERY_QUEUES))
    return results


def restore_all_consumers(app: Celery) -> dict[str, Any]:
    """Broadcast add_consumer across all 17 queues to resume message processing."""
    results: dict[str, Any] = {}
    for q in ALL_CELERY_QUEUES:
        try:
            res = app.control.add_consumer(q, reply=True)
            results[q] = res
        except Exception as exc:
            logger.error("Error restoring consumer for queue", queue=q, error=str(exc))
            results[q] = str(exc)
    logger.info("Restored consumers across all queues", queue_count=len(ALL_CELERY_QUEUES))
    return results


def get_worker_task_counts(app: Celery) -> tuple[int, int]:
    """Inspect active and reserved tasks across all registered Celery workers.

    Returns:
        (total_active, total_reserved)

    Raises:
        CeleryInspectionError if inspect() times out or fails.
    """
    inspector = app.control.inspect(timeout=5.0)
    if inspector is None:
        raise CeleryInspectionError("Celery inspect() returned None; broker unreachable")

    active_dict = inspector.active()
    reserved_dict = inspector.reserved()

    if active_dict is None or reserved_dict is None:
        raise CeleryInspectionError("Celery inspect active/reserved returned None (worker unreachable)")

    total_active = sum(len(tasks) for tasks in active_dict.values())
    total_reserved = sum(len(tasks) for tasks in reserved_dict.values())
    return total_active, total_reserved


def quiesce_celery(
    app: Celery,
    timeout_seconds: float = 60.0,
    poll_interval_seconds: float = 1.0,
) -> dict[str, Any]:
    """Execute clean Celery quiescence: stop consumers and drain active + reserved tasks.

    Fails closed: restores consumers and raises CeleryQuiescenceTimeoutError if timeout expires.
    """
    logger.info("Initiating Celery quiescence across 17 queues", timeout=timeout_seconds)
    cancel_all_consumers(app)

    t0 = time.time()
    while True:
        elapsed = time.time() - t0
        if elapsed > timeout_seconds:
            logger.error(
                "Celery quiescence timed out before workers drained; restoring consumers and failing closed",
                elapsed=round(elapsed, 2),
                timeout=timeout_seconds,
            )
            restore_all_consumers(app)
            raise CeleryQuiescenceTimeoutError(
                f"Celery workers failed to drain active and reserved tasks within {timeout_seconds}s timeout"
            )

        try:
            active, reserved = get_worker_task_counts(app)
            logger.info("Celery drain status", active=active, reserved=reserved, elapsed=round(elapsed, 1))
            if active == 0 and reserved == 0:
                logger.info("Celery quiescence achieved: zero active and reserved tasks", elapsed=round(elapsed, 2))
                return {
                    "status": "quiesced",
                    "drain_time_seconds": round(elapsed, 2),
                    "active_tasks": active,
                    "reserved_tasks": reserved,
                }
        except CeleryInspectionError as e:
            logger.warning("Transient inspection error during drain; retrying", error=str(e))

        time.sleep(poll_interval_seconds)
