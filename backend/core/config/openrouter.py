"""OpenRouter AI configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class OpenRouterSettings(BaseSettings):
    """OpenRouter API configuration."""

    api_key: str = Field(default="", alias="OPENROUTER_API_KEY", repr=False)
    base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
    # Primary model for generation tasks
    model: str = Field(default="anthropic/claude-3.5-sonnet", alias="OPENROUTER_MODEL")
    # Lightweight model for classification (intent, ambiguity) — cheaper per token
    lite_model: str = Field(default="anthropic/claude-3-haiku", alias="OPENROUTER_LITE_MODEL")
    max_output_tokens: int = Field(default=2048, alias="OPENROUTER_MAX_OUTPUT_TOKENS")
    # Low temperature for deterministic reliability scoring
    temperature: float = Field(default=0.1, alias="OPENROUTER_TEMPERATURE")
    request_timeout: int = Field(default=60, alias="OPENROUTER_REQUEST_TIMEOUT")

    model_config = {"populate_by_name": True, "env_file": ".env.local", "extra": "ignore"}
