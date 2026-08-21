"""Qdrant vector database configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class QdrantSettings(BaseSettings):
    """Qdrant client configuration."""

    host: str = Field(default="127.0.0.1", alias="QDRANT_HOST")
    port: int = Field(default=6333, alias="QDRANT_PORT")
    grpc_port: int = Field(default=6334, alias="QDRANT_GRPC_PORT")
    url_override: str | None = Field(default=None, alias="QDRANT_URL")
    api_key: str = Field(default="", alias="QDRANT_API_KEY")
    prefer_grpc: bool = Field(default=False, alias="QDRANT_PREFER_GRPC")
    collection_prefix: str = Field(default="raguard", alias="QDRANT_COLLECTION_PREFIX")

    # Telemetry and Resilience
    retry_attempts: int = Field(default=3, alias="QDRANT_RETRY_ATTEMPTS")
    retry_backoff_max: float = Field(default=10.0, alias="QDRANT_RETRY_BACKOFF_MAX")
    timeout: float = Field(default=10.0, alias="QDRANT_TIMEOUT")
    batch_size_limit: int = Field(default=100, alias="QDRANT_BATCH_SIZE_LIMIT")

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }

    def collection_name(self, dimension: int) -> str:
        return f"{self.collection_prefix}_knowledge_{dimension}"
