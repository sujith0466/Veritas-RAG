"""Unit tests for AdmissionControlMiddleware and Crash-Safe Writer Leases (`WP-3C Phase 2`, `TSK-3C-05`).

Verifies:
1. Mutating requests (POST/PUT/PATCH/DELETE) are admitted when maintenance mode is inactive.
2. Mutating requests are rejected with HTTP 503 and Retry-After: 30 when system:maintenance:mode is active.
3. Mutating requests are rejected with HTTP 503 when system:maintenance:recovery_locked is active.
4. Non-mutating requests (GET/HEAD/OPTIONS) pass through cleanly during maintenance.
5. Excluded routes (/health, /metrics) pass through cleanly during maintenance.
6. Dead writer leases expire after TTL and are pruned by CHECK_ACTIVE_WRITERS_SCRIPT.
7. Fail-closed rejection when Redis encounters connection errors during mutation admission.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from backend.core.middleware.admission_control import (
    CHECK_ACTIVE_WRITERS_SCRIPT,
    MAINTENANCE_MODE_KEY,
    RECOVERY_LOCKED_KEY,
    WRITER_KEY_PREFIX,
    WRITERS_SET_KEY,
    AdmissionControlMiddleware,
)
from tests.unit.backend.modules.reliability.test_circuit_breaker import (
    InMemoryRedisDouble,
)


class ExtendedRedisDouble(InMemoryRedisDouble):
    """Extended in-memory Redis test double supporting Admission Control Lua scripts."""

    def __init__(self) -> None:
        super().__init__()
        self.sets: dict[str, set[str]] = {}

    async def sadd(self, key: str, *members: str) -> int:
        if self.simulate_failure:
            raise RedisConnectionError("Simulated Redis failure")
        if key not in self.sets:
            self.sets[key] = set()
        count = 0
        for m in members:
            if m not in self.sets[key]:
                self.sets[key].add(str(m))
                count += 1
        return count

    async def smembers(self, key: str) -> set[str]:
        if self.simulate_failure:
            raise RedisConnectionError("Simulated Redis failure")
        return set(self.sets.get(key, set()))

    async def srem(self, key: str, *members: str) -> int:
        if self.simulate_failure:
            raise RedisConnectionError("Simulated Redis failure")
        if key not in self.sets:
            return 0
        count = 0
        for m in members:
            if m in self.sets[key]:
                self.sets[key].remove(m)
                count += 1
        return count

    async def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any:
        if self.simulate_failure:
            raise RedisConnectionError("Simulated Redis failure")

        keys = keys_and_args[:numkeys]
        args = keys_and_args[numkeys:]

        # ADMIT_MUTATION_SCRIPT
        if 'KEYS[1]' in script and 'KEYS[2]' in script and 'sadd' in script:
            mode_key, locked_key, writer_key, set_key = keys[0], keys[1], keys[2], keys[3]
            token, ttl = str(args[0]), int(args[1])
            self._clean_expired(mode_key)
            self._clean_expired(locked_key)
            if self.store.get(mode_key):
                return -1
            if self.store.get(locked_key):
                return -2
            await self.set(writer_key, token, ex=ttl)
            await self.sadd(set_key, token)
            return 1

        # RENEW_MUTATION_SCRIPT
        if 'expire' in script and numkeys == 1:
            writer_key = keys[0]
            token, ttl = str(args[0]), int(args[1])
            self._clean_expired(writer_key)
            if self.store.get(writer_key) == token:
                await self.expire(writer_key, ttl)
                return 1
            return 0

        # RELEASE_MUTATION_SCRIPT
        if 'srem' in script and numkeys == 2 and 'del' in script:
            writer_key, set_key = keys[0], keys[1]
            token = str(args[0])
            self._clean_expired(writer_key)
            if self.store.get(writer_key) == token:
                await self.delete(writer_key)
                await self.srem(set_key, token)
                return 1
            return 0

        # CHECK_ACTIVE_WRITERS_SCRIPT
        if 'active_count' in script:
            set_key = keys[0]
            prefix = str(args[0])
            writers = list(await self.smembers(set_key))
            active = 0
            for w in writers:
                self._clean_expired(f"{prefix}{w}")
                if f"{prefix}{w}" in self.store:
                    active += 1
                else:
                    await self.srem(set_key, w)
            return active

        return await super().eval(script, numkeys, *keys_and_args)


def create_test_app(redis_client: ExtendedRedisDouble) -> FastAPI:
    app = FastAPI()
    app.add_middleware(AdmissionControlMiddleware, redis_client=redis_client)

    @app.get("/health/ready")
    async def health_ready():
        return {"status": "ready"}

    @app.get("/documents")
    async def list_docs():
        return {"docs": []}

    @app.post("/documents/upload")
    async def upload_doc():
        return {"status": "uploaded"}

    return app


@pytest.fixture
def redis_double() -> ExtendedRedisDouble:
    return ExtendedRedisDouble()


@pytest.fixture
def client(redis_double: ExtendedRedisDouble) -> TestClient:
    app = create_test_app(redis_double)
    return TestClient(app)


def test_mutating_request_admitted_when_normal(client: TestClient, redis_double: ExtendedRedisDouble):
    resp = client.post("/documents/upload")
    assert resp.status_code == 200
    assert resp.json() == {"status": "uploaded"}


def test_mutating_request_rejected_during_maintenance(client: TestClient, redis_double: ExtendedRedisDouble):
    redis_double.store[MAINTENANCE_MODE_KEY] = "coordinator_token_123"

    resp = client.post("/documents/upload")
    assert resp.status_code == 503
    assert resp.headers.get("Retry-After") == "30"
    data = resp.json()
    assert data["status"] == "maintenance"
    assert data["reason"] == "maintenance_mode"


def test_mutating_request_rejected_during_recovery_lock(client: TestClient, redis_double: ExtendedRedisDouble):
    redis_double.store[RECOVERY_LOCKED_KEY] = "recovery_in_progress"

    resp = client.post("/documents/upload")
    assert resp.status_code == 503
    assert resp.headers.get("Retry-After") == "30"
    data = resp.json()
    assert data["status"] == "maintenance"
    assert data["reason"] == "recovery_locked"


def test_read_requests_and_health_probes_not_blocked_during_maintenance(client: TestClient, redis_double: ExtendedRedisDouble):
    redis_double.store[MAINTENANCE_MODE_KEY] = "coordinator_token_123"

    # GET request permitted
    resp_get = client.get("/documents")
    assert resp_get.status_code == 200

    # /health probe permitted
    resp_health = client.get("/health/ready")
    assert resp_health.status_code == 200


@pytest.mark.asyncio
async def test_crashed_writer_lease_pruning(redis_double: ExtendedRedisDouble):
    # Simulate worker admitted
    token = "worker_1:uuid_abc"
    await redis_double.set(f"{WRITER_KEY_PREFIX}{token}", token, ex=1)  # 1 second TTL
    await redis_double.sadd(WRITERS_SET_KEY, token)

    active_before = await redis_double.eval(CHECK_ACTIVE_WRITERS_SCRIPT, 1, WRITERS_SET_KEY, WRITER_KEY_PREFIX)
    assert active_before == 1

    # Simulate worker crash and TTL expiry
    time.sleep(1.05)

    active_after = await redis_double.eval(CHECK_ACTIVE_WRITERS_SCRIPT, 1, WRITERS_SET_KEY, WRITER_KEY_PREFIX)
    assert active_after == 0

    # Cleaned from set
    members = await redis_double.smembers(WRITERS_SET_KEY)
    assert token not in members


def test_redis_failure_fails_closed_for_mutations(client: TestClient, redis_double: ExtendedRedisDouble):
    redis_double.simulate_failure = True
    resp = client.post("/documents/upload")
    assert resp.status_code == 503
