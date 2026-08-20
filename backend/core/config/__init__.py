"""Unified configuration for RAGuard AI.

Aggregates all modular settings classes into a single Settings object.
The settings are loaded once at startup and cached via functools.lru_cache.

Usage:
    from backend.core.config import get_settings

    settings = get_settings()
    db_url = settings.database.url
    feature_on = settings.features.enable_retry_engine
"""

from functools import lru_cache

from .app import AppSettings, ServerSettings
from .database import DatabaseSettings
from .embeddings import EmbeddingSettings
from .feature_flags import FeatureFlagSettings
from .gemini import GeminiSettings
from .llm_manager import LLMManagerSettings
from .logging import LoggingSettings
from .observability import ObservabilitySettings
from .openrouter import OpenRouterSettings
from .qdrant import QdrantSettings
from .redis import RedisSettings
from .retrieval import RetrievalSettings
from .security import SecuritySettings
from .smtp import SmtpSettings
from .startup import StartupSettings
from .v1_engine import V1EngineSettings


class Settings:
    """Unified settings container.

    Each sub-settings class is loaded independently from environment variables.
    This keeps each config domain isolated while providing a single access point.
    """

    def __init__(self) -> None:
        self.app = AppSettings()
        self.server = ServerSettings()
        self.database = DatabaseSettings()
        self.redis = RedisSettings()
        self.qdrant = QdrantSettings()
        self.gemini = GeminiSettings()
        self.openrouter = OpenRouterSettings()
        self.ai = LLMManagerSettings()
        self.security = SecuritySettings()
        self.logging = LoggingSettings()
        self.observability = ObservabilitySettings()
        self.features = FeatureFlagSettings()
        self.embeddings = EmbeddingSettings()
        self.retrieval = RetrievalSettings()
        self.smtp = SmtpSettings()
        self.startup = StartupSettings()
        self.v1_engine = V1EngineSettings()

    @property
    def is_development(self) -> bool:
        return self.app.is_development

    @property
    def is_testing(self) -> bool:
        return self.app.is_testing

    @property
    def is_production(self) -> bool:
        return self.app.is_production


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton.

    The cache is busted in tests by calling get_settings.cache_clear().
    """
    return Settings()


__all__ = [
    "AppSettings",
    "DatabaseSettings",
    "EmbeddingSettings",
    "FeatureFlagSettings",
    "GeminiSettings",
    "LLMManagerSettings",
    "LoggingSettings",
    "ObservabilitySettings",
    "OpenRouterSettings",
    "QdrantSettings",
    "RedisSettings",
    "RetrievalSettings",
    "SecuritySettings",
    "ServerSettings",
    "SmtpSettings",
    "Settings",
    "V1EngineSettings",
    "get_settings",
]
