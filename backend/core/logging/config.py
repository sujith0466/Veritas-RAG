"""Structlog configuration for RAGuard AI.

Configures structlog with:
- JSON output in staging/production for log aggregators
- Human-readable colored console output in development
- Standard processors: timestamp, log level, exception formatting
- Correlation ID injection from request context
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor


from backend.observability.logging.pii_masker import mask_pii


def _add_app_context(
    logger: Any,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add application-level context to every log line."""
    event_dict.setdefault("service", "raguard-ai")
    return event_dict


def _add_otel_context(
    logger: Any,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Inject active OpenTelemetry trace_id and span_id into structured logs."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            ctx = span.get_span_context()
            if ctx and ctx.trace_id:
                event_dict["trace_id"] = format(ctx.trace_id, "032x")
                event_dict["span_id"] = format(ctx.span_id, "016x")
    except Exception:
        # Fallback cleanly if OpenTelemetry is not installed or active
        pass
    return event_dict


def configure_logging(log_level: str = "INFO", log_format: str = "console") -> None:
    """Configure structlog and the standard library logging.

    Call this once at application startup before any log statements.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
        log_format: "json" for structured JSON (production) or
                    "console" for human-readable (development).
    """
    # ── Shared processors applied to every log event ──────────────────────────
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_app_context,
        _add_otel_context,
        mask_pii,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        # Production: structured JSON consumed by log aggregators (ELK, Cloud Logging)
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        # Development: colored, human-readable output
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ── Redirect stdlib logging to structlog ───────────────────────────────────
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper(), logging.INFO),
        stream=sys.stdout,
        force=True,
    )
    # Suppress noisy third-party loggers
    for noisy_logger in ("uvicorn.access", "sqlalchemy.engine", "celery"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
