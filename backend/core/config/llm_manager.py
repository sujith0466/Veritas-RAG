"""LLM Provider Manager configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class LLMManagerSettings(BaseSettings):
    """Configuration for LLM provider selection and failover priority."""

    # Comma-separated list of provider priorities (e.g. "openrouter,gemini")
    provider_priority_raw: str = Field(
        default="openrouter,gemini", alias="LLM_PROVIDER_PRIORITY"
    )
    primary_provider: str = Field(default="openrouter", alias="PRIMARY_LLM_PROVIDER")
    fallback_provider: str = Field(default="gemini", alias="FALLBACK_LLM_PROVIDER")

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }

    @property
    def priority_list(self) -> list[str]:
        """Return clean list of provider names in priority order."""
        if not self.provider_priority_raw:
            # Fallback if raw priority list is empty
            return [
                p.strip().lower()
                for p in (self.primary_provider, self.fallback_provider)
                if p.strip()
            ]
        providers = [
            p.strip().lower()
            for p in self.provider_priority_raw.split(",")
            if p.strip()
        ]
        return providers if providers else ["openrouter", "gemini"]
