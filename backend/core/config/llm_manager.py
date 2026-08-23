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

    max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    retry_initial_delay: float = Field(default=1.0, alias="LLM_RETRY_INITIAL_DELAY")
    request_timeout: float = Field(default=30.0, alias="LLM_REQUEST_TIMEOUT")
    audit_mode: str = Field(default="hash_only", alias="LLM_AUDIT_MODE")
    audit_retention_days: int = Field(
        default=30, ge=1, le=3650, alias="LLM_AUDIT_RETENTION_DAYS"
    )

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
