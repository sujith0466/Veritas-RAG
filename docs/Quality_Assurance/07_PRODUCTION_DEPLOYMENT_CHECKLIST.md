# Production Deployment Checklist

## Pre-Deployment Verification
- [x] All automated tests (unit, integration, e2e) pass.
- [x] Infrastructure certification (Stage 1) is complete.
- [x] RAG Pipeline certification (Stage 2) is complete.
- [x] Performance and concurrency load testing (Stage 3) is complete.
- [x] Database migrations are applied.
- [x] Celery queues (`ingestion`, `embeddings`, `retrieval`, `default`) are properly configured.
- [x] Qdrant collections are backed up and snapshot mechanisms are verified.

## Deployment Steps
1. **Database Schema Update**: Run Alembic migrations against the production PostgreSQL instance.
2. **Redis Flush**: (Optional but recommended) Flush volatile Redis cache keys to prevent stale configuration loads.
3. **API Deployment**: Deploy the FastAPI backend image with proper environment variables (`SUPABASE_JWT_SECRET`, `OPENAI_API_KEY`, etc.).
4. **Worker Deployment**: Deploy the Celery worker image. Ensure the `NullPool` database connection strategy is active via the `sys.argv` detection check to prevent connection pool exhaustion.
5. **Qdrant Health Check**: Verify Qdrant is accessible and cluster state is healthy.

## Post-Deployment Validation
- Monitor API metrics and error rates.
- Execute a smoke test using a synthetic tenant.
- Verify that document ingestion works end-to-end.
- Check Celery logs for OCR or embedding model fallback errors.
