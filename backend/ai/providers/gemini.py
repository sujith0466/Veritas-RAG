"""Google Gemini LLM provider implementation.

Implements the LLMProvider interface for Google's Gemini models.
Business logic never imports this directly — it always uses the interface
and the factory to obtain a provider instance.
"""

from collections.abc import AsyncIterator

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

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response using the Gemini API.

        Raises:
            LLMProviderException: On any API error or timeout.
        """
        model = self._get_model(use_lite=request.use_lite_model)
        model_name = self._lite_model_name if request.use_lite_model else self._primary_model_name

        generation_config = genai.GenerationConfig(
            temperature=request.temperature or self._settings.temperature,
            max_output_tokens=request.max_output_tokens or self._settings.max_output_tokens,
        )

        prompt = request.prompt
        if request.system_instruction:
            prompt = f"{request.system_instruction}\n\n{request.prompt}"

        try:
            response = model.generate_content(
                contents=prompt,
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
        prompt = request.prompt
        if request.system_instruction:
            prompt = f"{request.system_instruction}\n\n{request.prompt}"

        try:
            response = model.generate_content(contents=prompt, stream=True)
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            logger.error("Gemini streaming error", error=str(exc))
            raise LLMProviderException(message=f"Gemini streaming error: {exc}") from exc

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
