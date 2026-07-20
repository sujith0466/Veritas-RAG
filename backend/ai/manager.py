"""LLM Provider Manager.

Implements the LLMProvider interface and acts as an automated failover router.
Obtains provider instances exclusively from the ProviderRegistry and iterates through
the configured provider priority list (`LLM_PROVIDER_PRIORITY`) until a request succeeds.
"""

from collections.abc import AsyncIterator
from typing import Any

import structlog

from backend.ai.interfaces.llm_provider import LLMProvider, LLMRequest, LLMResponse
from backend.ai.registry import ProviderRegistry
from backend.core.config import get_settings
from backend.core.exceptions import LLMProviderException

logger = structlog.get_logger(__name__)


class LLMProviderManager(LLMProvider):
    """Orchestrates LLM calls with automatic failover across configured priority providers.

    Obtains providers exclusively from `ProviderRegistry` and ensures zero business logic
    changes when switching primary or fallback AI models.
    """

    def __init__(self) -> None:
        self._settings = get_settings().ai

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Execute generate request across priority providers until one succeeds."""
        priority_list = self._settings.priority_list
        if not priority_list:
            raise LLMProviderException(
                message="No LLM providers configured in priority list.",
                detail={"priority_list": priority_list},
            )

        errors: list[dict[str, Any]] = []

        for provider_name in priority_list:
            try:
                provider = ProviderRegistry.get_provider(provider_name)
            except Exception as exc:
                logger.warning(
                    "Failed to instantiate provider from registry during generate",
                    provider=provider_name,
                    error=str(exc),
                )
                errors.append({"provider": provider_name, "error": str(exc)})
                continue

            try:
                logger.debug("Attempting LLM generate", provider=provider_name)
                response = await provider.generate(request)
                if errors:
                    logger.info(
                        "LLM generate succeeded via fallback provider",
                        successful_provider=provider_name,
                        prior_failures=len(errors),
                    )
                return response
            except Exception as exc:
                logger.warning(
                    "Provider generation failed, attempting next in priority list",
                    failed_provider=provider_name,
                    error=str(exc),
                )
                errors.append({"provider": provider_name, "error": str(exc)})

        logger.error("All configured LLM providers failed for generate request", errors=errors)
        raise LLMProviderException(
            message=f"All configured LLM providers failed: {[e['provider'] + ': ' + e['error'] for e in errors]}",
            detail={"errors": errors, "attempted_providers": priority_list},
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream tokens across priority providers with automatic failover on init failure."""
        priority_list = self._settings.priority_list
        if not priority_list:
            raise LLMProviderException(
                message="No LLM providers configured in priority list for streaming.",
                detail={"priority_list": priority_list},
            )

        errors: list[dict[str, Any]] = []

        for provider_name in priority_list:
            try:
                provider = ProviderRegistry.get_provider(provider_name)
            except Exception as exc:
                logger.warning(
                    "Failed to instantiate provider from registry during stream",
                    provider=provider_name,
                    error=str(exc),
                )
                errors.append({"provider": provider_name, "error": str(exc)})
                continue

            chunks_yielded = 0
            try:
                logger.debug("Attempting LLM stream", provider=provider_name)
                async for chunk in provider.stream(request):
                    chunks_yielded += 1
                    yield chunk
                if errors:
                    logger.info(
                        "LLM stream succeeded via fallback provider",
                        successful_provider=provider_name,
                        prior_failures=len(errors),
                    )
                return
            except Exception as exc:
                if chunks_yielded > 0:
                    logger.error(
                        "Provider stream failed after emitting chunks; cannot failover cleanly",
                        failed_provider=provider_name,
                        chunks_yielded=chunks_yielded,
                        error=str(exc),
                    )
                    raise LLMProviderException(
                        message=f"Stream aborted mid-generation from {provider_name}: {exc}",
                        detail={"failed_provider": provider_name, "chunks_yielded": chunks_yielded},
                    ) from exc

                logger.warning(
                    "Provider stream initialization failed, attempting next provider in priority list",
                    failed_provider=provider_name,
                    error=str(exc),
                )
                errors.append({"provider": provider_name, "error": str(exc)})

        logger.error("All configured LLM providers failed for stream request", errors=errors)
        raise LLMProviderException(
            message=f"All configured LLM providers failed for streaming: {[e['provider'] + ': ' + e['error'] for e in errors]}",
            detail={"errors": errors, "attempted_providers": priority_list},
        )

    async def health_check(self) -> bool:
        """Verify that at least one provider in the priority list is healthy."""
        priority_list = self._settings.priority_list
        for provider_name in priority_list:
            try:
                provider = ProviderRegistry.get_provider(provider_name)
                if await provider.health_check():
                    return True
            except Exception as exc:
                logger.debug("Provider health check failed or registry error", provider=provider_name, error=str(exc))
        return False

    async def detailed_health_check(self) -> dict[str, bool]:
        """Perform health checks on all configured priority providers and return per-provider status."""
        results: dict[str, bool] = {}
        for provider_name in self._settings.priority_list:
            try:
                provider = ProviderRegistry.get_provider(provider_name)
                results[provider_name] = await provider.health_check()
            except Exception:
                results[provider_name] = False
        return results
