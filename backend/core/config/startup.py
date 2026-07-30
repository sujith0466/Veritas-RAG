"""Startup configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class StartupSettings(BaseSettings):
    """Configuration for application startup validations."""

    validate_infrastructure: bool = Field(default=True, alias="VALIDATE_INFRASTRUCTURE")

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }
