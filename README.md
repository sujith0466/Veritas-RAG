<div align="center">
  <img src="docs/assets/banner.png.placeholder" alt="RAGuard AI Banner" width="100%">
</div>

<div align="center">

# RAGuard AI

### Enterprise Retrieval-Augmented Generation Reliability Platform

[![Python 3.13+](https://img.shields.io/badge/Python-3.13%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.7-purple?logo=qdrant)](https://qdrant.tech)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/github/v/release/your-org/raguard)](https://github.com/your-org/raguard/releases)

*Production-Grade AI Reliability for Enterprise RAG Deployments*

**[Documentation](https://docs.raguard.ai)** |
**[Quick Start](#quick-start)** |
**[Architecture](#architecture)** |
**[Contributing](CONTRIBUTING.md)** |
**[Discussions](https://github.com/your-org/raguard/discussions)**

</div>

---

## 📖 Overview

**RAGuard AI** is an enterprise-grade Reliability, Validation, and Governance platform for Retrieval-Augmented Generation (RAG) systems. It sits between your application and your LLM, ensuring that every AI output is grounded, validated, cited, and trustworthy.

Modern enterprise RAG systems suffer from hallucinated answers, poor context retrieval, and lack of explainability. RAGuard solves this by providing:
- **Hybrid Retrieval** — Dense & Sparse search with Reciprocal Rank Fusion.
- **Confidence Engine** — Automated scoring for context coverage and conflict.
- **Self-Healing Governor** — Autonomous model rotation and circuit breakers.
- **Validation Layer** — NLI-based claim verification and citation checking.

## 🚀 Quick Start

Get RAGuard running locally in under 3 minutes using Docker.

```bash
# 1. Clone the repository
git clone https://github.com/your-org/raguard.git
cd raguard

# 2. Configure environment variables
cp .env.example .env
# Edit .env to add your OPENAI_API_KEY

# 3. Start the platform
docker-compose up -d

# 4. Verify health
curl http://localhost:8000/health
```

> **Next Steps:** Check out the [Interactive API Quick Start](docs/developer/API_QUICKSTART.md) to make your first query!

## 🧩 Architecture

RAGuard implements a clean, event-driven Domain-Driven Design (DDD) architecture. 

<div align="center">
  <img src="docs/assets/architecture_diagram.png.placeholder" alt="Architecture Diagram" width="80%">
</div>

| Layer | Responsibility |
|-------|---------------|
| **API Gateway** | TLS termination, Rate Limiting, RBAC (FastAPI/Nginx) |
| **Intelligence** | Query Intent Extraction, DLP Redaction |
| **Retrieval** | Hybrid Search (Qdrant + BM25) |
| **Generation** | Grounded Provider Abstraction |
| **Validation** | Reflection & NLI Claim Extraction |
| **Observability**| Prometheus, OpenTelemetry, Structured Logs |

## 📚 Documentation Directory

| Resource | Description |
|----------|-------------|
| 🌐 **[Official Docs Site](https://docs.raguard.ai)** | Comprehensive MkDocs website |
| 🛠️ **[Installation Guide](docs/INSTALLATION_GUIDE.md)** | Setup instructions |
| 🧑‍💻 **[Developer Guide](docs/DEVELOPER_GUIDE.md)** | Extending RAGuard |
| 🛡️ **[Security Guide](docs/SECURITY_GUIDE.md)** | DLP & Audit config |
| ⚙️ **[Operator Guide](docs/OPERATOR_GUIDE.md)** | Day-2 operations |
| 💼 **[Portfolio & Showcase](docs/showcase/PROJECT_OVERVIEW.md)** | Media kit & One-Pagers |

## 🤝 Community & Support

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) to get started.

- **Issues**: Use [GitHub Issues](https://github.com/your-org/raguard/issues) for bug reports and feature requests.
- **Discussions**: Join [GitHub Discussions](https://github.com/your-org/raguard/discussions) for architecture debates and Q&A.
- **Security**: Report vulnerabilities per our [Security Policy](SECURITY.md).

## 📄 License

RAGuard AI is licensed under the MIT License. See [LICENSE](LICENSE) for details.
