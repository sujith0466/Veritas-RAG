# Centralized Logging Strategy

RAGuard emits all logs in structured JSON format when `ENVIRONMENT=production`.

## Docker Compose Setup
The `docker-compose.prod.yml` uses the `json-file` driver with rotation:
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

## Ingestion
For production, run a log forwarder (FluentBit, Promtail, or Filebeat) to scrape the
`/var/lib/docker/containers/*/*.log` files and ship them to Datadog, Elasticsearch, or Loki.

All logs contain a `trace_id` for OpenTelemetry correlation.
