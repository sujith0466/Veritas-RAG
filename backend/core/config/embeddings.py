"""Embedding Pipeline provider configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class EmbeddingSettings(BaseSettings):
    """Configuration for embedding providers, default models, and batch sizes."""

    default_provider: str = Field(default="openai", alias="DEFAULT_EMBEDDING_PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(
        default="text-embedding-3-large", alias="OPENAI_EMBEDDING_MODEL"
    )
    cohere_api_key: str = Field(default="", alias="COHERE_API_KEY")
    cohere_model: str = Field(
        default="embed-multilingual-v3.0", alias="COHERE_EMBEDDING_MODEL"
    )
    local_model: str = Field(
        default="BAAI/bge-large-en-v1.5", alias="LOCAL_EMBEDDING_MODEL"
    )
    batch_size: int = Field(default=100, alias="EMBEDDING_BATCH_SIZE")

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }
