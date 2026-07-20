"""Unit tests for the modular configuration system."""

from pydantic import ValidationError
import pytest

from backend.core.config import (
    AppSettings,
    DatabaseSettings,
    FeatureFlagSettings,
    GeminiSettings,
    LLMManagerSettings,
    LoggingSettings,
    OpenRouterSettings,
    QdrantSettings,
    RedisSettings,
    SecuritySettings,
    ServerSettings,
    Settings,
    SupabaseSettings,
    get_settings,
)


@pytest.mark.unit
class TestAppSettings:
    def test_default_values_and_aliases(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_NAME", "Test App")
        monkeypatch.setenv("APP_VERSION", "2.0.0")
        monkeypatch.setenv("APP_ENVIRONMENT", "production")
        monkeypatch.setenv("APP_DEBUG", "false")
        monkeypatch.setenv("APP_SECRET_KEY", "super-secret-key-that-is-32-chars-long")

        settings = AppSettings()
        assert settings.name == "Test App"
        assert settings.version == "2.0.0"
        assert settings.environment == "production"
        assert settings.debug is False
        assert settings.secret_key == "super-secret-key-that-is-32-chars-long"

    def test_environment_properties(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_SECRET_KEY", "secret")

        monkeypatch.setenv("APP_ENVIRONMENT", "development")
        app_dev = AppSettings()
        assert app_dev.is_development is True
        assert app_dev.is_testing is False
        assert app_dev.is_production is False

        monkeypatch.setenv("APP_ENVIRONMENT", "testing")
        app_test = AppSettings()
        assert app_test.is_development is False
        assert app_test.is_testing is True
        assert app_test.is_production is False

        monkeypatch.setenv("APP_ENVIRONMENT", "production")
        app_prod = AppSettings()
        assert app_prod.is_development is False
        assert app_prod.is_testing is False
        assert app_prod.is_production is True


@pytest.mark.unit
class TestDatabaseSettings:
    def test_valid_async_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db")
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
        settings = DatabaseSettings()
        assert settings.url == "postgresql+asyncpg://user:pass@localhost:5432/db"
        assert settings.pool_size == 10

    def test_invalid_sync_url_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
        with pytest.raises(ValidationError) as exc_info:
            DatabaseSettings()
        assert "DATABASE_URL must use asyncpg driver" in str(exc_info.value)


@pytest.mark.unit
class TestRedisSettings:
    def test_url_properties(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REDIS_HOST", "redis.local")
        monkeypatch.setenv("REDIS_PORT", "6380")
        monkeypatch.setenv("REDIS_PASSWORD", "secretpass")
        monkeypatch.setenv("REDIS_DB", "2")
        monkeypatch.setenv("TEST_REDIS_DB", "14")

        settings = RedisSettings()
        assert settings.url == "redis://:secretpass@redis.local:6380/2"
        assert settings.test_url == "redis://:secretpass@redis.local:6380/14"


@pytest.mark.unit
class TestQdrantSettings:
    def test_collection_name_helper(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("QDRANT_COLLECTION_PREFIX", "custom_prefix")
        settings = QdrantSettings()
        assert settings.collection_name("tenant_123") == "custom_prefix_tenant_123"


@pytest.mark.unit
class TestSecuritySettings:
    def test_cors_origins_and_allowed_hosts_parsing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "http://foo.com, https://bar.org ")
        monkeypatch.setenv("ALLOWED_HOSTS", "foo.com, bar.org")
        settings = SecuritySettings()
        assert settings.cors_origins == ["http://foo.com", "https://bar.org"]
        assert settings.allowed_hosts == ["foo.com", "bar.org"]

    def test_empty_cors_origins_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORS_ORIGINS", " , ")
        with pytest.raises(ValidationError) as exc_info:
            SecuritySettings()
        assert "CORS_ORIGINS must contain at least one origin" in str(exc_info.value)


@pytest.mark.unit
class TestOpenRouterSettings:
    def test_default_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
        settings = OpenRouterSettings()
        assert settings.model == "anthropic/claude-3.5-sonnet"
        assert settings.base_url == "https://openrouter.ai/api/v1"


@pytest.mark.unit
class TestLLMManagerSettings:
    def test_priority_list_parsing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER_PRIORITY", "openrouter, gemini , groq ")
        settings = LLMManagerSettings()
        assert settings.priority_list == ["openrouter", "gemini", "groq"]

    def test_empty_priority_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER_PRIORITY", "   ")
        settings = LLMManagerSettings()
        assert settings.priority_list == ["openrouter", "gemini"]


@pytest.mark.unit
class TestUnifiedSettings:
    def test_settings_aggregation(self) -> None:
        settings = Settings()
        assert isinstance(settings.app, AppSettings)
        assert isinstance(settings.server, ServerSettings)
        assert isinstance(settings.database, DatabaseSettings)
        assert isinstance(settings.redis, RedisSettings)
        assert isinstance(settings.qdrant, QdrantSettings)
        assert isinstance(settings.supabase, SupabaseSettings)
        assert isinstance(settings.gemini, GeminiSettings)
        assert isinstance(settings.openrouter, OpenRouterSettings)
        assert isinstance(settings.ai, LLMManagerSettings)
        assert isinstance(settings.security, SecuritySettings)
        assert isinstance(settings.logging, LoggingSettings)
        assert isinstance(settings.features, FeatureFlagSettings)

    def test_settings_singleton_and_cache_clear(self) -> None:
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

        get_settings.cache_clear()
        s3 = get_settings()
        assert s1 is not s3
