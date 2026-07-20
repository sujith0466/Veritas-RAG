"""Qdrant vector database configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class QdrantSettings(BaseSettings):
    """Qdrant client configuration."""

    host: str = Field(default="localhost", alias="QDRANT_HOST")
    port: int = Field(default=6333, alias="QDRANT_PORT")
    grpc_port: int = Field(default=6334, alias="QDRANT_GRPC_PORT")
    api_key: str = Field(default="", alias="QDRANT_API_KEY")
    prefer_grpc: bool = Field(default=False, alias="QDRANT_PREFER_GRPC")
    collection_prefix: str = Field(default="raguard", alias="QDRANT_COLLECTION_PREFIX")

    model_config = {"populate_by_name": True, "env_file": ".env.local", "extra": "ignore"}

    def collection_name(self, tenant_id: str) -> str:
        """Generate a tenant-scoped collection name."""
        return f"{self.collection_prefix}_{tenant_id}"
