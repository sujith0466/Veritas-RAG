"""Observability and Tracing Configuration Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings


class ObservabilitySettings(BaseSettings):
    """Configuration for OpenTelemetry tracing, metrics, and exporter endpoints."""

    otlp_endpoint: str | None = Field(default=None, alias="OTLP_ENDPOINT")
    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")
    tracing_enabled: bool = Field(default=True, alias="TRACING_ENABLED")
    service_name: str = Field(default="raguard-ai", alias="OTEL_SERVICE_NAME")
    sample_rate: float = Field(default=1.0, alias="OTEL_TRACE_SAMPLE_RATE")

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }
