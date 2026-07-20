"""Unit tests for the AI Provider Abstraction Layer (Gemini implementation & factory)."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.ai.factory import create_llm_provider
from backend.ai.interfaces.llm_provider import LLMProvider, LLMRequest, LLMResponse
from backend.ai.providers.gemini import GeminiProvider
from backend.core.exceptions import LLMProviderException


@pytest.mark.unit
class TestLLMDataclasses:
    def test_llm_request_defaults(self) -> None:
        req = LLMRequest(prompt="Hello RAGuard")
        assert req.prompt == "Hello RAGuard"
        assert req.system_instruction is None
        assert req.temperature is None
        assert req.max_output_tokens is None
        assert req.use_lite_model is False

    def test_llm_response_total_tokens(self) -> None:
        resp = LLMResponse(
            content="Generated answer",
            input_tokens=15,
            output_tokens=35,
            model_used="gemini-2.0-flash",
        )
        assert resp.total_tokens == 50


@pytest.mark.unit
class TestGeminiProvider:
    @patch("backend.ai.providers.gemini.genai")
    def test_init_configures_genai(self, mock_genai: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")
        from backend.core.config import get_settings
        get_settings.cache_clear()

        provider = GeminiProvider()
        mock_genai.configure.assert_called_once_with(api_key="fake-key-for-test")
        assert isinstance(provider, LLMProvider)

    @patch("backend.ai.providers.gemini.genai")
    @pytest.mark.asyncio
    async def test_generate_primary_model(self, mock_genai: MagicMock) -> None:
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Here is the summary."
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider()
        req = LLMRequest(
            prompt="Summarize this",
            system_instruction="You are an expert",
            temperature=0.2,
            max_output_tokens=512,
            use_lite_model=False,
        )

        resp = await provider.generate(req)

        mock_genai.GenerativeModel.assert_called_with(
            model_name="gemini-2.0-flash",
            generation_config=mock_genai.GenerationConfig(),
        )
        mock_model.generate_content.assert_called_once()
        assert resp.content == "Here is the summary."
        assert resp.input_tokens == 10
        assert resp.output_tokens == 20
        assert resp.model_used == "gemini-2.0-flash"

    @patch("backend.ai.providers.gemini.genai")
    @pytest.mark.asyncio
    async def test_generate_lite_model(self, mock_genai: MagicMock) -> None:
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "INTENT_CLASSIFIED"
        mock_response.usage_metadata.prompt_token_count = 5
        mock_response.usage_metadata.candidates_token_count = 3
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider()
        req = LLMRequest(prompt="Classify this", use_lite_model=True)

        resp = await provider.generate(req)

        mock_genai.GenerativeModel.assert_called_with(
            model_name="gemini-2.0-flash-lite",
            generation_config=mock_genai.GenerationConfig(),
        )
        assert resp.content == "INTENT_CLASSIFIED"
        assert resp.model_used == "gemini-2.0-flash-lite"

    @patch("backend.ai.providers.gemini.genai")
    @pytest.mark.asyncio
    async def test_generate_wraps_api_errors(self, mock_genai: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = RuntimeError("API Rate limit hit")
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider()
        with pytest.raises(LLMProviderException) as exc_info:
            await provider.generate(LLMRequest(prompt="Hello"))

        assert "Gemini provider error" in str(exc_info.value)
        assert exc_info.value.error_code == "EXT_002"
        assert exc_info.value.detail["model"] == "gemini-2.0-flash"

    @patch("backend.ai.providers.gemini.genai")
    @pytest.mark.asyncio
    async def test_stream_tokens(self, mock_genai: MagicMock) -> None:
        mock_model = MagicMock()
        chunk1 = MagicMock(text="Hello ")
        chunk2 = MagicMock(text="World!")
        mock_model.generate_content.return_value = [chunk1, chunk2]
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider()
        tokens = []
        async for token in provider.stream(LLMRequest(prompt="Say hi")):
            tokens.append(token)

        assert tokens == ["Hello ", "World!"]

    @patch("backend.ai.providers.gemini.genai")
    @pytest.mark.asyncio
    async def test_stream_wraps_errors(self, mock_genai: MagicMock) -> None:
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("Connection reset")
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider()
        with pytest.raises(LLMProviderException) as exc_info:
            async for _ in provider.stream(LLMRequest(prompt="test")):
                pass
        assert "Gemini streaming error" in str(exc_info.value)

    @patch("backend.ai.providers.gemini.genai")
    @pytest.mark.asyncio
    async def test_health_check_success_and_failure(self, mock_genai: MagicMock) -> None:
        mock_model = MagicMock()
        mock_response = MagicMock(text="pong")
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider()
        assert await provider.health_check() is True

        # Now simulate failure
        mock_model.generate_content.side_effect = Exception("Timeout")
        assert await provider.health_check() is False


@pytest.mark.unit
class TestProviderRegistry:
    def test_registry_lookup_and_instantiation(self) -> None:
        from backend.ai.providers.openrouter import OpenRouterProvider
        from backend.ai.registry import ProviderRegistry

        assert ProviderRegistry.get_provider_class("gemini") is GeminiProvider
        assert ProviderRegistry.get_provider_class("openrouter") is OpenRouterProvider

        assert "gemini" in ProviderRegistry.list_providers()
        assert "openrouter" in ProviderRegistry.list_providers()

    def test_unknown_provider_raises(self) -> None:
        from backend.ai.registry import ProviderRegistry

        with pytest.raises(ValueError) as exc_info:
            ProviderRegistry.get_provider("nonexistent")
        assert "Unknown LLM provider 'nonexistent'" in str(exc_info.value)


@pytest.mark.unit
class TestOpenRouterProvider:
    @pytest.mark.asyncio
    async def test_generate_success(self) -> None:
        from httpx import AsyncClient, Response

        from backend.ai.providers.openrouter import OpenRouterProvider

        mock_http = MagicMock(spec=AsyncClient)
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "anthropic/claude-3.5-sonnet",
            "choices": [{"message": {"content": "OpenRouter summary output"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 25},
        }
        mock_http.post.return_value = mock_response

        provider = OpenRouterProvider(http_client=mock_http)
        resp = await provider.generate(LLMRequest(prompt="Summarize"))

        assert resp.content == "OpenRouter summary output"
        assert resp.input_tokens == 12
        assert resp.output_tokens == 25
        assert resp.model_used == "anthropic/claude-3.5-sonnet"

    @pytest.mark.asyncio
    async def test_generate_api_error_raises(self) -> None:
        from httpx import AsyncClient, Response

        from backend.ai.providers.openrouter import OpenRouterProvider

        mock_http = MagicMock(spec=AsyncClient)
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_http.post.return_value = mock_response

        provider = OpenRouterProvider(http_client=mock_http)
        with pytest.raises(LLMProviderException) as exc_info:
            await provider.generate(LLMRequest(prompt="Hello"))

        assert "status 429" in str(exc_info.value)
        assert exc_info.value.detail["status_code"] == 429

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        from httpx import AsyncClient, Response

        from backend.ai.providers.openrouter import OpenRouterProvider

        mock_http = MagicMock(spec=AsyncClient)
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200
        mock_http.get.return_value = mock_response

        provider = OpenRouterProvider(http_client=mock_http)
        assert await provider.health_check() is True

        mock_response.status_code = 500
        assert await provider.health_check() is False


@pytest.mark.unit
class TestLLMProviderManager:
    @pytest.mark.asyncio
    async def test_generate_primary_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.ai.manager import LLMProviderManager
        from backend.ai.registry import ProviderRegistry

        monkeypatch.setenv("LLM_PROVIDER_PRIORITY", "openrouter,gemini")
        from backend.core.config import get_settings
        get_settings.cache_clear()

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = LLMResponse(
            content="Primary output", input_tokens=1, output_tokens=1, model_used="mock"
        )

        with patch.object(ProviderRegistry, "get_provider", return_value=mock_provider) as mock_get:
            manager = LLMProviderManager()
            resp = await manager.generate(LLMRequest(prompt="Hello"))
            assert resp.content == "Primary output"
            mock_get.assert_called_once_with("openrouter")

    @pytest.mark.asyncio
    async def test_generate_failover_to_secondary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.ai.manager import LLMProviderManager
        from backend.ai.registry import ProviderRegistry

        monkeypatch.setenv("LLM_PROVIDER_PRIORITY", "openrouter,gemini")
        from backend.core.config import get_settings
        get_settings.cache_clear()

        mock_primary = MagicMock(spec=LLMProvider)
        mock_primary.generate.side_effect = LLMProviderException("Primary 503")

        mock_secondary = MagicMock(spec=LLMProvider)
        mock_secondary.generate.return_value = LLMResponse(
            content="Fallback output", input_tokens=2, output_tokens=2, model_used="gemini-fallback"
        )

        def mock_get_provider(name: str, **kwargs: Any) -> LLMProvider:
            if name == "openrouter":
                return mock_primary
            if name == "gemini":
                return mock_secondary
            raise ValueError(f"Unexpected {name}")

        with patch.object(ProviderRegistry, "get_provider", side_effect=mock_get_provider):
            manager = LLMProviderManager()
            resp = await manager.generate(LLMRequest(prompt="Hello"))
            assert resp.content == "Fallback output"
            assert resp.model_used == "gemini-fallback"

    @pytest.mark.asyncio
    async def test_generate_all_providers_fail_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.ai.manager import LLMProviderManager
        from backend.ai.registry import ProviderRegistry

        monkeypatch.setenv("LLM_PROVIDER_PRIORITY", "openrouter,gemini")
        from backend.core.config import get_settings
        get_settings.cache_clear()

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.side_effect = LLMProviderException("Provider error")

        with patch.object(ProviderRegistry, "get_provider", return_value=mock_provider):
            manager = LLMProviderManager()
            with pytest.raises(LLMProviderException) as exc_info:
                await manager.generate(LLMRequest(prompt="Hello"))
            assert "All configured LLM providers failed" in str(exc_info.value)


@pytest.mark.unit
class TestLLMProviderFactory:
    @patch("backend.ai.providers.gemini.genai")
    def test_create_llm_provider_default_and_explicit(self, mock_genai: MagicMock) -> None:
        from backend.ai.manager import LLMProviderManager
        from backend.ai.providers.openrouter import OpenRouterProvider

        provider_default = create_llm_provider()
        assert isinstance(provider_default, LLMProviderManager)

        provider_manager = create_llm_provider("manager")
        assert isinstance(provider_manager, LLMProviderManager)

        provider_gemini = create_llm_provider("gemini")
        assert isinstance(provider_gemini, GeminiProvider)

        provider_openrouter = create_llm_provider("openrouter")
        assert isinstance(provider_openrouter, OpenRouterProvider)

    def test_create_llm_provider_unknown_raises(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            create_llm_provider("unknown_provider")
        assert "Unknown LLM provider 'unknown_provider'" in str(exc_info.value)
