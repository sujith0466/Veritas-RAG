# RAGuard AI — Project Overview

## Problem Statement

Enterprise RAG deployments suffer from unreliable AI outputs caused by:
- Insufficient retrieval context
- Conflicting evidence across documents
- Hallucinated or ungrounded answers
- Lack of confidence scoring and explainability

## Solution

RAGuard AI wraps any RAG pipeline with a multi-layer reliability engine:

1. **Query Intelligence** — Normalizes, validates, and extracts intent from user queries.
2. **Hybrid Retrieval** — Combines dense (semantic) and sparse (keyword) search with result fusion.
3. **Confidence Engine** — Scores retrieved context for coverage and detects conflicts.
4. **Retry Controller** — Rewrites or clarifies low-confidence queries automatically.
5. **Grounded Generation** — Produces LLM outputs anchored to verified source documents.
6. **Validation** — NLI-based claim extraction and citation verification.
7. **Observability** — Comprehensive tracing, metrics, and audit logging.

## Architecture Summary

- **Backend**: Python 3.13, FastAPI, SQLAlchemy (async)
- **Vector DB**: Qdrant (dense embeddings)
- **Relational DB**: PostgreSQL (metadata, audit, analytics)
- **Cache**: Redis (quotas, circuit-breaker state)
- **Observability**: OpenTelemetry, Prometheus
- **Security**: DLP engine, JWT RBAC, compliance auditing
- **Deployment**: Docker, Docker Compose, GitHub Actions CI/CD

## Phase Roadmap (Completed)

| Wave | Phases | Scope |
|------|--------|-------|
| Wave 1 | 1-5 | Core infrastructure, query intelligence, hybrid retrieval |
| Wave 2 | 6-10 | Confidence engine, retry controller, generation |
| Wave 3 | 11-15 | Reflection, validation, knowledge health, evaluation |
| Wave 4 | 16-20 | Dashboard, alerting, self-healing, analytics, resilience |
| Wave 5 | 21-24 | Observability, security, intelligence optimization, marketplace |
