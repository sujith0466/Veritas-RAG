# Changelog

All notable changes to RAGuard AI are documented here.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-07-21

### Added (Phases 1-24)
- Complete enterprise RAG reliability platform across 24 implementation phases.
- Hybrid retrieval: Qdrant dense + BM25 sparse with Reciprocal Rank Fusion.
- Confidence engine: Coverage analysis, conflict detection, evidence scoring.
- Retry controller: Dynamic query rewriting and clarification loops.
- Grounded generation with LLM orchestration and provider abstraction.
- Reflection engine: Self-critique and iterative correction.
- NLI-based answer validation with citation verification.
- Knowledge health monitoring and automated parity checks.
- AI evaluation with golden datasets and benchmarking.
- Real-time executive dashboard with WebSocket live feeds.
- Multi-channel alert engine (Slack, PagerDuty, Email, Webhook).
- Self-healing governor with circuit breakers and model rotation.
- Multi-tenant ROI analytics with token quotas and forecasting.
- Production-hardening: connection pooling, chaos engineering, region failover.
- Enterprise observability: OpenTelemetry, Prometheus, structured logging.
- Enterprise security: DLP engine, RBAC, compliance auditing, key rotation.
- AI intelligence: threshold optimization and feedback processing.
- Global marketplace: SHA-256 verified configuration bundles.

### Infrastructure
- FastAPI 0.115 (async), Python 3.13, SQLAlchemy 2.x async.
- PostgreSQL 15, Qdrant 1.7+, Redis 7.
- Docker multi-stage build, Docker Compose orchestration.
- GitHub Actions CI/CD pipeline.
- Alembic migrations (0001-0020).

---

## [Unreleased]
- Frontend UI dashboard (React/Vue).
- ML-based NER for DLP.
- Helm chart for Kubernetes.
