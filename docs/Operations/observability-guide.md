# Observability Guide

## Metrics (Prometheus)

Metrics are exposed at `GET /observability/v1/metrics` in Prometheus text format.

Key metrics:
| Metric | Type | Description |
|--------|------|-------------|
| `raguard_http_requests_total` | Counter | Total HTTP requests |
| `raguard_http_errors_total` | Counter | Total HTTP 5xx errors |
| `raguard_tokens_consumed_total` | Counter | Total LLM tokens used |
| `raguard_http_request_duration_seconds` | Histogram | Request latency distribution |

## Distributed Tracing (OpenTelemetry)

Configure an OTLP endpoint in `.env`:
```
OTLP_ENDPOINT=http://jaeger:4317
```

Each request is automatically traced with:
- `trace_id` (W3C format)
- `span_id`
- `operation_name`
- `duration_ms`

## Structured Logging

All logs are emitted as JSON:
```json
{
  "timestamp": "2026-07-21T00:00:00Z",
  "level": "INFO",
  "message": "Query processed successfully",
  "logger": "raguard",
  "trace_id": "abc123",
  "span_id": "def456"
}
```

## Health Endpoints

| Endpoint | Kubernetes Probe |
|----------|----------------|
| `/health/liveness` | Liveness |
| `/health/readiness` | Readiness |
| `/health` | Manual check |

## Alerting

Alerts are dispatched via the Phase 17 alert engine.
Supported channels: Slack, PagerDuty, Email, Generic Webhook.
