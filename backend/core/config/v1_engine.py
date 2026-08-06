from pydantic_settings import BaseSettings


class V1EngineSettings(BaseSettings):
    """Configuration for the V1 Engine internal API client."""

    base_url: str | None = None
    enabled: bool = False
    client_cert_path: str | None = None
    client_key_path: str | None = None
    ca_cert_path: str | None = None
    signing_key: str | None = None
    min_version: str = "1.0.0"
    max_connections: int = 50
    max_keepalive: int = 20
    connect_timeout: float = 5.0
    per_attempt_timeout: float = 10.0
    total_timeout: float = 30.0
    service_token: str | None = None

    class Config:
        env_prefix = "V1_ENGINE_"
