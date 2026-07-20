"""Supabase authentication configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class SupabaseSettings(BaseSettings):
    """Supabase project and authentication configuration."""

    url: str = Field(alias="SUPABASE_URL")
    anon_key: str = Field(alias="SUPABASE_ANON_KEY")
    service_role_key: str = Field(alias="SUPABASE_SERVICE_ROLE_KEY", repr=False)
    jwt_secret: str = Field(alias="SUPABASE_JWT_SECRET", repr=False)
    jwt_algorithm: str = Field(default="HS256", alias="SUPABASE_JWT_ALGORITHM")
    jwks_url: str | None = Field(default=None, alias="SUPABASE_JWKS_URL")

    model_config = {"populate_by_name": True, "env_file": ".env.local", "extra": "ignore"}
