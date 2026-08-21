<div align="center">
  <img src="https://via.placeholder.com/150" alt="Veritas RAG Logo" width="120" height="120">

  <h1>Veritas RAG</h1>
  <p><strong>Veritas RAG — An Enterprise Knowledge Reliability Platform for Self-Correcting Retrieval-Augmented Generation</strong></p>

  <p>
    <a href="https://github.com/sujith0466/Veritas RAG/releases"><img src="https://img.shields.io/github/v/release/sujith0466/Veritas RAG?style=for-the-badge&color=success" alt="Release"></a>
    <a href="https://github.com/sujith0466/Veritas RAG/blob/main/LICENSE"><img src="https://img.shields.io/github/license/sujith0466/Veritas RAG?style=for-the-badge&color=blue" alt="License"></a>
    <a href="https://github.com/sujith0466/Veritas RAG/issues"><img src="https://img.shields.io/github/issues/sujith0466/Veritas RAG?style=for-the-badge&color=orange" alt="Issues"></a>
    <a href="https://github.com/sujith0466/Veritas RAG/stargazers"><img src="https://img.shields.io/github/stars/sujith0466/Veritas RAG?style=for-the-badge&color=yellow" alt="Stars"></a>
  </p>
</div>

<hr>

## 📖 Project Overview

**Veritas RAG** (historical product name: Veritas RAG; now Veritas RAG) is a production-grade, enterprise platform for Self-Correcting Retrieval-Augmented Generation (RAG). Designed from the ground up with a Domain-Driven Design (DDD) modular monolith architecture, Veritas RAG guarantees strict multi-tenant isolation, enterprise identity & session management, mathematical hallucination prevention, hybrid search indexing, and real-time observability.

---

## ✨ Core Capabilities & Architectural Pillars

### 1. Multi-Tenant Workspace Lifecycle & Governance (Epic 3 ✅ Frozen)
- **Lifecycle Management:** Dedicated workspace states (`ACTIVE`, `ARCHIVED`, `SUSPENDED`, `SOFT_DELETED`) with audit logging.
- **Slug Management:** URL-safe slug generation with collision detection and optimistic locking.
- **JSON Schema Settings:** Typed JSONB workspace configuration with versioned snapshot history, atomic rollback, and key-level diffing.
- **Dynamic Workspace Branding (F3.7):** WCAG AA color luminance & contrast ratio validation ($\ge 4.5:1$), real-time CSS root variable generation, Tailwind design token compilation, and Redis preview staging.
- **Enterprise Feature Flags (F3.8):** Multi-tier evaluation engine featuring a 7-step priority pipeline (Killswitch $\to$ Prerequisites $\to$ Workspace Overrides $\to$ User Targeting $\to$ Role Targeting $\to$ MurmurHash3 Percentage Rollouts $\to$ Date Windows), L1 in-memory / L2 Redis caching, and Redis Pub/Sub cluster invalidation.

### 2. Enterprise Authentication & Identity (Epic 2 ✅ Frozen)
- **Zero Client-Side Trust:** Secure server-side authentication utilizing Argon2id password hashing and cryptographic single-use tokens.
- **Session Tracking & Instant Revocation:** Redis-backed token revocation, active session monitoring, and remote session termination.
- **Multi-Factor & Recovery:** 6-digit time-based email OTP verification, cryptographic password reset, and email confirmation flows.
- **Enterprise SSO:** Extensible OAuth2/OIDC `IdentityProvider` framework supporting Google, GitHub, and custom enterprise providers.

### 3. Foundational Infrastructure & Observability (Epic 1 ✅ Frozen)
- **Async PostgreSQL 15+:** SQLAlchemy 2.0 async engine with PgBouncer connection pooling and tenant-partitioned schemas.
- **Distributed Redis 7+:** Multi-tier caching, distributed mutex locking, token blacklisting, and rate limiting.
- **Vector Search (Qdrant 1.7+):** Tenant-isolated dense vector collections with HNSW indexing and metadata filtering.
- **Object Storage (S3 / MinIO):** Encrypted object store with presigned URL workflows and WORM / Object Lock audit trails.
- **Full Observability:** OpenTelemetry distributed tracing, structured JSON logging with PII scrubbing, Prometheus metric scrapers, and Kubernetes health probes (`/health/live`, `/health/ready`, `/health/startup`).

### 4. Knowledge Processing Pipeline (Epic 6 ✅ Frozen)
- **Redis & Celery Queue Topology (F6.1):** Multi-tier asynchronous priority queues (`critical`, `high`, `normal`, `low`) with distributed locking, idempotency gating, and worker heartbeats.
- **OCR & Multi-Engine Text Extraction (F6.2):** Unified extraction pipeline with Tesseract/EasyOCR fallback, layout preservation, and extraction contract verification.
- **Token-Aware Semantic Chunking (F6.3):** Context-aware sliding chunk windows, overlap preservation, and canonical document manifest generation.
- **Embedding Generation & Vector Indexing (F6.4 & F6.5):** Batch vectorization with dimension validation, payload enrichment, and multi-tenant Qdrant collection indexing.
- **ProcessingJob Lifecycle & Observability (F6.6):** Granular step duration tracking, error code mapping, and OpenTelemetry trace propagation.
- **Dead Letter Queue Engine (F6.7):** Automated classification of recoverable vs. fatal ingestion failures with administrative remediation and retry workflows.
- **S3 Presigned Upload Lifecycle (F6.8):** Secure object lock, checksum validation, and automated asynchronous pipeline triggering upon upload completion.

