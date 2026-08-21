# Tenant Isolation Architecture

## Design Principles
Veritas RAG guarantees strict multi-tenant isolation at the application, database, and vector storage layers.

## 1. Authentication Layer (Supabase)
- Each user authenticates via Supabase, returning a JWT token.
- The JWT contains the `tenant_id`.

## 2. API / Application Layer
- The `get_current_user` dependency parses the JWT and attaches the `tenant_id` to the request context.
- All subsequent database queries use this `tenant_id` context to append `WHERE tenant_id = <tenant_id>` to SQLAlchemy queries.

## 3. Relational Database Layer (PostgreSQL)
- The database enforces Row Level Security (RLS) if configured, though application-level filtering is primarily used.
- Every major table (`documents`, `workspaces`, etc.) contains a `tenant_id` column.

## 4. Vector Database Layer (Qdrant)
- **Strict Isolation**: Veritas RAG utilizes a separate Qdrant collection per tenant (`raguard_<tenant_id>`).
- This physically prevents Tenant A from retrieving Tenant B's vectors, even if the API layer fails to inject the correct filter payload.
- In multi-tenant shared collections (future roadmap), the `tenant_id` is passed as a must-match filter payload condition in every search query.

## Validation
- Stage 3 Certification confirmed that unauthorized cross-tenant requests yield 404 (Document Not Found) or 503/404 (Collection Not Found) rather than exposing data.
