"""OpenRouter AI configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class OpenRouterSettings(BaseSettings):
    """OpenRouter API configuration."""

    api_key: str = Field(default="", alias="OPENROUTER_API_KEY", repr=False)
    base_url: str = Field(
        default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL"
    )
    # Comma-separated list of primary models for failover
    models_raw: str = Field(
        default="anthropic/claude-3.5-sonnet,meta-llama/llama-3-70b-instruct,google/gemini-flash-1.5",
        alias="OPENROUTER_MODELS",
    )
    # Lightweight model for classification (intent, ambiguity) — cheaper per token
    lite_models_raw: str = Field(
        default="anthropic/claude-3-haiku,google/gemini-flash-1.5",
        alias="OPENROUTER_LITE_MODELS",
    )
    max_output_tokens: int = Field(default=2048, alias="OPENROUTER_MAX_OUTPUT_TOKENS")
    # Low temperature for deterministic reliability scoring
    temperature: float = Field(default=0.1, alias="OPENROUTER_TEMPERATURE")
    request_timeout: int = Field(default=60, alias="OPENROUTER_REQUEST_TIMEOUT")

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }

    @property
    def models(self) -> list[str]:
        return [m.strip() for m in self.models_raw.split(",") if m.strip()]

    @property
    def lite_models(self) -> list[str]:
        return [m.strip() for m in self.lite_models_raw.split(",") if m.strip()]
