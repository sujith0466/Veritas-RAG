"""Abstract LLM provider interface.

All LLM provider implementations must implement this interface.
Business logic in backend/modules/ communicates ONLY through this interface —
never directly with vendor SDKs.

This decouples the business logic from Gemini, OpenAI, or any other provider,
enabling:
- Swappable providers without touching business logic (NFR: Maintainability)
- 100% unit-testable business logic via mock providers
- Easy provider comparison in evaluation scenarios
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMRequest:
    """Input to an LLM provider generate or stream call."""

    prompt: str
    system_instruction: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    tenant_id: str | None = None
    workspace_id: str | None = None
    # If True, use gemini-2.0-flash-lite for lightweight classification/routing tasks
    use_lite_model: bool = False
    conversation_history: list[dict[str, str]] | None = None


@dataclass
class LLMResponse:
    """Output from an LLM provider call."""

    content: str
    # Raw token usage for cost tracking
    input_tokens: int
    output_tokens: int
    # Which model was actually used
    model_used: str
    # Provider-specific metadata for debugging
    metadata: dict[str, Any] | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMProvider(ABC):
    """Abstract interface for all LLM providers.

    Implementations: backend/providers/llm/gemini.py
    """

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response for the given prompt.

        Args:
            request: The LLM request with prompt and generation parameters.

        Returns:
            LLMResponse with the generated content and token usage.

        Raises:
            LLMProviderException: If the provider returns an error.
        """
        ...

    @abstractmethod
    def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream the response tokens as they are generated.

        Args:
            request: The LLM request with prompt and generation parameters.

        Yields:
            Token chunks as they arrive from the provider.

        Raises:
            LLMProviderException: If the provider returns an error.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify the provider is reachable and functional.

        Returns:
            True if the provider is healthy, False otherwise.
        """
        ...
