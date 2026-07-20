"""OpenRouter LLM provider implementation.

Implements the LLMProvider interface for OpenRouter (supporting Anthropic, OpenAI,
Groq, Mistral, and other models via unified API).
"""

from collections.abc import AsyncIterator
import json
from typing import Any

import httpx
import structlog

from backend.ai.interfaces.llm_provider import LLMProvider, LLMRequest, LLMResponse
from backend.core.config import get_settings
from backend.core.exceptions import LLMProviderException

logger = structlog.get_logger(__name__)


class OpenRouterProvider(LLMProvider):
    """OpenRouter implementation of LLMProvider.

    Uses async HTTP requests against OpenRouter's OpenAI-compatible chat completion API.
    Supports model switching, streaming, and full token usage tracking.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._settings = settings.openrouter
        self._http_client = http_client
        self._headers = {
            "Authorization": f"Bearer {self._settings.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://raguard.ai",
            "X-Title": "RAGuard AI",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is not None:
            return self._http_client
        # Return a fresh or managed client; call site can inject client or use default
        return httpx.AsyncClient(timeout=self._settings.request_timeout)

    def _build_payload(self, request: LLMRequest, stream: bool = False) -> dict[str, Any]:
        messages = []
        if request.system_instruction:
            messages.append({"role": "system", "content": request.system_instruction})
        messages.append({"role": "user", "content": request.prompt})

        model_name = self._settings.lite_model if request.use_lite_model else self._settings.model
        temperature = (
            request.temperature if request.temperature is not None else self._settings.temperature
        )
        max_tokens = (
            request.max_output_tokens
            if request.max_output_tokens is not None
            else self._settings.max_output_tokens
        )

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if stream:
            payload["stream"] = True
        return payload

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response using OpenRouter API."""
        payload = self._build_payload(request, stream=False)
        model_name = payload["model"]
        url = f"{self._settings.base_url.rstrip('/')}/chat/completions"

        client_to_close: httpx.AsyncClient | None = None
        client = self._http_client
        if client is None:
            client_to_close = httpx.AsyncClient(timeout=self._settings.request_timeout)
            client = client_to_close

        try:
            response = await client.post(url, headers=self._headers, json=payload)
            if response.status_code != 200:
                error_body = response.text
                logger.error(
                    "OpenRouter API error response",
                    status_code=response.status_code,
                    error=error_body,
                    model=model_name,
                )
                raise LLMProviderException(
                    message=f"OpenRouter API returned status {response.status_code}: {error_body}",
                    detail={"model": model_name, "status_code": response.status_code},
                )

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise LLMProviderException(
                    message="OpenRouter API returned no completion choices",
                    detail={"model": model_name, "response": data},
                )

            content = choices[0].get("message", {}).get("content", "") or ""
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            return LLMResponse(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_used=model_name,
                metadata={"raw_model": data.get("model", model_name)},
            )
        except LLMProviderException:
            raise
        except Exception as exc:
            logger.error("OpenRouter request failed", error=str(exc), model=model_name)
            raise LLMProviderException(
                message=f"OpenRouter provider error: {exc}",
                detail={"model": model_name},
            ) from exc
        finally:
            if client_to_close is not None:
                await client_to_close.aclose()

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream response tokens as they arrive from OpenRouter API."""
        payload = self._build_payload(request, stream=True)
        model_name = payload["model"]
        url = f"{self._settings.base_url.rstrip('/')}/chat/completions"

        client_to_close: httpx.AsyncClient | None = None
        client = self._http_client
        if client is None:
            client_to_close = httpx.AsyncClient(timeout=self._settings.request_timeout)
            client = client_to_close

        try:
            async with client.stream("POST", url, headers=self._headers, json=payload) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise LLMProviderException(
                        message=f"OpenRouter stream status {response.status_code}: {error_body.decode('utf-8', errors='ignore')}",
                        detail={"model": model_name, "status_code": response.status_code},
                    )

                async for line in response.aiter_lines():
                    clean_line = line.strip()
                    if not clean_line or not clean_line.startswith("data: "):
                        continue
                    data_str = clean_line[len("data: "):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            token = delta.get("content")
                            if token:
                                yield token
                    except json.JSONDecodeError:
                        continue
        except LLMProviderException:
            raise
        except Exception as exc:
            logger.error("OpenRouter stream failed", error=str(exc), model=model_name)
            raise LLMProviderException(
                message=f"OpenRouter streaming error: {exc}",
                detail={"model": model_name},
            ) from exc
        finally:
            if client_to_close is not None:
                await client_to_close.aclose()

    async def health_check(self) -> bool:
        """Verify OpenRouter API connectivity by probing the models endpoint."""
        url = f"{self._settings.base_url.rstrip('/')}/models"
        client_to_close: httpx.AsyncClient | None = None
        client = self._http_client
        if client is None:
            client_to_close = httpx.AsyncClient(timeout=10)
            client = client_to_close

        try:
            response = await client.get(url, headers=self._headers)
            return response.status_code == 200
        except Exception as exc:
            logger.warning("OpenRouter health check failed", error=str(exc))
            return False
        finally:
            if client_to_close is not None:
                await client_to_close.aclose()
