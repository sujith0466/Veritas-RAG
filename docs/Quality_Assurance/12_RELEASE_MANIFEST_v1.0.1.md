# Release Manifest: Veritas RAG (v1.0.1)

## 1. Release Overview
- **Release Version**: v1.0.1 (Production Baseline)
- **Release Date**: July 28, 2026
- **Planned Git Tag**: `v1.0.1`
- **Repository Status**: Clean / Verified
- **Production Baseline Identifier**: RAGuard_Core_v1.0.1

## 2. Technology Stack
- **Backend Framework**: FastAPI (Python 3.12+)
- **Database**: PostgreSQL 16
- **Database ORM**: SQLAlchemy 2.0 (Async)
- **Vector Database**: Qdrant (Dockerized)
- **Background Workers**: Celery / Redis
- **Frontend Framework**: React 18 / TypeScript / Tailwind CSS
- **Authentication**: Supabase (JWT / Auth)

## 3. Architecture Summary
- **Database Architecture**: Hybrid pooling. `QueuePool` restricts the API layer to bounded PgBouncer connections. `NullPool` enables Celery workers to safely execute pre-fork concurrent operations without asyncio Future detachment errors.
- **Vector Database**: Multi-tenant isolation utilizing one physical Qdrant collection (`raguard_<tenant_id>`) per tenant. HNSW indexing, Cosine Distance, 384 dimensions.
- **Authentication**: Stateless JWT validation via asymmetric `PyJWKClient` verification or fallback symmetric `HS256` shared secret.
- **Security**: Robust `tenant_id` context propagation for both SQL Row-Level-Security paradigms and Application-Level payload filtering. Cross-tenant bounds strictly enforce 404/503.
- **LLM Providers**: Modular architecture via `LLMProviderManager`. Default generation via OpenAI (`gpt-4o-mini`).
- **Embedding Model**: `BAAI/bge-small-en-v1.5` (Local Inference via HuggingFace).

## 4. Completed Certifications
- ✅ **Stage 1**: Infrastructure & Reliability (Docker, Pooling, Resilience)
- ✅ **Stage 2**: RAG Pipeline & Ingestion Validation
- ✅ **Stage 3**: Concurrency & Performance Load Testing

## 5. Performance Baseline
- **Concurrency Support**: 50 concurrent requests cleanly supported by Auth endpoints without resource exhaustion.
- **Latency (Auth/Health)**: Average ~103ms / P95 ~184ms
- **Latency (Search/Retrieval)**: Extremely CPU-bound under concurrency (Average ~45s, P95 ~65s at 25 concurrent connections) due to local embedding inference bottlenecking the async loop.

## 6. Known Limitations
1. **Search Concurrency Bottleneck**: Intensive concurrent search requests cause synchronous event-loop starvation during embedding generation. (Slated for refactor in `v1.1.0` via asynchronous embedding offloading or external API providers).
2. **OCR Fallback Image**: Default Celery Docker image lacks native `tesseract-ocr` binaries; heavily scanned PDFs with <50 words trigger `OCR_002` exception.
3. **Empty Tenant Searches**: Querying a newly created tenant before document ingestion triggers Qdrant Collection Not Found (`503`).

## 7. Deployment Requirements & Rollback Strategy
- **Deployment Requirements**: Requires Supabase backend, OpenAI API Key, PostgreSQL, Redis, and Qdrant deployed as per Docker Compose manifest. Set `SUPABASE_JWT_SECRET` in `.env`.
- **Rollback Strategy**: Application is largely stateless; rollback by reverting Docker image tags to `v1.0.0` or prior `main` commits. Alembic migrations should be downgraded via `alembic downgrade -1` if schema changes occurred.

## 8. References
- [Infrastructure Certification](01_INFRASTRUCTURE_CERTIFICATION.md)
- [Pipeline Certification](02_RAG_PIPELINE_CERTIFICATION.md)
- [Deployment Checklist](07_PRODUCTION_DEPLOYMENT_CHECKLIST.md)
- [Tenant Isolation](08_TENANT_ISOLATION_ARCHITECTURE.md)
- [Disaster Recovery](10_DISASTER_RECOVERY_PLAN.md)
- [Final Verdict](10_RELEASE_CERTIFICATION.md)
