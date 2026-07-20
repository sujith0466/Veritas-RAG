"""Feature flag configuration.

All flags default to False and must be explicitly enabled via environment variables.
This prevents accidental activation of incomplete features in production.

Usage:
    from backend.core.config import get_settings
    settings = get_settings()
    if settings.features.enable_retry_engine:
        # execute retry logic
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class FeatureFlagSettings(BaseSettings):
    """Feature flags for controlled rollout of RAGuard AI capabilities.

    Each flag corresponds to a distinct system capability. Flags are disabled
    by default to ensure production safety — features must be explicitly enabled
    per environment.
    """

    # Core AI pipeline features
    enable_retry_engine: bool = Field(
        default=False,
        alias="ENABLE_RETRY_ENGINE",
        description="Enable the Self-Correction retry loop (FR-SC-1 to FR-SC-4)",
    )
    enable_reflection: bool = Field(
        default=False,
        alias="ENABLE_REFLECTION",
        description="Enable post-generation Reflection Engine (FR-VAL-3)",
    )
    enable_answer_validation: bool = Field(
        default=False,
        alias="ENABLE_ANSWER_VALIDATION",
        description="Enable claim-level citation entailment verification (FR-VAL-1 to FR-VAL-4)",
    )
    enable_knowledge_health: bool = Field(
        default=False,
        alias="ENABLE_KNOWLEDGE_HEALTH",
        description="Enable proactive knowledge base health scanning (FR-KH-1 to FR-KH-4)",
    )
    enable_evaluation: bool = Field(
        default=False,
        alias="ENABLE_EVALUATION",
        description="Enable golden-set evaluation harness (FR-EVAL-1 to FR-EVAL-3)",
    )
    enable_analytics: bool = Field(
        default=False,
        alias="ENABLE_ANALYTICS",
        description="Enable analytics dashboard and metrics aggregation (FR-OBS-1)",
    )
    enable_monitoring: bool = Field(
        default=False,
        alias="ENABLE_MONITORING",
        description="Enable Prometheus metrics export",
    )
    enable_otel_tracing: bool = Field(
        default=False,
        alias="ENABLE_OTEL_TRACING",
        description="Enable OpenTelemetry distributed tracing",
    )

    model_config = {"populate_by_name": True, "env_file": ".env.local", "extra": "ignore"}
