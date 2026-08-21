# ADR-006: Provider Abstraction Layer

**Status**: Accepted
**Date**: 2026-07-17
**Author**: Platform Engineer & AI Infrastructure Engineer
**Phase**: Phase 1 — Foundation & Enterprise Setup

---

## Context

Veritas RAG integrates with multiple external services: Google Gemini (LLM), embedding models, Qdrant (vector DB), PostgreSQL, Redis, and Supabase Auth. Direct coupling to vendor SDKs in business logic creates tight dependencies that are expensive to change and hard to test.

## Decision

All external service integrations will be accessed through **abstract provider interfaces** defined in `backend/providers/`. Business logic in `backend/modules/` communicates only with these interfaces, never with vendor SDKs directly.

## Provider Interface Locations

```
backend/providers/
    llm/
        __init__.py
        base.py          # Abstract LLMProvider interface
        gemini.py        # Gemini implementation
    embeddings/
        __init__.py
        base.py          # Abstract EmbeddingProvider interface
    vector_db/
        __init__.py
        base.py          # Abstract VectorDBProvider interface
        qdrant.py        # Qdrant implementation
    storage/
        __init__.py
        base.py          # Abstract StorageProvider interface
    authentication/
        __init__.py
        base.py          # Abstract AuthProvider interface
        supabase.py      # Supabase implementation
```

## Rationale

- **Testability**: Unit tests inject mock providers without real network calls.
- **Vendor portability**: Switching from Gemini to OpenAI requires only a new provider implementation, not changes to business logic.
- **PRD alignment**: NFR Maintainability — "any individual module can be replaced without redesigning adjacent layers."

## Consequences

**Positive:**
- Full vendor portability for all external integrations.
- 100% unit-testable business logic.
- Provider selection configurable per environment.

**Negative:**
- Additional abstraction layer adds indirection.
- Provider interface must be designed carefully to not leak vendor-specific concepts.

## References
- PRD Section 18: NFR — Maintainability
- PRD Section 22: AI Model & Algorithm Responsibility Matrix
