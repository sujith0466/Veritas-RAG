# ADR-001: FastAPI as the Backend Framework

**Status**: Accepted
**Date**: 2026-07-17
**Author**: Principal Software Architect
**Phase**: Phase 0 — Architecture Freeze

---

## Context

Veritas RAG requires a backend web framework capable of serving a high-throughput, async AI pipeline. The framework must support async-first I/O (critical for non-blocking LLM and database calls), automatic OpenAPI documentation, strong type validation, and a robust dependency injection system. The team is proficient in Python.

## Decision

We will use **FastAPI** (v0.115.x) as the backend web framework.

## Rationale

| Criterion | FastAPI | Django REST | Flask |
|---|---|---|---|
| Async-first | Native (ASGI) | Limited (WSGI-first) | Limited (WSGI-first) |
| Type validation | Pydantic v2 native | Serializers (manual) | No built-in |
| Auto OpenAPI docs | Built-in | Plugin required | Plugin required |
| Dependency injection | Built-in | Not native | Not native |
| Performance | High (Starlette) | Medium | Medium |
| Python typing | First-class | Partial | Optional |

FastAPI's native integration with Pydantic v2 is critical for the strict input validation required by the PRD (FR-QU validation, security input hardening). The ASGI architecture allows the self-correction loop, retrieval, and LLM calls to run concurrently without thread-pool exhaustion.

## Consequences

**Positive:**
- Automatic OpenAPI spec generation from Pydantic models.
- Native async/await throughout the stack.
- Dependency injection enables testable, clean architecture.
- Pydantic v2 strict mode enforces the input validation contract from the PRD.

**Negative:**
- Smaller ecosystem compared to Django for admin/ORM tooling (mitigated by SQLAlchemy).
- Less opinionated — team must define conventions (addressed by this ADR collection).

## References
- PRD Section 8: Tech Stack
- NFR: Scalability (horizontal scaling of services)
