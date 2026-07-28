# ADR-003: Supabase Authentication

**Status**: Accepted
**Date**: 2026-07-17
**Author**: Security Architect
**Phase**: Phase 0 — Architecture Freeze

---

## Context

RAGuard AI requires a production-grade authentication system that supports email/password login, JWT-based session management, and future extensibility (OAuth, SSO). The system must be operable by a small team without managing an auth server from scratch, and must integrate with the chosen PostgreSQL database (Supabase).

## Decision

We will use **Supabase Authentication** as the identity provider, with JWT tokens verified on the FastAPI backend using the Supabase JWT secret (RS256).

## Rationale

| Criterion | Supabase Auth | Auth0 | Custom JWT |
|---|---|---|---|
| Integration with Supabase PostgreSQL | Native | Manual | Manual |
| Managed service | Yes | Yes | No |
| Cost (hackathon scale) | Free tier sufficient | Limited free tier | Infrastructure cost |
| Email/password + OAuth | Built-in | Built-in | Build from scratch |
| JWT verification in FastAPI | Standard RS256 | Standard RS256 | Custom |

Supabase Auth provides Row-Level Security integration with the PostgreSQL database, which will be leveraged for tenant isolation in future phases.

## Security Controls

- JWT verified on every protected request using SUPABASE_JWT_SECRET (RS256)
- Service role key never exposed to the frontend
- Only SUPABASE_ANON_KEY (read-safe) exposed to the browser
- Token refresh handled by Supabase JS SDK on the frontend

## Consequences

**Positive:**
- Zero auth server maintenance burden.
- Native Row-Level Security for multi-tenant isolation (Phase 3+).
- Standard JWT format — backend verification is portable.

**Negative:**
- Supabase service dependency — a Supabase outage affects authentication (mitigated by token caching in Redis).
- JWT secret rotation requires coordinated backend config update.

## References
- PRD Section 11: Security Requirements
- PRD Section 8: Tech Stack
