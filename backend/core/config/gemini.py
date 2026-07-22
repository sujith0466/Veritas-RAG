"""Google Gemini AI configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class GeminiSettings(BaseSettings):
    """Google Gemini API configuration."""

    api_key: str = Field(default="", alias="GEMINI_API_KEY", repr=False)
    # Primary model for generation tasks
    model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")
    # Lightweight model for classification (intent, ambiguity) — cheaper per token
    lite_model: str = Field(default="gemini-2.0-flash-lite", alias="GEMINI_LITE_MODEL")
    max_output_tokens: int = Field(default=2048, alias="GEMINI_MAX_OUTPUT_TOKENS")
    # Low temperature for deterministic reliability scoring
    temperature: float = Field(default=0.1, alias="GEMINI_TEMPERATURE")
    request_timeout: int = Field(default=60, alias="GEMINI_REQUEST_TIMEOUT")

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }
