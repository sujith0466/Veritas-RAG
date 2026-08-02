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
            "Authorization": f"Bearer {self._settings.resolved_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://raguard.ai",
            "X-Title": "RAGuard AI",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is not None:
            return self._http_client
        # Return a fresh or managed client; call site can inject client or use default
        return httpx.AsyncClient(timeout=self._settings.request_timeout)

    def _build_payload(
        self, request: LLMRequest, model_name: str, stream: bool = False
    ) -> dict[str, Any]:
        messages = []
        if request.system_instruction:
            messages.append({"role": "system", "content": request.system_instruction})
        messages.append({"role": "user", "content": request.prompt})

        temperature = (
            request.temperature
            if request.temperature is not None
            else self._settings.temperature
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
        """Generate a response using OpenRouter API with model-level failover."""
        models = (
            self._settings.lite_models
            if request.use_lite_model
            else self._settings.models
        )
        if not models:
            raise LLMProviderException(
                message="No OpenRouter models configured.", detail={}
            )

        url = f"{self._settings.base_url.rstrip('/')}/chat/completions"
        client_to_close: httpx.AsyncClient | None = None
        client = self._http_client
        if client is None:
            client_to_close = httpx.AsyncClient(timeout=self._settings.request_timeout)
            client = client_to_close

        errors: list[dict[str, Any]] = []

        try:
            for model_name in models:
                payload = self._build_payload(request, model_name, stream=False)
                try:
                    response = await client.post(
                        url, headers=self._headers, json=payload
                    )
                    if response.status_code != 200:
                        error_body = response.text
                        logger.error(
                            "OpenRouter API error response",
                            status_code=response.status_code,
                            error=error_body,
                            model=model_name,
                        )
                        errors.append(
                            {
                                "model": model_name,
                                "error": f"Status {response.status_code}: {error_body}",
                                "status_code": response.status_code,
                            }
                        )
                        continue

                    data = response.json()
                    choices = data.get("choices", [])
                    if not choices:
                        errors.append(
                            {"model": model_name, "error": "No completion choices"}
                        )
                        continue

                    content = choices[0].get("message", {}).get("content", "") or ""
                    usage = data.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)

                    if errors:
                        logger.info(
                            "OpenRouter failover succeeded",
                            successful_model=model_name,
                            prior_failures=len(errors),
                        )

                    return LLMResponse(
                        content=content,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        model_used=model_name,
                        metadata={"raw_model": data.get("model", model_name)},
                    )
                except Exception as exc:
                    logger.warning(
                        "OpenRouter model failed, attempting next",
                        failed_model=model_name,
                        error=str(exc),
                    )
                    errors.append({"model": model_name, "error": str(exc)})

            logger.error("All OpenRouter models failed", errors=errors)
            last_status = errors[-1].get("status_code") if errors else None
            raise LLMProviderException(
                message=f"All OpenRouter models failed: {[e['model'] + ': ' + e['error'] for e in errors]}",
                detail={"errors": errors, "attempted_models": models},
                status_code=last_status,
            )
        finally:
            if client_to_close is not None:
                await client_to_close.aclose()

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream response tokens as they arrive from OpenRouter API with model-level failover."""
        models = (
            self._settings.lite_models
            if request.use_lite_model
            else self._settings.models
        )
        if not models:
            raise LLMProviderException(
                message="No OpenRouter models configured for streaming.", detail={}
            )

        url = f"{self._settings.base_url.rstrip('/')}/chat/completions"
        client_to_close: httpx.AsyncClient | None = None
        client = self._http_client
        if client is None:
            client_to_close = httpx.AsyncClient(timeout=self._settings.request_timeout)
            client = client_to_close

        errors: list[dict[str, Any]] = []

        try:
            for model_name in models:
                payload = self._build_payload(request, model_name, stream=True)
                chunks_yielded = 0
                try:
                    async with client.stream(
                        "POST", url, headers=self._headers, json=payload
                    ) as response:
                        if response.status_code != 200:
                            error_body = await response.aread()
                            errors.append(
                                {
                                    "model": model_name,
                                    "error": f"Status {response.status_code}: {error_body.decode('utf-8', errors='ignore')}",
                                    "status_code": response.status_code,
                                }
                            )
                            continue

                        async for line in response.aiter_lines():
                            clean_line = line.strip()
                            if not clean_line or not clean_line.startswith("data: "):
                                continue
                            data_str = clean_line[len("data: ") :].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                choices = chunk.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    token = delta.get("content")
                                    if token:
                                        chunks_yielded += 1
                                        yield token
                            except json.JSONDecodeError:
                                continue

                        if errors:
                            logger.info(
                                "OpenRouter stream failover succeeded",
                                successful_model=model_name,
                                prior_failures=len(errors),
                            )
                        return
                except Exception as exc:
                    if chunks_yielded > 0:
                        logger.error(
                            "OpenRouter stream failed mid-generation",
                            failed_model=model_name,
                            error=str(exc),
                        )
                        raise LLMProviderException(
                            message=f"Stream aborted mid-generation from {model_name}: {exc}",
                            detail={
                                "failed_model": model_name,
                                "chunks_yielded": chunks_yielded,
                            },
                        ) from exc
                    logger.warning(
                        "OpenRouter model stream init failed, attempting next",
                        failed_model=model_name,
                        error=str(exc),
                    )
                    errors.append({"model": model_name, "error": str(exc)})

            logger.error("All OpenRouter models failed for stream", errors=errors)
            last_status = errors[-1].get("status_code") if errors else None
            raise LLMProviderException(
                message=f"All OpenRouter models failed for streaming: {[e['model'] + ': ' + e['error'] for e in errors]}",
                detail={"errors": errors, "attempted_models": models},
                status_code=last_status,
            )
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