### 5. Knowledge Base & Vector Infrastructure (Epic 7 ✅ Frozen)
- **Knowledge Base Inspection (F7.1):** End-to-end workspace statistics and vector parity audits between PostgreSQL chunks and Qdrant.
- **Knowledge Health Scoring (F7.2):** 4-dimensional mathematical scoring engine (Coverage, Freshness, Quality, Reliability) with automated remediation recommendations.
- **Staleness Detection (F7.3):** Exponential decay evaluation with background alerting and bulk archiving workflows.
- **Zero-Downtime Re-Indexing (F7.4):** Atomic Qdrant alias namespace swaps, supporting staging collection parity checks and fallback rollbacks.

### 6. Advanced RAG & Confidence Engine
- **Hybrid Retrieval:** Fuses Dense Vector Search (Qdrant) with Sparse Keyword Search (BM25) using Reciprocal Rank Fusion (RRF).
- **Contextual Reranking:** Cross-Encoder neural rescoring to maximize precision.
- **Confidence Evaluation:** Mathematical hallucination prevention that evaluates evidence strength, relevance, and semantic overlap before LLM generation.

---

## 🏗️ System Architecture

```mermaid
graph TD
    Client[Client UI / React + Vite] --> Gateway[FastAPI Gateway]

    subgraph "Core Security & Auth"
        Gateway --> Auth[Auth & Session Manager]
        Auth --> RBAC[Role-Based Access Control]
        Auth --> RedisAuth[(Redis Session Cache)]
    end

    subgraph "Workspace & Governance Layer"
        Gateway --> Workspaces[Workspace Management Service]
        Gateway --> Branding[Branding & CSS Compiler]
        Gateway --> Flags[Feature Flag Evaluation Engine]
        Flags --> L1Cache[L1 In-Memory LRU]
        Flags --> L2Cache[(Redis L2 Cache & Pub/Sub)]
    end

    subgraph "Data & Persistence"
        Workspaces --> PG[(PostgreSQL Database)]
        Auth --> PG
        Flags --> PG
        Gateway --> S3[(S3 Object Storage)]
    end

    subgraph "RAG Pipeline"
        Gateway --> Ingestion[Document Ingestion]
        Gateway --> Retrieval[Hybrid Retrieval Engine]
        Ingestion --> Qdrant[(Qdrant Vector DB)]
        Retrieval --> Qdrant
        Retrieval --> Reranker[Cross-Encoder Reranker]
        Reranker --> Confidence[Confidence Engine]
        Confidence --> LLM[LLM Generation]
    end
```

---

## 🛠️ Technology Stack

| Component | Technology | Version | Description |
|---|---|---|---|
| **Backend Framework** | FastAPI (Python) | 0.109+ | High-performance asynchronous API server |
| **Relational Database** | PostgreSQL + asyncpg | 15+ | Multi-tenant transactional persistence |
| **ORM & Migrations** | SQLAlchemy 2.0 + Alembic | 2.0+ | Typed async models & schema versioning |
| **In-Memory Cache & Broker** | Redis | 7+ | L1/L2 caching, Pub/Sub, distributed locks |
| **Vector Database** | Qdrant | 1.7+ | Tenant-partitioned vector indexing & search |
| **Object Storage** | AWS S3 / MinIO | - | Presigned uploads and immutable audit logs |
| **Frontend Framework** | React 18 + Vite | 5+ | Responsive TypeScript SPA with Tailwind CSS |
| **State Management** | Zustand + React Context | 4.5+ | Global state container & context providers |
| **Observability** | OpenTelemetry + Prometheus | - | Tracing, structured logs, and metrics |

---

## 🚀 Getting Started

### 1. Prerequisites
- Docker Engine 24.0+ & Docker Compose v2.0+
- Python 3.11+ / Node.js 18+ (for local native development)

### 2. Setup Environment
```bash
git clone https://github.com/sujith0466/Veritas RAG.git
cd Veritas RAG
cp .env.example .env
```

### 3. Launch with Docker Compose
```bash
docker-compose up --build -d
make migrate
```
Services initialized:
- **FastAPI Backend:** `http://localhost:8000` (Swagger UI at `/docs`)
- **React Frontend:** `http://localhost:5173`
- **PostgreSQL:** `localhost:5432`
- **Redis:** `localhost:6379`
- **Qdrant:** `localhost:6333`

### 4. Developer Onboarding & QA
To automatically set up a QA Admin account, tenant, and populate sample enterprise data:
```bash
make qa-bootstrap
```
You can now log in at `http://localhost:5173/auth/login` using the credentials defined in your `.env` file (Default: `QA_EMAIL` and `QA_PASSWORD`).

