<div align="center">

# RAGuard AI

### Enterprise Retrieval-Augmented Generation Reliability Platform

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Version](https://img.shields.io/badge/Version-1.0.0-brightgreen)](CHANGELOG.md)

*Production-Grade AI Reliability for Enterprise RAG Deployments*

</div>

---

## Overview

RAGuard AI is an enterprise-grade Reliability, Validation, and Governance platform for
Retrieval-Augmented Generation (RAG) systems. It detects insufficient context, identifies
conflicting evidence, rewrites ambiguous queries, and validates generated answers before
they reach end-users — ensuring trustworthy AI outputs at scale.

## Key Features

- **Hybrid Retrieval** — Dense (Qdrant) + Sparse (BM25) with Reciprocal Rank Fusion
- **Confidence Engine** — Coverage analysis, conflict detection, evidence strength scoring
- **Retry Controller** — Dynamic query rewriting and clarification loops
- **Grounded Generation** — LLM-anchored generation with citation verification
- **Reflection & Validation** — NLI-based claim validation and answer grounding
- **Self-Healing** — Autonomous circuit-breaker failover and model rotation
- **Enterprise Security** — DLP / PII redaction, RBAC, compliance auditing
- **Observability** — OpenTelemetry tracing, Prometheus metrics, structured JSON logging
- **Marketplace** — SHA-256 verified tenant configuration bundles

## Quick Start

```bash
# Clone repository
git clone https://github.com/your-org/raguard.git
cd raguard

# Configure environment
cp .env.example .env

# Start with Docker
docker-compose up -d

# Health check
curl http://localhost:8000/health
```

## Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](docs/INSTALLATION_GUIDE.md) | Setup instructions |
| [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) | Production deployment |
| [API Reference](docs/API_REFERENCE.md) | REST API documentation |
| [Architecture](docs/SYSTEM_ARCHITECTURE.md) | System design |
| [Security Guide](docs/SECURITY_GUIDE.md) | Security configuration |
| [Operator Guide](docs/OPERATOR_GUIDE.md) | Day-2 operations |

## License

MIT License. See [LICENSE](LICENSE).
