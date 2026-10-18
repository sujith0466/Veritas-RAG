"""Regression test for Docker Compose Celery worker queue contract (P0-1).

Validates that the root docker-compose.yml Celery worker service explicitly
subscribes to all mandatory ingestion, processing, and indexing queues,
specifically including the 'indexing' queue required by sync_vectors_to_qdrant_task.
"""

from pathlib import Path
import yaml
import pytest


# Determine repository root relative to this test file:
# tests/unit/backend/core/test_compose_queue_contract.py -> 5 levels up to repo root
REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"

MANDATORY_QUEUES = {
    "ingestion",
    "indexing",
    "embeddings",
    "retrieval",
    "default",
    "retention",
}


def test_root_docker_compose_worker_subscribes_to_indexing_queue():
    """Verify that root docker-compose.yml worker command includes the 'indexing' queue."""
    assert COMPOSE_PATH.exists(), f"docker-compose.yml not found at {COMPOSE_PATH}"

    with open(COMPOSE_PATH, "r", encoding="utf-8") as f:
        compose_data = yaml.safe_load(f)

    assert isinstance(compose_data, dict), "docker-compose.yml must parse to a mapping"
    services = compose_data.get("services", {})
    assert "worker" in services, "Service 'worker' not found in docker-compose.yml"

    worker_service = services["worker"]
    worker_cmd = worker_service.get("command")
    assert worker_cmd is not None, "Worker service must define a 'command' attribute"

    # Support either list or string representation of command in Compose
    if isinstance(worker_cmd, list):
        cmd_tokens = worker_cmd
    elif isinstance(worker_cmd, str):
        cmd_tokens = worker_cmd.split()
    else:
        pytest.fail(f"Unexpected type for worker command: {type(worker_cmd)}")

    assert "celery" in cmd_tokens, f"Expected celery command, got: {worker_cmd}"
    assert "-Q" in cmd_tokens, f"Expected explicit queue list (-Q) in worker command: {worker_cmd}"

    q_idx = cmd_tokens.index("-Q")
    assert q_idx + 1 < len(cmd_tokens), "Malformed -Q argument: no queue list argument follows -Q"

    queue_arg = cmd_tokens[q_idx + 1]
    subscribed_queues = {q.strip() for q in queue_arg.split(",") if q.strip()}

    # Assert 'indexing' specifically for P0-1
    assert "indexing" in subscribed_queues, (
        f"Defect P0-1 detected: 'indexing' queue is missing from root worker subscription. "
        f"Subscribed queues: {subscribed_queues}"
    )

    # Assert all mandatory queues are present
    missing = MANDATORY_QUEUES - subscribed_queues
    assert not missing, f"Missing mandatory queues in root compose worker: {missing}"
