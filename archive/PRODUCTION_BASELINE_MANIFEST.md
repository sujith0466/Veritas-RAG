# Production Baseline Manifest

This manifest certifies the formal configuration of the RAGuard Enterprise v1.0.0 Production Infrastructure.

## Deployment Topology
- **Edge Proxy**: Nginx 1.25-alpine (TLS termination, HSTS)
- **API Runtime**: RAGuard multi-stage Docker container (Python 3.13)
- **Orchestration**: Docker Compose (`docker-compose.prod.yml` with `update_config`)
- **Primary Data**: PostgreSQL 15 (Docker / Managed Service compatible)
- **Vector DB**: Qdrant 1.7 (Docker / Managed Service compatible)
- **Cache & Locks**: Redis 7

## Observability Configuration
- **Metrics Endpoint**: `/observability/v1/metrics`
- **Prometheus Scrape Interval**: 15s
- **Grafana Dashboards**: `raguard_dashboard.json`
- **Log Forwarding**: Structured JSON logs via `json-file` Docker driver.

## Security Baseline
- Secrets injected dynamically via external Secret Manager.
- Database backups executed periodically via `scripts/dr/backup_db.sh`.
- Network layer restricts API access directly, funneling strictly through port 443 on Nginx.

## Certification
**Status**: The Production Deployment Infrastructure is **OFFICIALLY FROZEN**.
**Timestamp**: 2026-07-21T01:33:14Z
