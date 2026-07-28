# RAGuard AI — Production Readiness Checklist

This checklist is the mandatory Go-Live approval document before deploying v1.0.0 to production.

## 1. Infrastructure & Networking
- [ ] Compute resources provisioned (CPU/Memory requirements met)
- [ ] DNS records configured (`api.raguard.yourdomain.com`)
- [ ] Firewall / Security Groups restricted to necessary ports (443/80/SSH)

## 2. Security & TLS
- [ ] TLS Certificates provisioned and mounted to Reverse Proxy
- [ ] HSTS enabled (via `ENVIRONMENT=production`)
- [ ] Secret Management system integrated (no hardcoded secrets)
- [ ] Environment Variables (`.env.prod`) validated

## 3. Platform & Containers
- [ ] Docker / K8s orchestrator configured
- [ ] Reverse Proxy (Nginx/Traefik) configured for routing and rate limiting
- [ ] Multi-stage Docker image built and pushed to private registry

## 4. Observability
- [ ] Prometheus scraping `/observability/v1/metrics`
- [ ] Grafana Dashboards imported and functioning
- [ ] Centralized Logging (e.g., ELK, Datadog) ingesting structured JSON logs
- [ ] Alerting channels (Slack/PagerDuty) configured for 5xx and latency spikes

## 5. Resilience
- [ ] Postgres automated backups scheduled (`pg_dump`)
- [ ] Qdrant snapshot routine configured
- [ ] Disaster Recovery restoration procedure tested
- [ ] High Availability (multi-node / replicas) verified

## 6. Validation
- [ ] Production Health Checks passing (`/health`)
- [ ] End-to-End Smoke Test executed
- [ ] Performance Load Testing executed (SLAs met)

## 7. Compliance & Certification
- [ ] Stage 1 Release Assets verified
- [ ] All Runbooks generated and accessible to SRE team
- [ ] `production-baseline-manifest.md` signed and frozen
