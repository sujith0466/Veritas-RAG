"""W3C Distributed Trace Context Propagation Engine.

Implements W3C Trace Context recommendation (traceparent, tracestate) and provides
utilities for injecting and extracting trace context across HTTP boundaries and
asynchronous message brokers (Celery/Redis).
"""

from __future__ import annotations

import re
from typing import Any

from opentelemetry import propagate, trace
from opentelemetry.context.context import Context
from opentelemetry.trace import format_span_id, format_trace_id
import structlog

logger = structlog.get_logger(__name__)

# W3C traceparent regex: version(2 hex)-trace_id(32 hex)-parent_id(16 hex)-trace_flags(2 hex)
_TRACEPARENT_PATTERN = re.compile(
    r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$", re.IGNORECASE
)


def parse_traceparent(header_val: str | None) -> dict[str, str] | None:
    """Validate and parse a W3C traceparent header string."""
    if not header_val or not isinstance(header_val, str):
        return None

    match = _TRACEPARENT_PATTERN.match(header_val.strip())
    if not match:
        return None

    version, trace_id, parent_id, flags = match.groups()

    # Disallow invalid all-zero IDs per W3C specification
    if trace_id == "0" * 32 or parent_id == "0" * 16:
        return None

    # Version 'ff' is invalid per W3C spec
    if version.lower() == "ff":
        return None

    return {
        "version": version.lower(),
        "trace_id": trace_id.lower(),
        "parent_id": parent_id.lower(),
        "flags": flags.lower(),
    }


def get_w3c_traceparent() -> str | None:
    """Return the current active span's W3C traceparent header value."""
    span = trace.get_current_span()
    if span is None or not span.is_recording():
        return None

    ctx = span.get_span_context()
    if not ctx or not ctx.trace_id or not ctx.span_id:
        return None

    trace_id_str = format_trace_id(ctx.trace_id)
    span_id_str = format_span_id(ctx.span_id)
    flags_str = f"{ctx.trace_flags:02x}"

    return f"00-{trace_id_str}-{span_id_str}-{flags_str}"


def inject_trace_context(carrier: dict[str, str] | None = None) -> dict[str, str]:
    """Inject the active trace context into a carrier dictionary (HTTP headers, task metadata).

    Args:
        carrier: Existing headers dict or None to create a new dict.

    Returns:
        The carrier dictionary populated with W3C traceparent and tracestate headers.
    """
    if carrier is None:
        carrier = {}

    try:
        propagate.inject(carrier)

        # Fallback explicit injection if global propagator was not set
        if "traceparent" not in carrier:
            tp = get_w3c_traceparent()
            if tp:
                carrier["traceparent"] = tp
    except Exception as exc:
        logger.debug("Failed to inject OpenTelemetry trace context", error=str(exc))

    return carrier


def extract_trace_context(carrier: dict[str, Any] | None) -> Context | None:
    """Extract OpenTelemetry trace context from a carrier dictionary.

    Args:
        carrier: Incoming HTTP headers or message metadata.

    Returns:
        The extracted OpenTelemetry Context object, or None if extraction fails.
    """
    if not carrier:
        return None

    # Normalize header keys to lowercase
    normalized_carrier = {str(k).lower(): str(v) for k, v in carrier.items() if v is not None}

    # Validate traceparent syntax if present
    tp_val = normalized_carrier.get("traceparent")
    if tp_val and not parse_traceparent(tp_val):
        logger.debug("Malformed incoming traceparent header ignored", traceparent=tp_val)
        normalized_carrier.pop("traceparent", None)

    try:
        ctx = propagate.extract(normalized_carrier)
        return ctx
    except Exception as exc:
        logger.debug("Failed to extract OpenTelemetry trace context", error=str(exc))
        return None
