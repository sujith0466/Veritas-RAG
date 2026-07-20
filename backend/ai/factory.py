"""LLM provider factory.

Returns the correct LLMProvider implementation or automated Provider Manager based on configuration.
Business logic calls this factory to obtain a provider — it never instantiates concrete providers directly.

Usage:
    from backend.ai.factory import create_llm_provider

    provider = create_llm_provider()
    response = await provider.generate(LLMRequest(prompt="..."))
"""

import structlog

from .interfaces.llm_provider import LLMProvider
from .manager import LLMProviderManager
from .providers.gemini import GeminiProvider
from .providers.openrouter import OpenRouterProvider
from .registry import ProviderRegistry

logger = structlog.get_logger(__name__)

# Register standard providers in the central registry at module load time.
ProviderRegistry.register("gemini", GeminiProvider)
ProviderRegistry.register("openrouter", OpenRouterProvider)


def create_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """Instantiate and return an LLMProvider implementation or manager.

    Args:
        provider_name: Optional explicit provider name (e.g. 'gemini', 'openrouter').
                       If None or 'manager', returns the automated LLMProviderManager
                       which orchestrates priority failover across configured providers.

    Returns:
        A concrete LLMProvider implementation (usually LLMProviderManager).

    Raises:
        ValueError: If an explicit provider name is requested but not registered.
    """
    if provider_name is None or provider_name.strip().lower() == "manager":
        logger.info("Creating LLMProviderManager (with priority failover)")
        return LLMProviderManager()

    clean_name = provider_name.strip().lower()
    logger.info("Creating specific LLM provider from registry", provider=clean_name)
    return ProviderRegistry.get_provider(clean_name)
