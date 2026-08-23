"""Targeted unit tests for LLM provider priority configuration and routing (ISS-010)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.ai.interfaces.llm_provider import LLMRequest, LLMResponse
from backend.ai.manager import LLMProviderManager
from backend.ai.registry import ProviderRegistry
from backend.core.config.llm_manager import LLMManagerSettings


def test_llm_010_01_default_provider_priority():
    """LLM-010-01: Default provider priority list is [openrouter, gemini]."""
    settings = LLMManagerSettings(_env_file=None)
    assert settings.priority_list == ["openrouter", "gemini"]


def test_llm_010_02_default_primary_provider():
    """LLM-010-02: Default primary provider is openrouter."""
    settings = LLMManagerSettings(_env_file=None)
    assert settings.primary_provider == "openrouter"


def test_llm_010_03_default_fallback_provider():
    """LLM-010-03: Default fallback provider is gemini."""
    settings = LLMManagerSettings(_env_file=None)
    assert settings.fallback_provider == "gemini"


def test_llm_010_04_explicit_provider_priority_env_override():
    """LLM-010-04: Explicit LLM_PROVIDER_PRIORITY override is respected."""
    with patch.dict("os.environ", {"LLM_PROVIDER_PRIORITY": "gemini,openrouter"}):
        settings = LLMManagerSettings()
        assert settings.priority_list == ["gemini", "openrouter"]


def test_llm_010_05_explicit_primary_provider_override():
    """LLM-010-05: Explicit PRIMARY_LLM_PROVIDER override is respected when priority raw is empty."""
    settings = LLMManagerSettings(provider_priority_raw="", primary_provider="custom_llm", fallback_provider="gemini", _env_file=None)
    assert settings.priority_list == ["custom_llm", "gemini"]


def test_llm_010_06_explicit_fallback_provider_override():
    """LLM-010-06: Explicit FALLBACK_LLM_PROVIDER override is respected when priority raw is empty."""
    settings = LLMManagerSettings(provider_priority_raw="", primary_provider="openrouter", fallback_provider="custom_fallback", _env_file=None)
    assert settings.priority_list == ["openrouter", "custom_fallback"]


def test_llm_010_07_disabled_v1_engine_excluded_from_default_priority():
    """LLM-010-07: v1_engine is not present in default provider priority list."""
    settings = LLMManagerSettings(_env_file=None)
    assert "v1_engine" not in settings.priority_list


@pytest.mark.asyncio
async def test_llm_010_08_provider_manager_resolves_openrouter_first():
    """LLM-010-08: LLMProviderManager routes to OpenRouter on initial request attempt."""
    manager = LLMProviderManager()
    manager._settings = LLMManagerSettings(_env_file=None)

    mock_openrouter = AsyncMock()
    mock_openrouter.generate.return_value = LLMResponse(
        content="OpenRouter generation result",
        input_tokens=10,
        output_tokens=20,
        model_used="openrouter/anthropic/claude-3.5-sonnet",
    )

    with patch.object(ProviderRegistry, "get_provider", return_value=mock_openrouter) as mock_get_provider:
        req = LLMRequest(prompt="Test prompt", system_instruction="System prompt", tenant_id="tenant-1", workspace_id="ws-1")
        resp = await manager.generate(req)

        assert mock_get_provider.call_args[0][0] == "openrouter"
        assert resp.content == "OpenRouter generation result"
        assert resp.model_used == "openrouter/anthropic/claude-3.5-sonnet"


@pytest.mark.asyncio
async def test_llm_010_09_gemini_fallback_on_openrouter_failure():
    """LLM-010-09: LLMProviderManager falls back to Gemini when OpenRouter fails."""
    manager = LLMProviderManager()
    manager._settings = LLMManagerSettings(max_retries=0, _env_file=None)

    mock_openrouter = AsyncMock()
    mock_openrouter.generate.side_effect = RuntimeError("OpenRouter 503 Service Unavailable")

    mock_gemini = AsyncMock()
    mock_gemini.generate.return_value = LLMResponse(
        content="Gemini fallback response",
        input_tokens=10,
        output_tokens=15,
        model_used="gemini-1.5-pro",
    )

    def mock_registry_lookup(provider_name):
        if provider_name == "openrouter":
            return mock_openrouter
        if provider_name == "gemini":
            return mock_gemini
        raise ValueError(f"Unknown provider {provider_name}")

    with patch.object(ProviderRegistry, "get_provider", side_effect=mock_registry_lookup):
        req = LLMRequest(prompt="Test prompt", system_instruction="System prompt", tenant_id="tenant-1", workspace_id="ws-1")
        resp = await manager.generate(req)

        assert resp.content == "Gemini fallback response"
        assert resp.model_used == "gemini-1.5-pro"


def test_llm_010_10_provider_registry_backward_compatibility():
    """LLM-010-10: ProviderRegistry preserves registration of all supported providers including v1_engine."""
    from backend.ai.providers.gemini import GeminiProvider
    from backend.ai.providers.openrouter import OpenRouterProvider
    from backend.ai.providers.v1_engine.provider import V1EngineProvider

    assert ProviderRegistry.get_provider_class("openrouter") == OpenRouterProvider
    assert ProviderRegistry.get_provider_class("gemini") == GeminiProvider
    assert ProviderRegistry.get_provider_class("v1_engine") == V1EngineProvider
