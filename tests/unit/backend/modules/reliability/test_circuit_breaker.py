"""Unit Tests for CircuitBreakerEngine (`ADR-005`, `Phase 2 Milestone 5`).

Tests state transitions (`CLOSED -> OPEN -> HALF_OPEN -> CLOSED`), threshold triggering,
and administrative force-reset operations using an in-memory Redis test double.
"""

import time

import pytest

from backend.modules.reliability.circuit_breaker.engine import CircuitBreakerEngine
from backend.modules.reliability.circuit_breaker.states import CircuitState


class InMemoryRedisDouble:
    """In-memory async dictionary simulating Redis key/value and TTL behaviors for unit tests."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.expires: dict[str, float] = {}

    def _clean_expired(self, key: str) -> None:
        if key in self.expires and time.time() > self.expires[key]:
            self.store.pop(key, None)
            self.expires.pop(key, None)

    async def get(self, key: str) -> str | None:
        self._clean_expired(key)
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = str(value)
        if ex is not None:
            self.expires[key] = time.time() + ex
        else:
            self.expires.pop(key, None)
        return True

    async def incr(self, key: str) -> int:
        self._clean_expired(key)
        val = int(self.store.get(key, "0")) + 1
        self.store[key] = str(val)
        return val

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self.store:
                self.store.pop(k, None)
                self.expires.pop(k, None)
                count += 1
        return count

    async def expire(self, key: str, seconds: int) -> bool:
        if key in self.store:
            self.expires[key] = time.time() + seconds
            return True
        return False

    async def ttl(self, key: str) -> int:
        self._clean_expired(key)
        if key not in self.store:
            return -2
        if key not in self.expires:
            return -1
        remaining = int(self.expires[key] - time.time())
        return max(0, remaining)


@pytest.fixture
def redis_double() -> InMemoryRedisDouble:
    return InMemoryRedisDouble()


@pytest.fixture
def engine(redis_double: InMemoryRedisDouble) -> CircuitBreakerEngine:
    return CircuitBreakerEngine(
        redis_client=redis_double,  # type: ignore[arg-type]
        failure_threshold=3,
        recovery_threshold=2,
        cooldown_seconds=1,
    )


@pytest.mark.asyncio
async def test_initial_state_closed(engine: CircuitBreakerEngine) -> None:
    state = await engine.check_state("tenant_a", "qdrant_hybrid")
    assert state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_failure_threshold_trips_to_open(engine: CircuitBreakerEngine) -> None:
    state1 = await engine.record_failure("tenant_a", "qdrant_hybrid", "RET_004")
    assert state1 == CircuitState.CLOSED

    state2 = await engine.record_failure("tenant_a", "qdrant_hybrid", "RET_004")
    assert state2 == CircuitState.CLOSED

    state3 = await engine.record_failure("tenant_a", "qdrant_hybrid", "RET_004")
    assert state3 == CircuitState.OPEN

    checked = await engine.check_state("tenant_a", "qdrant_hybrid")
    assert checked == CircuitState.OPEN


@pytest.mark.asyncio
async def test_cooldown_decay_transitions_to_half_open(engine: CircuitBreakerEngine) -> None:
    for _ in range(3):
        await engine.record_failure("tenant_b", "qdrant_hybrid", "RET_004")

    assert await engine.check_state("tenant_b", "qdrant_hybrid") == CircuitState.OPEN

    # Wait for cooldown_seconds (1s) to expire
    time.sleep(1.1)

    checked = await engine.check_state("tenant_b", "qdrant_hybrid")
    assert checked == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_recovery_to_closed(engine: CircuitBreakerEngine) -> None:
    for _ in range(3):
        await engine.record_failure("tenant_c", "qdrant_hybrid", "RET_004")
    time.sleep(1.1)
    assert await engine.check_state("tenant_c", "qdrant_hybrid") == CircuitState.HALF_OPEN

    # First success probe while HALF_OPEN
    await engine.record_success("tenant_c", "qdrant_hybrid")
    assert await engine.check_state("tenant_c", "qdrant_hybrid") == CircuitState.HALF_OPEN

    # Second success probe meets recovery_threshold=2 -> CLOSED
    await engine.record_success("tenant_c", "qdrant_hybrid")
    assert await engine.check_state("tenant_c", "qdrant_hybrid") == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_failure_retrips_to_open(engine: CircuitBreakerEngine) -> None:
    for _ in range(3):
        await engine.record_failure("tenant_d", "qdrant_hybrid", "RET_004")
    time.sleep(1.1)
    assert await engine.check_state("tenant_d", "qdrant_hybrid") == CircuitState.HALF_OPEN

    state = await engine.record_failure("tenant_d", "qdrant_hybrid", "RET_004")
    assert state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_force_reset(engine: CircuitBreakerEngine) -> None:
    for _ in range(3):
        await engine.record_failure("tenant_e", "qdrant_hybrid", "RET_004")
    assert await engine.check_state("tenant_e", "qdrant_hybrid") == CircuitState.OPEN

    reset_res = await engine.force_reset("tenant_e", "qdrant_hybrid")
    assert reset_res is True
    assert await engine.check_state("tenant_e", "qdrant_hybrid") == CircuitState.CLOSED
