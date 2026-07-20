"""App-level configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Core application identity and runtime mode settings."""

    name: str = Field(default="RAGuard AI", alias="APP_NAME")
    version: str = Field(default="1.0.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="APP_ENVIRONMENT")
    debug: bool = Field(default=False, alias="APP_DEBUG")
    secret_key: str = Field(alias="APP_SECRET_KEY")

    model_config = {"populate_by_name": True, "env_file": ".env.local", "extra": "ignore"}

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_testing(self) -> bool:
        return self.environment == "testing"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


class ServerSettings(BaseSettings):
    """Uvicorn / server runtime configuration."""

    host: str = Field(default="0.0.0.0", alias="SERVER_HOST")
    port: int = Field(default=8000, alias="SERVER_PORT")
    workers: int = Field(default=1, alias="SERVER_WORKERS")
    reload: bool = Field(default=False, alias="SERVER_RELOAD")

    model_config = {"populate_by_name": True, "env_file": ".env.local", "extra": "ignore"}