To reset your environment (wipes the database and restarts from scratch):
```bash
make reset
```

---

## 📚 API Endpoint Overview

| Category | Endpoint | Method | Description |
|---|---|---|---|
| **Auth** | `/api/v1/auth/register` | `POST` | User registration with Argon2id |
| **Auth** | `/api/v1/auth/login` | `POST` | Dual-token authentication |
| **Auth** | `/api/v1/auth/refresh` | `POST` | Refresh token rotation |
| **Auth** | `/api/v1/auth/sessions` | `GET` | List active sessions |
| **Workspaces** | `/api/v1/workspaces` | `GET`, `POST` | List & provision workspaces |
| **Workspaces** | `/api/v1/workspaces/{id}` | `GET`, `PATCH`, `DELETE` | Workspace CRUD & lifecycle |
| **Workspaces** | `/api/v1/workspaces/{id}/archive` | `POST` | Archive workspace |
| **Workspaces** | `/api/v1/workspaces/{id}/restore` | `POST` | Restore archived workspace |
| **Branding** | `/api/v1/workspaces/{id}/branding` | `GET` | Get compiled CSS variables & tokens |
| **Branding** | `/api/v1/workspaces/{id}/branding/preview` | `POST` | Stage branding draft preview |
| **Branding** | `/api/v1/workspaces/{id}/branding/publish` | `POST` | Publish branding with cache bust |
| **Feature Flags**| `/api/v1/feature-flags` | `GET`, `POST` | Global feature flag catalog |
| **Feature Flags**| `/api/v1/feature-flags/{key}/killswitch` | `POST` | Emergency global killswitch toggle |
| **Feature Flags**| `/api/v1/workspaces/{id}/feature-flags/evaluate` | `GET` | Bulk workspace flag evaluation |

---

## 📂 Repository Directory Layout

```
Veritas RAG/
├── backend/
│   ├── api/v1/             # FastAPI routers, request/response schemas, dependencies
│   ├── core/               # Auth context, security, config, events, logging
│   ├── database/           # Async database engine, sessions, Alembic migrations
│   ├── models/entities/    # SQLAlchemy domain entities (Workspaces, Flags, Auth)
│   ├── repositories/       # Async data repositories
│   ├── services/           # Domain business logic (Workspace, FeatureFlag, Auth)
│   └── tests/              # Unit & integration test suites
├── frontend/
│   ├── src/
│   │   ├── components/     # UI components, layouts, guards
│   │   ├── providers/      # React context providers (Auth, Branding, FeatureFlag)
│   │   ├── services/       # Typed API clients
│   │   ├── stores/         # Zustand global stores
│   │   └── pages/          # Application view pages
│   └── tests/              # E2E & unit test suites
├── docs/                   # Architecture specs, ADRs, runbooks, and archives
│   ├── architecture/       # Detailed domain architecture specifications
│   └── archive/            # Historical artifacts for Epics 1, 2, 3
├── infrastructure/         # Terraform IaC, Kubernetes manifests, Docker scripts
├── docker-compose.yml      # Multi-container local orchestration
└── README.md
```

---

## 🗺️ Program 2 Implementation Roadmap

| Epic | Description | Status | Progress |
|---|---|---|---|
| **Epic 1** | Infrastructure & Foundation Layer | ✅ **FROZEN** | 100% |
| **Epic 2** | Authentication & Identity Management | ✅ **FROZEN** | 100% |
| **Epic 3** | Workspace Architecture & Management | ✅ **FROZEN** | 100% |
| **Epic 4** | User & Role Management (RBAC / Invitations / Profiles) | ✅ **FROZEN** | 100% |
| **Epic 5** | Document & Folder Management | ✅ **FROZEN** | 100% |
| **Epic 6** | Document Ingestion Pipeline | ✅ **FROZEN** | 100% |
| **Epic 7** | Vector Search & Qdrant Integration | ✅ **FROZEN** | 100% |
| **Epic 8** | AI Platform Wrapper | ✅ **FROZEN** | 100% |
| **Epic 9** | Chat Platform | ✅ **FROZEN** | 100% |
| **Epic 10** | RAG Health & Analytics | ✅ **FROZEN** | 100% |
| **Epic 11** | Notifications (Email, Webhooks, In-App) | ✅ **FROZEN** | 100% |
| **Epic 12** | Admin Portal (Workspace & Platform Admin, RBAC, Quotas, Audit Logs) | ✅ **FROZEN** | 100% |
| **Epic 13** | Policy & Configuration (Quotas, Usages, Retention Lifecycles) | ✅ **FROZEN** | 100% |
| **Epic 14** | Observability & Production Monitoring (OTel, Metrics, Grafana, Alerts, Health Probes) | ✅ **FROZEN** | 100% |
| **Epic 15** | Production Hardening & Enterprise Security | ✅ **CERTIFIED BASELINE** | 100% (Baseline Established) |
| **Epic 16** | Production Launch & Final Handover | ⏳ **NEXT ACTIVE** | 0% |

---

## 📄 License & Governance

Licensed under the MIT License. See [LICENSE](LICENSE) for details.
Copyright (c) 2026 Sujith Kumar.
