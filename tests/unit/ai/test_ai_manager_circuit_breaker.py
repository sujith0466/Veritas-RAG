"""Unit tests for LLMProviderManager Circuit Breaker integration (`WP-3C Phase 1`).

Tests:
- Pre-stream failover when chunks_yielded == 0
- Mid-stream abort with zero provider stitching when chunks_yielded > 0
- Fast-fail routing when circuit breaker is OPEN
- Canary exclusivity lock (SET NX EX 15) when circuit breaker is HALF_OPEN
- Single-canary lifecycle (success recovers breaker, failure re-trips)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.ai.interfaces.llm_provider import LLMProvider, LLMRequest, LLMResponse
from backend.ai.manager import LLMProviderManager
from backend.ai.registry import ProviderRegistry
from backend.modules.reliability.circuit_breaker.engine import (
    CircuitBreakerEngine,
)
from backend.modules.reliability.circuit_breaker.states import CircuitState
from tests.unit.backend.modules.reliability.test_circuit_breaker import (
    InMemoryRedisDouble,
)


class MockTestProvider(LLMProvider):
    """Mock LLM provider for unit testing streaming and generate failure/failover flows."""

    def __init__(
        self,
        name: str,
        chunks: list[str] | None = None,
        fail_at_chunk: int | None = None,
        fail_on_init: bool = False,
        response_text: str = "Mock response",
    ) -> None:
        self.name = name
        self.chunks = chunks or ["Hello", " world", "!"]
        self.fail_at_chunk = fail_at_chunk
        self.fail_on_init = fail_on_init
        self.response_text = response_text
        self.stream_call_count = 0
        self.generate_call_count = 0

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.generate_call_count += 1
        if self.fail_on_init:
            from backend.core.exceptions import LLMProviderException

            raise LLMProviderException(
                f"{self.name} generate failed", status_code=503
            )
        return LLMResponse(
            content=self.response_text,
            model_used=self.name,
            total_tokens=10,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        self.stream_call_count += 1
        if self.fail_on_init:
            from backend.core.exceptions import LLMProviderException

            raise LLMProviderException(
                f"{self.name} connection refused", status_code=503
            )

        for i, chunk in enumerate(self.chunks):
            if self.fail_at_chunk is not None and i >= self.fail_at_chunk:
                from backend.core.exceptions import LLMProviderException

                raise LLMProviderException(
                    f"{self.name} connection dropped mid-stream",
                    status_code=500,
                )
            yield chunk

    async def health_check(self) -> bool:
        return not self.fail_on_init


@pytest.fixture
def redis_double() -> InMemoryRedisDouble:
    return InMemoryRedisDouble()


@pytest.fixture
def circuit_breaker(redis_double: InMemoryRedisDouble) -> CircuitBreakerEngine:
    return CircuitBreakerEngine(
        redis_client=redis_double,  # type: ignore[arg-type]
        failure_threshold=3,
        recovery_threshold=1,
        cooldown_seconds=60,
    )


@pytest.fixture
def mock_settings() -> Any:
    settings = MagicMock()
    settings.priority_list = ["primary_provider", "fallback_provider"]
    settings.max_retries = 0  # 0 retries to test direct failover
    settings.retry_initial_delay = 0.01
    return settings


@pytest.fixture
def ai_manager(
    circuit_breaker: CircuitBreakerEngine, mock_settings: Any
) -> LLMProviderManager:
    with patch(
        "backend.ai.manager.get_settings",
        return_value=MagicMock(ai=mock_settings),
    ):
        manager = LLMProviderManager(circuit_breaker=circuit_breaker)
        manager._settings = mock_settings
        return manager


@pytest.mark.asyncio
async def test_pre_stream_failover(ai_manager: LLMProviderManager) -> None:
    """Pre-stream failure (chunks_yielded == 0) routes cleanly to secondary provider."""
    primary = MockTestProvider("primary_provider", fail_on_init=True)
    fallback = MockTestProvider(
        "fallback_provider", chunks=["Fallback", " tokens"]
    )

    ProviderRegistry.register("primary_provider", lambda **kw: primary)
    ProviderRegistry.register("fallback_provider", lambda **kw: fallback)

    req = LLMRequest(prompt="Test prompt")
    collected_chunks = []
    async for chunk in ai_manager.stream(req):
        collected_chunks.append(chunk)

    assert primary.stream_call_count == 1
    assert fallback.stream_call_count == 1
    assert collected_chunks == ["Fallback", " tokens"]

    # Verify failure recorded on primary circuit breaker
    state = await ai_manager.circuit_breaker.check_state(
        "system", "primary_provider"
    )
    # 1 failure out of 3 -> still CLOSED
    assert state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_mid_stream_abort_zero_provider_stitching(
    ai_manager: LLMProviderManager,
) -> None:
    """Mid-stream failure (chunks_yielded > 0) aborts immediately; zero provider stitching."""
    from backend.core.exceptions import LLMProviderException

    primary = MockTestProvider(
        "primary_provider",
        chunks=["Part 1", " Part 2", " Part 3"],
        fail_at_chunk=1,
    )
    fallback = MockTestProvider(
        "fallback_provider", chunks=["Should", " not", " run"]
    )

    ProviderRegistry.register("primary_provider", lambda **kw: primary)
    ProviderRegistry.register("fallback_provider", lambda **kw: fallback)

    req = LLMRequest(prompt="Test mid-stream abort")
    collected = []

    with pytest.raises(LLMProviderException) as exc_info:
        async for chunk in ai_manager.stream(req):
            collected.append(chunk)

    # First chunk was yielded before abort
    assert collected == ["Part 1"]
    assert "Stream aborted mid-generation" in str(exc_info.value)
    assert exc_info.value.detail.get("chunks_yielded") == 1
    assert exc_info.value.detail.get("is_interrupted") is True

    # Secondary provider MUST NOT be called! Zero provider stitching
    assert fallback.stream_call_count == 0


@pytest.mark.asyncio
async def test_fast_fail_when_circuit_breaker_open(
    ai_manager: LLMProviderManager,
) -> None:
    """When primary provider breaker is OPEN, stream routes to fallback without calling primary."""
    primary = MockTestProvider("primary_provider")
    fallback = MockTestProvider("fallback_provider", chunks=["Fallback", " ok"])

    ProviderRegistry.register("primary_provider", lambda **kw: primary)
    ProviderRegistry.register("fallback_provider", lambda **kw: fallback)

    # Trip primary breaker to OPEN
    for _ in range(3):
        await ai_manager.circuit_breaker.record_failure(
            "system", "primary_provider", "503"
        )
    assert (
        await ai_manager.circuit_breaker.check_state(
            "system", "primary_provider"
        )
        == CircuitState.OPEN
    )

    req = LLMRequest(prompt="Test fast fail")
    collected = []
    async for chunk in ai_manager.stream(req):
        collected.append(chunk)

    # Primary was fast-failed with 0 calls
    assert primary.stream_call_count == 0
    assert fallback.stream_call_count == 1
    assert collected == ["Fallback", " ok"]


@pytest.mark.asyncio
async def test_canary_exclusivity_lock_when_half_open(
    ai_manager: LLMProviderManager, redis_double: InMemoryRedisDouble
) -> None:
    """When provider is HALF_OPEN, only caller acquiring canary lock runs canary; concurrent caller falls over."""
    primary = MockTestProvider("primary_provider", chunks=["Primary", " canary"])
    fallback = MockTestProvider(
        "fallback_provider", chunks=["Fallback", " bypass"]
    )

    ProviderRegistry.register("primary_provider", lambda **kw: primary)
    ProviderRegistry.register("fallback_provider", lambda **kw: fallback)

    # Set primary to HALF_OPEN
    redis_double.store["system:circuit_breaker:primary_provider:state"] = (
        CircuitState.HALF_OPEN.value
    )

    # Pre-occupy canary lock to simulate another concurrent canary probe running
    await ai_manager.circuit_breaker.acquire_canary_lock(
        "primary_provider", "other_worker_token", ttl_seconds=15
    )

    req = LLMRequest(prompt="Test concurrent canary")
    collected = []
    async for chunk in ai_manager.stream(req):
        collected.append(chunk)

    # Primary was skipped because canary lock was occupied; fell over to fallback
    assert primary.stream_call_count == 0
    assert fallback.stream_call_count == 1
    assert collected == ["Fallback", " bypass"]


@pytest.mark.asyncio
async def test_single_canary_success_recovers_circuit(
    ai_manager: LLMProviderManager, redis_double: InMemoryRedisDouble
) -> None:
    """Canary probe success in HALF_OPEN state recovers circuit to CLOSED and releases canary lock."""
    primary = MockTestProvider("primary_provider", chunks=["Canary", " success"])
    fallback = MockTestProvider("fallback_provider")

    ProviderRegistry.register("primary_provider", lambda **kw: primary)
    ProviderRegistry.register("fallback_provider", lambda **kw: fallback)

    # Set primary to HALF_OPEN
    redis_double.store["system:circuit_breaker:primary_provider:state"] = (
        CircuitState.HALF_OPEN.value
    )

    req = LLMRequest(prompt="Test canary recovery")
    collected = []
    async for chunk in ai_manager.stream(req):
        collected.append(chunk)

    assert primary.stream_call_count == 1
    assert collected == ["Canary", " success"]

    # Verify breaker recovered to CLOSED (recovery_threshold=1)
    state = await ai_manager.circuit_breaker.check_state(
        "system", "primary_provider"
    )
    assert state == CircuitState.CLOSED

    # Verify canary lock was released
    assert (
        "system:circuit_breaker:primary_provider:canary_lock"
        not in redis_double.store
    )
