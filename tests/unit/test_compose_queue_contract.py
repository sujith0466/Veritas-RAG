"""Unit contract test for AUD-003: Celery Worker Queue Subscription Alignment."""

from pathlib import Path
import re
import pytest
import yaml

from backend.tasks.celery_app import celery_app


# Reserved or unconsumed queues by architectural design
UNCONSUMED_QUEUES = {
    "jobs.dlq",     # Dead Letter Queue (durable holding, manual inspection)
    "ai",           # Reserved for future asynchronous batch AI evaluation
    "evaluation",   # Reserved for future offline RAGAS evaluation
}


def test_celery_worker_compose_queue_contract():
    """Verify docker-compose.yml worker command subscribes to all operational queues."""
    repo_root = Path(__file__).resolve().parents[2]
    compose_path = repo_root / "docker-compose.yml"
    assert compose_path.exists(), f"docker-compose.yml not found at {compose_path}"

    with open(compose_path, "r", encoding="utf-8") as f:
        compose_data = yaml.safe_load(f)

    worker_service = compose_data.get("services", {}).get("worker", {})
    command = worker_service.get("command", "")

    # Match -Q <queues>
    match = re.search(r"-Q\s+([^\s]+)", command)
    assert match, f"Worker command does not specify -Q queue flag: {command}"

    subscribed_queues = set(match.group(1).split(","))

    # All queues declared in celery_app
    declared_queues = set(celery_app.conf.task_queues.keys())

    # Expected operational queues
    expected_operational_queues = declared_queues - UNCONSUMED_QUEUES

    # 1. Assert exactly 14 operational queues are subscribed
    assert len(expected_operational_queues) == 14
    assert subscribed_queues == expected_operational_queues, (
        f"Worker queue subscription mismatch.\n"
        f"Missing from worker: {expected_operational_queues - subscribed_queues}\n"
        f"Unexpected in worker: {subscribed_queues - expected_operational_queues}"
    )

    # 2. Assert all declared queues are accounted for (subscribed + unconsumed)
    assert subscribed_queues | UNCONSUMED_QUEUES == declared_queues
