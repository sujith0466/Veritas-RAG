"""Distributed tracing — OpenTelemetry span management and custom stage helpers."""

from .tracer import (get_current_trace_id, get_tracer, init_tracer,
                     trace_confidence_evaluation, trace_generation,
                     trace_query_processing, trace_reflection, trace_reporting,
                     trace_retrieval, trace_retry_controller, trace_stage)

__all__ = [
    "init_tracer",
    "get_tracer",
    "get_current_trace_id",
    "trace_stage",
    "trace_query_processing",
    "trace_retrieval",
    "trace_confidence_evaluation",
    "trace_retry_controller",
    "trace_generation",
    "trace_reflection",
    "trace_reporting",
]
