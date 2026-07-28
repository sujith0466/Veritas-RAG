# ADR-004: Qdrant as the Vector Database

**Status**: Accepted
**Date**: 2026-07-17
**Author**: Database Architect
**Phase**: Phase 0 — Architecture Freeze

---

## Context

RAGuard AI stores document embeddings for dense retrieval and must support: metadata filtering for tenant isolation, efficient approximate nearest-neighbor search, and a Python-native async client. The vector store must be self-hostable for hackathon deployment without a cloud dependency.

## Decision

We will use **Qdrant** (v1.12.x) as the vector database, self-hosted via Docker.

## Rationale

| Criterion | Qdrant | Pinecone | Weaviate | pgvector |
|---|---|---|---|
| Self-hostable | Yes | No (managed only) | Yes | Yes |
| Metadata filtering | Rich payload filter | Basic | GraphQL | SQL WHERE |
| Python async client | Native | REST only | REST | SQLAlchemy async |
| Tenant isolation | Collection-per-tenant or payload filter | Index-per-tenant | Class-per-tenant | Schema-per-tenant |
| Performance at moderate scale | Excellent | Excellent | Good | Good (with indexing) |
| Open source | Yes (Apache 2.0) | No | Yes | Yes (PostgreSQL ext) |

Qdrant's payload filter system directly supports the metadata-based tenant isolation required by FR-RET-2 without application-layer filtering. Its async Python client integrates cleanly with FastAPI's async architecture.

## Consequences

**Positive:**
- Self-hosted — no cloud dependency for hackathon.
- Rich metadata filtering for tenant isolation at the retrieval layer.
- Async Python client native to FastAPI's architecture.
- gRPC support for high-throughput production use.

**Negative:**
- Requires operational expertise to tune for production scale (addressed in Phase 5).
- No managed cloud backup (addressed by volume mounts in Docker Compose for Phase 1).

## References
- PRD Section 9: Data Requirements
- PRD Section 5.2: Hybrid Retrieval (FR-RET-2, tenant isolation)
