# ADR-005: Domain-Oriented Modular Architecture

**Status**: Accepted
**Date**: 2026-07-17
**Author**: Principal Software Architect
**Phase**: Phase 1 — Foundation & Enterprise Setup

---

## Context

RAGuard AI has 12 distinct AI modules (Query Intelligence, Hybrid Retrieval, Retrieval Reliability, Self-Correction, Reflection, Query Rewrite, Clarification, Answer Validation, Reliability Scoring, Knowledge Health, Evaluation, Analytics). A flat services/ directory would make ownership, testing, and future team assignment ambiguous as the system grows through its 22 phases.

## Decision

We will organize business capabilities into **domain-oriented modules** under `backend/modules/`, where each module owns its own API routes, schemas, services, repositories, and models. Shared functionality resides in `backend/core/` and `backend/infrastructure/`.

## Module Structure

```
backend/modules/<domain>/
    __init__.py
    api/
        routes.py
        schemas.py
    services/
        <domain>_service.py
    repositories/
        <domain>_repository.py
    models/
        <domain>_models.py
```

## Domains (Phase 1 reserved, implementation phased)

| Module | Phase |
|---|---|
| auth | Phase 1 |
| ingestion | Phase 2 |
| retrieval | Phase 2 |
| reflection | Phase 3 |
| retry | Phase 3 |
| validation | Phase 3 |
| evaluation | Phase 4 |
| analytics | Phase 4 |
| dashboard | Phase 4 |

## Rationale

- **Ownership**: Each module has a clear owner and boundary.
- **Testability**: Modules can be tested in isolation with mocked dependencies.
- **Scalability**: Modules can be extracted to separate services if the monolith needs to be split.
- **PRD alignment**: Module boundaries map directly to PRD Section 20 (Core Modules).

## Consequences

**Positive:**
- Clear separation of concerns from day one.
- Maps directly to the 12 PRD modules — no translation needed.
- Enables parallel team development on separate modules.

**Negative:**
- More files than a flat structure for simple CRUD.
- Requires discipline to avoid cross-module direct imports (enforced by code review).

## Cross-Module Communication Rule

Modules must NOT import from each other directly. Cross-module communication goes through:
1. The service layer of the calling module (orchestration)
2. Internal events (via `backend/core/events/`)
3. Shared interfaces in `backend/core/`

## References
- PRD Section 20: Core Modules
- PRD Section 21: Module Dependencies Matrix
