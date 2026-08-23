"""Google Gemini LLM provider implementation.

Implements the LLMProvider interface for Google's Gemini models.
Business logic never imports this directly — it always uses the interface
and the factory to obtain a provider instance.
"""

from collections.abc import AsyncIterator
from typing import Any

import google.generativeai as genai
import structlog

from backend.core.config import get_settings
from backend.core.exceptions import LLMProviderException

from ..interfaces.llm_provider import LLMProvider, LLMRequest, LLMResponse

logger = structlog.get_logger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini implementation of LLMProvider.

    Uses google-generativeai SDK. Applies the principle of using cheaper
    'lite' models for classification tasks and the full model for generation.
    """

    def __init__(self) -> None:
        settings = get_settings()
        genai.configure(api_key=settings.gemini.api_key)
        self._settings = settings.gemini
        self._primary_model_name = settings.gemini.model
        self._lite_model_name = settings.gemini.lite_model

    def _get_model(self, use_lite: bool = False) -> genai.GenerativeModel:
        model_name = self._lite_model_name if use_lite else self._primary_model_name
        return genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.GenerationConfig(
                temperature=self._settings.temperature,
                max_output_tokens=self._settings.max_output_tokens,
            ),
        )

    def _build_contents(self, request: LLMRequest) -> Any:
        if not request.conversation_history:
            if request.system_instruction:
                return f"{request.system_instruction}\n\n{request.prompt}"
            return request.prompt

        contents: list[dict[str, Any]] = []
        first_user_injected = False
        for turn in request.conversation_history:
            if not isinstance(turn, dict):
                continue
            role = turn.get("role")
            content = turn.get("content") or turn.get("message")
            if role in ("user", "assistant") and content and isinstance(content, str) and content.strip():
                gemini_role = "user" if role == "user" else "model"
                turn_text = content.strip()
                if not first_user_injected and gemini_role == "user" and request.system_instruction:
                    turn_text = f"{request.system_instruction}\n\n{turn_text}"
                    first_user_injected = True
                contents.append({"role": gemini_role, "parts": [turn_text]})

        current_prompt = request.prompt
        if not first_user_injected and request.system_instruction:
            current_prompt = f"{request.system_instruction}\n\n{current_prompt}"
        contents.append({"role": "user", "parts": [current_prompt]})
        return contents

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response using the Gemini API.

        Raises:
            LLMProviderException: On any API error or timeout.
        """
        model = self._get_model(use_lite=request.use_lite_model)
        model_name = (
            self._lite_model_name
            if request.use_lite_model
            else self._primary_model_name
        )

        generation_config = genai.GenerationConfig(
            temperature=request.temperature or self._settings.temperature,
            max_output_tokens=request.max_output_tokens
            or self._settings.max_output_tokens,
        )

        contents = self._build_contents(request)

        try:
            response = model.generate_content(
                contents=contents,
                generation_config=generation_config,
                request_options={"timeout": self._settings.request_timeout},
            )
        except Exception as exc:
            logger.error("Gemini API error", error=str(exc), model=model_name)
            raise LLMProviderException(
                message=f"Gemini provider error: {exc}",
                detail={"model": model_name},
            ) from exc

        text = response.text or ""
        usage = response.usage_metadata

        return LLMResponse(
            content=text,
            input_tokens=usage.prompt_token_count if usage else 0,
            output_tokens=usage.candidates_token_count if usage else 0,
            model_used=model_name,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream tokens from Gemini.

        Note: Gemini SDK streaming is synchronous under the hood in the
        current SDK version. This wraps it as an async iterator.
        """
        model = self._get_model(use_lite=request.use_lite_model)
        contents = self._build_contents(request)

        try:
            response = model.generate_content(contents=contents, stream=True)
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            logger.error("Gemini streaming error", error=str(exc))
            raise LLMProviderException(
                message=f"Gemini streaming error: {exc}"
            ) from exc

    async def health_check(self) -> bool:
        """Verify Gemini API connectivity with a minimal token generation call."""
        try:
            model = self._get_model(use_lite=True)
            response = model.generate_content(
                contents="ping",
                generation_config=genai.GenerationConfig(max_output_tokens=5),
                request_options={"timeout": 10},
            )
            return bool(response.text)
        except Exception as exc:
            logger.warning("Gemini health check failed", error=str(exc))
            return False
