"""Security configuration settings."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class SecuritySettings(BaseSettings):
    """CORS, rate limiting, and application security configuration."""

    # CORS — comma-separated list of allowed origins
    cors_origins_str: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        alias="CORS_ORIGINS",
    )
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: list[str] = Field(default=["*"])
    cors_allow_headers: list[str] = Field(default=["*"])

    # Allowed hosts — comma-separated; empty string = allow all
    allowed_hosts_str: str = Field(default="", alias="ALLOWED_HOSTS")

    # Rate limiting
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")

    # File uploads
    max_upload_size_bytes: int = Field(
        default=52_428_800, alias="MAX_UPLOAD_SIZE_BYTES"
    )  # 50MB

    model_config = {"populate_by_name": True, "env_file": ".env.local", "extra": "ignore"}

    @field_validator("cors_origins_str")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        origins = [o.strip() for o in v.split(",") if o.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS must contain at least one origin")
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_str.split(",") if o.strip()]

    @property
    def allowed_hosts(self) -> list[str]:
        if not self.allowed_hosts_str:
            return []
        return [h.strip() for h in self.allowed_hosts_str.split(",") if h.strip()]
