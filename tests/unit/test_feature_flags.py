"""Unit tests for feature flags management."""

import pytest

from backend.core.config import get_settings
from backend.core.feature_flags import is_enabled


@pytest.mark.unit
class TestFeatureFlags:
    def test_all_flags_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Clear any environment overrides
        for flag in [
            "ENABLE_RETRY_ENGINE",
            "ENABLE_REFLECTION",
            "ENABLE_ANSWER_VALIDATION",
            "ENABLE_KNOWLEDGE_HEALTH",
            "ENABLE_EVALUATION",
            "ENABLE_ANALYTICS",
            "ENABLE_MONITORING",
            "ENABLE_OTEL_TRACING",
        ]:
            monkeypatch.delenv(flag, raising=False)

        get_settings.cache_clear()
        settings = get_settings()

        assert settings.features.enable_retry_engine is False
        assert settings.features.enable_reflection is False
        assert settings.features.enable_answer_validation is False
        assert settings.features.enable_knowledge_health is False
        assert settings.features.enable_evaluation is False
        assert settings.features.enable_analytics is False
        assert settings.features.enable_monitoring is False
        assert settings.features.enable_otel_tracing is False

        assert is_enabled("enable_retry_engine") is False
        assert is_enabled("unknown_flag") is False

    def test_enabling_specific_flags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENABLE_RETRY_ENGINE", "true")
        monkeypatch.setenv("ENABLE_EVALUATION", "1")
        monkeypatch.setenv("ENABLE_REFLECTION", "false")

        get_settings.cache_clear()

        assert is_enabled("enable_retry_engine") is True
        assert is_enabled("enable_evaluation") is True
        assert is_enabled("enable_reflection") is False
