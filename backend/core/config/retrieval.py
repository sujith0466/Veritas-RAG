"""Retrieval Pipeline provider configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class RetrievalSettings(BaseSettings):
    """Configuration for retrieval providers and reranking models."""

    reranker_model: str = Field(
        default="BAAI/bge-reranker-large", alias="RERANKER_MODEL"
    )

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }
