<div align="center">
  <img src="docs/assets/banner.png.placeholder" alt="RAGuard AI Banner" width="100%">
</div>

<div align="center">

# RAGuard AI v1.0.0

### Enterprise Retrieval-Augmented Generation Reliability Platform

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.7-purple?logo=qdrant)](https://qdrant.tech)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

*Production-Grade AI Reliability for Enterprise RAG Deployments*

**[Documentation](https://docs.raguard.ai)** |
**[Quick Start](#installation)** |
**[Architecture](#architecture)** |
**[Contributing](CONTRIBUTING.md)** 

</div>

---

## 📖 Project Overview

**RAGuard AI** is an enterprise-grade Reliability, Validation, and Governance platform for Retrieval-Augmented Generation (RAG) systems. It sits between your application and your Large Language Model (LLM), ensuring that every AI output is grounded, validated, cited, and strictly controlled before reaching the end user.

## ❓ Problem Statement

Modern enterprise RAG systems suffer from:
1. **Hallucinations**: Models fabricate answers when context is poor.
2. **Brittle Architectures**: Provider outages break the entire pipeline.
3. **Lack of Explainability**: End-users don't know *why* an AI generated a response.
4. **Security Risks**: PII and sensitive data leak into LLM prompts.

## 💡 Solution: Why RAGuard?

RAGuard solves these issues by intercepting the standard AI workflow and applying rigorous, multi-stage validations.
- **Self-Healing Governor**: Autonomous model rotation and circuit breakers prevent downtime.
- **Hybrid Retrieval**: Dense (Qdrant) and Sparse (BM25) search with Reciprocal Rank Fusion ensures high recall.
- **Confidence Engine**: Automated scoring for context coverage and logical consistency.
- **Validation Layer**: NLI-based claim verification and citation checking.

## 🧩 Architecture

RAGuard implements a clean, event-driven Domain-Driven Design (DDD) architecture. 

<div align="center">
  <img src="docs/assets/architecture_diagram.png.placeholder" alt="Architecture Diagram" width="80%">
</div>

### System Workflow
1. **Request Intake**: API Gateway handles TLS, Rate Limiting, and JWT RBAC.
2. **Intelligence**: Query Intent Extraction and Data Loss Prevention (DLP) redaction.
3. **Retrieval**: Parallel Hybrid Search over Qdrant and BM25 indices.
4. **Generation**: Grounded generation via the LLM Provider Manager.
5. **Validation**: NLI Claim Extraction and Logical Reflection.
6. **Observability**: Asynchronous dispatch to Prometheus, OpenTelemetry, and structured audit logs.

## 📸 Screenshots

*(Placeholders for actual screenshots)*
- **Dashboard Overview**: `docs/assets/screenshots/dashboard.png.placeholder`
- **Analytics & Reliability**: `docs/assets/screenshots/analytics.png.placeholder`
- **Document Manager**: `docs/assets/screenshots/documents.png.placeholder`

## ✨ Features

- **End-to-End Enterprise RAG**: Complete document ingestion, chunking, and embedding pipeline.
- **Multi-Tenant Authentication**: Built on Supabase with seamless JWT integration.
- **LLM Provider Failover**: Automatic switching between OpenAI, Gemini, Anthropic, and Local models.
- **DLP & PII Masking**: On-the-fly redaction of sensitive data.
- **Glassmorphic UI**: Premium React + Tailwind frontend.
- **Observability**: OpenTelemetry tracing and Prometheus metrics built-in.

## 💻 Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.12+)
- **Database**: PostgreSQL (SQLAlchemy + Asyncpg)
- **Vector Store**: Qdrant
- **Caching**: Redis
- **Authentication**: Supabase (JWT)

### Frontend
- **Framework**: React 18 (Vite) + TypeScript
- **Styling**: Tailwind CSS + Framer Motion
- **State Management**: Zustand + React Query
- **Routing**: React Router v6

## 📂 Folder Structure

```text
raguard/
├── backend/            # FastAPI Python Backend
│   ├── api/            # API Gateway & Routers
│   ├── core/           # Security, Auth, Logging, Dependencies
│   ├── modules/        # DDD Domain Modules (Retrieval, Scoring, etc.)
│   ├── observability/  # Metrics & Traces
│   └── templates/      # Jinja2 Landing Pages
├── frontend/           # React + Vite Frontend
│   ├── src/
│   │   ├── components/ # Reusable UI Components
│   │   ├── pages/      # Route Components
│   │   ├── store/      # Zustand Stores
│   │   └── api/        # Axios Interceptors
├── docker/             # Docker configuration files
├── docs/               # Markdown Documentation
└── archive/            # Historical / Development Scripts
```

## 🚀 Installation & Docker Setup

Get RAGuard running locally in under 3 minutes using Docker Compose.

```bash
# 1. Clone the repository
git clone https://github.com/your-org/raguard.git
cd raguard

# 2. Configure environment variables
cp .env.example .env
# Edit .env to add your OPENAI_API_KEY and Supabase credentials.

# 3. Start the platform
docker-compose -f docker-compose.yml up --build -d

# 4. Verify health
curl http://localhost:8000/health
```

## ⚙️ Configuration & Environment Variables

RAGuard is heavily configurable via environment variables. See `.env.example` for defaults.
- `ENVIRONMENT`: `development`, `staging`, or `production`.
- `SUPABASE_URL` & `SUPABASE_JWT_SECRET`: For multi-tenant authentication.
- `OPENAI_API_KEY`, `GEMINI_API_KEY`: API Keys for the LLM Provider Manager.
- `LLM_PRIORITY_LIST`: Fallback order (e.g., `openai,gemini,anthropic`).

## 🔐 Authentication

RAGuard relies on **Supabase** for secure, scalable authentication.
- A **Demo User** (`demo@localhost` / `ChangeMe123!`) is automatically seeded in development environments.
- API requests are protected by JWT Bearer tokens validated against asymmetric or symmetric JWKS.

## 🧠 RAG Pipeline & LLM Provider Manager

The ingestion pipeline automatically splits PDFs/TXT files using semantic chunking. The **LLM Provider Manager** wraps external models in a standardized `ChatModel` interface, handling rate limits, backoffs, and transparent failover across providers if primary providers experience downtime.

## 📚 API Documentation

Once the backend is running, the interactive Swagger documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 🚢 Deployment

RAGuard is designed for Kubernetes or Docker Swarm.
1. Build the production image: `docker build -t raguard:1.0.0 --target prod .`
2. Configure your secret manager to inject production environment variables (see `.env.prod.example`).
3. Deploy behind a secure ingress controller (e.g., Nginx, Traefik) handling TLS termination.

See [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) for full instructions.

## 🚑 Troubleshooting & FAQ

- **Docker daemon fails to start?** Ensure Docker Desktop is running and WSL2 backend is enabled.
- **Authentication 401 Errors?** Ensure `SUPABASE_JWT_SECRET` matches your Supabase project settings.
- **Vector Search failing?** Check Qdrant logs to ensure collections were initialized.

See [FAQ.md](docs/FAQ.md) for more.

## 🛤️ Roadmap & Future Work

- [ ] **v1.1.0**: GraphRAG Integration for complex relational querying.
- [ ] **v1.2.0**: Native LangSmith/Langfuse telemetry integration.
- [ ] **v2.0.0**: Multi-modal Retrieval (Image + Text).

## ⚠️ Known Limitations

- Reranking currently supports only local cross-encoders. Managed services like Cohere Rerank are on the roadmap.
- PDF extraction relies on standard text layout. Heavy tables may require OCR plugins.

## 🤝 Contributing

We welcome contributions! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before submitting pull requests.

## ⚖️ License

RAGuard AI is licensed under the [MIT License](LICENSE).

## 🙏 Acknowledgements

- Built with [FastAPI](https://fastapi.tiangolo.com)
- Powered by [Qdrant](https://qdrant.tech)
- Styled with [Tailwind CSS](https://tailwindcss.com)

## 💬 Support

For enterprise support, please reach out via GitHub Issues or contact support@raguard.ai.
