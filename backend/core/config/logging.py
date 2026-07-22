"""Logging configuration settings."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class LoggingSettings(BaseSettings):
    """Structured logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )
    # json: structured JSON output for production / log aggregators
    # console: human-readable colored output for development
    format: Literal["json", "console"] = Field(default="console", alias="LOG_FORMAT")
    log_requests: bool = Field(default=True, alias="LOG_REQUESTS")

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }
