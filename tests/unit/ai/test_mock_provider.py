"""Unit tests for MockLLMProvider and Fail-Closed Production Guard.

WP-3D: TSK-3D-01 — Mock LLM Provider & Production Guard.
"""

import asyncio
import os
import time
from unittest.mock import patch

import pytest

from backend.ai.factory import create_llm_provider
from backend.ai.interfaces.llm_provider import LLMRequest
from backend.ai.providers.mock_provider import MockLLMProvider
from backend.ai.registry import ProviderRegistry
from backend.core.config.llm_manager import LLMManagerSettings
from backend.core.exceptions import LLMProviderException


@pytest.fixture(autouse=True)
def clean_environment():
    """Ensure non-production environment defaults for tests."""
    original_env = os.environ.get("ENVIRONMENT")
    original_app_env = os.environ.get("APP_ENVIRONMENT")
    original_mock = os.environ.get("MOCK_LLM_PROVIDER")

    os.environ["ENVIRONMENT"] = "testing"
    os.environ["APP_ENVIRONMENT"] = "testing"
    os.environ["MOCK_LLM_PROVIDER"] = "true"

    yield

    if original_env is not None:
        os.environ["ENVIRONMENT"] = original_env
    else:
        os.environ.pop("ENVIRONMENT", None)

    if original_app_env is not None:
        os.environ["APP_ENVIRONMENT"] = original_app_env
    else:
        os.environ.pop("APP_ENVIRONMENT", None)

    if original_mock is not None:
        os.environ["MOCK_LLM_PROVIDER"] = original_mock
    else:
        os.environ.pop("MOCK_LLM_PROVIDER", None)


@pytest.mark.asyncio
async def test_mock_provider_generate_deterministic():
    """Verify non-streaming generate returns deterministic content and valid token counts."""
    provider = MockLLMProvider(
        ttft_delay_seconds=0.01,
        canned_response="Veritas RAG deterministic test response.",
    )

    request = LLMRequest(prompt="What is Veritas RAG?")
    response = await provider.generate(request)

    assert response.content == "Veritas RAG deterministic test response."
    assert response.model_used == "mock-deterministic-llm"
    assert response.input_tokens > 0
    assert response.output_tokens == len("Veritas RAG deterministic test response.".split())
    assert response.total_tokens == response.input_tokens + response.output_tokens
    assert response.metadata.get("mock") is True


@pytest.mark.asyncio
async def test_mock_provider_streaming_pacing():
    """Verify stream yields all tokens with simulated TTFT delay and inter-token pacing."""
    provider = MockLLMProvider(
        ttft_delay_seconds=0.05,
        token_delay_seconds=0.01,
        canned_response="Alpha Beta Gamma",
    )

    request = LLMRequest(prompt="Test stream")
    start = time.perf_counter()
    chunks = []
    async for chunk in provider.stream(request):
        chunks.append(chunk)
    elapsed = time.perf_counter() - start

    assert "".join(chunks) == "Alpha Beta Gamma"
    assert len(chunks) == 3
    # Elapsed time must be at least the TTFT delay (0.05s)
    assert elapsed >= 0.045


def test_mock_provider_fail_closed_production_guard_environment_var():
    """Verify production guard raises RuntimeError if ENVIRONMENT=production."""
    os.environ["ENVIRONMENT"] = "production"

    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION.*production"):
        MockLLMProvider()


def test_mock_provider_fail_closed_production_guard_app_env_var():
    """Verify production guard raises RuntimeError if APP_ENVIRONMENT=prod."""
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["APP_ENVIRONMENT"] = "prod"

    with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION.*production"):
        MockLLMProvider()


def test_mock_provider_fail_closed_production_guard_settings():
    """Verify production guard raises RuntimeError if settings.is_production is True."""
    with patch("backend.ai.providers.mock_provider.get_settings") as mock_settings:
        mock_settings.return_value.is_production = True
        with pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION.*production"):
            MockLLMProvider()


def test_mock_provider_registry_and_factory():
    """Verify MockLLMProvider is properly registered and retrievable via factory."""
    cls = ProviderRegistry.get_provider_class("mock")
    assert cls is MockLLMProvider

    inst = create_llm_provider("mock")
    assert isinstance(inst, MockLLMProvider)


def test_mock_provider_isolation_prevents_external_fallback():
    """Verify that when mock_llm_provider=True, fallback priority is restricted exclusively to mock."""
    settings = LLMManagerSettings(
        MOCK_LLM_PROVIDER=True,
        LLM_PROVIDER_PRIORITY="openrouter,gemini",
        PRIMARY_LLM_PROVIDER="openrouter",
        FALLBACK_LLM_PROVIDER="gemini",
    )
    # Priority list must be strictly locked to ['mock'] to eliminate any chance of external billing
    assert settings.priority_list == ["mock"]


@pytest.mark.asyncio
async def test_mock_provider_simulated_failure():
    """Verify simulate_failure=True raises LLMProviderException."""
    provider = MockLLMProvider(simulate_failure=True)
    request = LLMRequest(prompt="Should fail")

    with pytest.raises(LLMProviderException, match="MockSimulatedFailure"):
        await provider.generate(request)

    with pytest.raises(LLMProviderException, match="MockSimulatedFailure"):
        async for _ in provider.stream(request):
            pass


@pytest.mark.asyncio
async def test_mock_provider_health_check():
    """Verify health check reports healthy normally and unhealthy when failure simulated."""
    healthy_provider = MockLLMProvider(simulate_failure=False)
    assert await healthy_provider.health_check() is True

    failing_provider = MockLLMProvider(simulate_failure=True)
    assert await failing_provider.health_check() is False
