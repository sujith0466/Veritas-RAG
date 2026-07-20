"""RAGuard AI — AI provider interfaces, registry, manager, and factory (`backend/ai/`)."""

from .factory import create_llm_provider
from .interfaces.llm_provider import LLMProvider, LLMRequest, LLMResponse
from .manager import LLMProviderManager
from .providers.gemini import GeminiProvider
from .providers.openrouter import OpenRouterProvider
from .registry import ProviderRegistry

__all__ = [
    "GeminiProvider",
    "LLMProvider",
    "LLMProviderManager",
    "LLMRequest",
    "LLMResponse",
    "OpenRouterProvider",
    "ProviderRegistry",
    "create_llm_provider",
]
