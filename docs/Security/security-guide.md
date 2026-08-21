# Security Guide

## Authentication & Authorization

- JWT Bearer tokens validated on every request.
- Tokens must contain `tenant_id` and `role` claims.
- Roles: `admin`, `operator`, `viewer`.
- RBAC enforced at the endpoint level via `Depends()` decorators.

## Data Loss Prevention (DLP)

Veritas RAG intercepts all user prompts before they reach LLM providers.
The `DLPEngine` redacts:
- Email addresses
- Social Security Numbers (SSN)
- Credit card patterns (configurable)
- Custom regex patterns (extensible)

Enable via `.env`:
```
DLP_ENABLED=true
```

## Prompt Injection Protection

- System instructions are always separated from user context.
- NLI-based validation detects semantic drift from the expected answer space.

## Compliance Audit Logging

All security-sensitive operations emit structured audit events:
```json
{
  "tenant_id": "acme",
  "actor_id": "user-123",
  "action": "PII_REDACTED",
  "resource": "prompt",
  "status": "SUCCESS",
  "timestamp": "2026-07-21T00:00:00Z"
}
```

## Encryption

- API keys are stored as environment variables, never in the database.
- `KeyManager` provides zero-downtime key rotation.
- TLS enforced in production via `SecurityHeadersMiddleware` (HSTS header).

## Tenant Isolation

Every database query and API endpoint requires `tenant_id` validation.
Qdrant collections are namespaced per tenant.
