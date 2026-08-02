"""Database configuration settings."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """PostgreSQL / SQLAlchemy configuration."""

    url: str = Field(alias="DATABASE_URL")
    alembic_url: str = Field(alias="ALEMBIC_DATABASE_URL")
    use_pgbouncer: bool = Field(default=False, alias="USE_PGBOUNCER")
    pgbouncer_url: str | None = Field(default=None, alias="PGBOUNCER_URL")
    pool_size: int = Field(default=5, alias="DATABASE_POOL_SIZE")
    max_overflow: int = Field(default=10, alias="DATABASE_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, alias="DATABASE_POOL_TIMEOUT")
    pool_recycle: int = Field(default=1800, alias="DATABASE_POOL_RECYCLE")
    echo: bool = Field(default=False, alias="DATABASE_ECHO")

    # Test database URL (used when APP_ENVIRONMENT=testing)
    test_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/raguard_test",
        alias="TEST_DATABASE_URL",
    )

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }

    @field_validator("url")
    @classmethod
    def validate_async_url(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use asyncpg driver: postgresql+asyncpg://..."
            )
        return v
