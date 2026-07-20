"""AI Provider Registry.

Central registry for discovering, registering, and instantiating concrete LLMProvider classes.
Decouples provider implementation details from the Provider Manager and Factory.
"""

from typing import Any

import structlog

from backend.ai.interfaces.llm_provider import LLMProvider

logger = structlog.get_logger(__name__)


class ProviderRegistry:
    """Registry for managing available LLM providers.

    Allows registering new provider implementations dynamically and obtaining instances
    without hardcoding provider names across business logic or the provider manager.
    """

    _registry: dict[str, type[LLMProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: type[LLMProvider]) -> None:
        """Register a new LLMProvider implementation under the given name.

        Args:
            name: Unique lowercase identifier for the provider (e.g. 'openrouter', 'gemini').
            provider_class: Concrete class implementing LLMProvider.
        """
        clean_name = name.strip().lower()
        cls._registry[clean_name] = provider_class
        logger.debug("Registered LLM provider class", provider=clean_name)

    @classmethod
    def get_provider_class(cls, name: str) -> type[LLMProvider] | None:
        """Retrieve the provider class for the given name without instantiating it."""
        if not cls._registry:
            from backend.ai.providers.gemini import GeminiProvider
            from backend.ai.providers.openrouter import OpenRouterProvider

            cls.register("gemini", GeminiProvider)
            cls.register("openrouter", OpenRouterProvider)
        return cls._registry.get(name.strip().lower())

    @classmethod
    def get_provider(cls, name: str, **kwargs: Any) -> LLMProvider:
        """Instantiate and return the requested LLMProvider.

        Args:
            name: Name of the registered provider to instantiate.
            **kwargs: Optional constructor arguments passed to the provider class.

        Returns:
            An instantiated concrete LLMProvider.

        Raises:
            ValueError: If the requested provider name is not registered.
        """
        clean_name = name.strip().lower()
        provider_class = cls.get_provider_class(clean_name)
        if provider_class is None:
            available = list(cls._registry.keys())
            raise ValueError(
                f"Unknown LLM provider '{clean_name}'. Registered providers: {available}"
            )
        logger.info("Instantiating LLM provider from registry", provider=clean_name)
        return provider_class(**kwargs)

    @classmethod
    def list_providers(cls) -> list[str]:
        """Return a list of all currently registered provider names."""
        return sorted(cls._registry.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear the registry (useful for testing isolation)."""
        cls._registry.clear()
