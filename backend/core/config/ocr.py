"""OCR Engine and pipeline configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class OCRSettings(BaseSettings):
    """Configuration for OCR engines, timeout bounding, and execution policies."""

    timeout_seconds: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        alias="OCR_TIMEOUT_SECONDS",
        description="Overall timeout deadline in seconds bounding OCR execution across all engines.",
    )

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }
