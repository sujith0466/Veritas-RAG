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
    """Feature flags for controlled rollout of Veritas RAG capabilities.

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

    # Epic 8 Streaming Resilience
    enable_sse_recovery: bool = Field(
        default=True,
        alias="ENABLE_SSE_RECOVERY",
        description="Enable SSE Last-Event-ID recovery and Redis caching (F8.4)",
    )
    enable_sse_heartbeat: bool = Field(
        default=False,
        alias="ENABLE_SSE_HEARTBEAT",
        description="Enable heartbeat events during long streams (F8.4)",
    )
    enable_timeout_events: bool = Field(
        default=True,
        alias="ENABLE_TIMEOUT_EVENTS",
        description="Enable structured timeout error events (F8.5)",
    )
    enable_partial_persistence: bool = Field(
        default=True,
        alias="ENABLE_PARTIAL_PERSISTENCE",
        description="Persist partial messages on cancellation or timeout (F8.6)",
    )

    # Epic 8 Batch 3 Streaming Enhancements & Policy
    enable_streaming_reliability: bool = Field(
        default=False,
        alias="ENABLE_STREAMING_RELIABILITY",
        description="Enable incremental streaming reliability score updates (F8.7)",
    )
    enable_streaming_citations: bool = Field(
        default=True,
        alias="ENABLE_STREAMING_CITATIONS",
        description="Enable progressive streaming of citations (F8.8)",
    )
    enable_ai_policy_engine: bool = Field(
        default=False,
        alias="ENABLE_AI_POLICY_ENGINE",
        description="Enable AI Policy Middleware for token/topic/PII enforcement (F8.9)",
    )

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }
