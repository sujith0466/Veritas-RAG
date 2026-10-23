"""Deterministic Offline Mock LLM Provider for Performance & Load Testing.

WP-3D: TSK-3D-01 — Mock LLM Provider & Production Guard.

Provides repeatable, offline LLM responses with configurable Time To First Token (TTFT)
and inter-token pacing without incurring external LLM API costs or upstream rate limits.
Enforces an unbypassable, fail-closed production guard refusing initialization in production.
"""

import asyncio
from collections.abc import AsyncIterator
import os
from typing import Any

import structlog

from backend.ai.interfaces.llm_provider import LLMProvider, LLMRequest, LLMResponse
from backend.core.config import get_settings
from backend.core.exceptions import LLMProviderException

logger = structlog.get_logger(__name__)


class MockLLMProvider(LLMProvider):
    """Deterministic offline mock LLM provider for performance, stress, and capacity testing."""

    DEFAULT_RESPONSE_TEXT = (
        "Veritas RAG is an enterprise knowledge platform utilizing self-correcting "
        "retrieval-augmented generation to provide verified answers with citation integrity."
    )

    def __init__(
        self,
        ttft_delay_seconds: float = 0.2,
        token_delay_seconds: float = 0.02,
        canned_response: str | None = None,
        model_name: str = "mock-deterministic-llm",
        simulate_failure: bool = False,
    ) -> None:
        """Initialize the MockLLMProvider with fail-closed production guards.

        Args:
            ttft_delay_seconds: Simulated delay before the first token is yielded (default 200ms).
            token_delay_seconds: Simulated delay between subsequent tokens (default 20ms).
            canned_response: Deterministic text to return (defaults to standard Veritas text).
            model_name: Nominal model name reported in LLMResponse.
            simulate_failure: If True, generate and stream raise an LLMProviderException.

        Raises:
            RuntimeError: If initialization is attempted in a production environment.
        """
        self._enforce_production_guard()

        self.ttft_delay_seconds = max(0.0, float(ttft_delay_seconds))
        self.token_delay_seconds = max(0.0, float(token_delay_seconds))
        self.canned_response = canned_response or self.DEFAULT_RESPONSE_TEXT
        self.model_name = model_name
        self.simulate_failure = simulate_failure

        logger.info(
            "Initialized MockLLMProvider for offline performance testing",
            ttft_delay_seconds=self.ttft_delay_seconds,
            token_delay_seconds=self.token_delay_seconds,
            model_name=self.model_name,
        )

    @classmethod
    def _enforce_production_guard(cls) -> None:
        """Fail-closed check preventing MockLLMProvider initialization in production.

        Inspects runtime environment settings and environment variables. If any check
        indicates a production environment, raises a non-recoverable RuntimeError.
        """
        # 1. Environment variable inspection
        for env_var in ("ENVIRONMENT", "APP_ENVIRONMENT"):
            val = os.environ.get(env_var, "").strip().lower()
            if val in ("production", "prod"):
                logger.critical(
                    "FATAL SECURITY GUARD: MockLLMProvider initialization refused in production",
                    flag=env_var,
                    value=val,
                )
                raise RuntimeError(
                    f"CRITICAL SAFETY VIOLATION: MockLLMProvider is strictly forbidden in production! "
                    f"({env_var}={val})"
                )

        # 2. Application settings object inspection
        try:
            settings = get_settings()
            if settings.is_production:
                logger.critical(
                    "FATAL SECURITY GUARD: MockLLMProvider refused by settings.is_production"
                )
                raise RuntimeError(
                    "CRITICAL SAFETY VIOLATION: MockLLMProvider is strictly forbidden in production! "
                    "(settings.is_production=True)"
                )
        except RuntimeError:
            raise
        except Exception as exc:
            # If settings inspection encounters an unexpected error, fail-closed if production implied
            env_raw = os.environ.get("ENVIRONMENT", "").lower()
            if "prod" in env_raw:
                raise RuntimeError(
                    f"CRITICAL SAFETY VIOLATION: MockLLMProvider fail-closed: {exc}"
                ) from exc

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Simulate non-streaming generation with configured TTFT delay."""
        self._enforce_production_guard()

        if self.simulate_failure:
            raise LLMProviderException(
                message="MockSimulatedFailure: MockLLMProvider configured failure for testing",
                detail={"provider": "mock", "error_type": "MockSimulatedFailure"},
            )

        if self.ttft_delay_seconds > 0:
            await asyncio.sleep(self.ttft_delay_seconds)

        content = self.canned_response
        input_tokens = len(request.prompt.split()) + 10
        output_tokens = len(content.split())

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_used=self.model_name,
            metadata={"mock": True, "ttft_simulated": self.ttft_delay_seconds},
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Simulate token streaming with realistic TTFT delay and inter-token pacing."""
        self._enforce_production_guard()

        if self.simulate_failure:
            raise LLMProviderException(
                message="MockSimulatedFailure: MockLLMProvider configured failure for streaming",
                detail={"provider": "mock", "error_type": "MockSimulatedFailure"},
            )

        # 1. Simulate initial Time To First Token (TTFT)
        if self.ttft_delay_seconds > 0:
            await asyncio.sleep(self.ttft_delay_seconds)

        # 2. Stream chunk by chunk with inter-token pacing
        words = self.canned_response.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == len(words) - 1 else f"{word} "
            yield chunk
            if self.token_delay_seconds > 0:
                await asyncio.sleep(self.token_delay_seconds)

    async def health_check(self) -> bool:
        """Verify the mock provider is operational."""
        try:
            self._enforce_production_guard()
            return not self.simulate_failure
        except Exception:
            return False
