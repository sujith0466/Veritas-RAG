# RAGuard AI — Low-Level Architecture

## Service Layer Pattern

Every module follows a strict three-layer pattern:

```
Router (FastAPI) -> Service (Business Logic) -> Repository (Data Access)
```

## Key Design Patterns

### Repository Pattern
- `BaseRepository` in `backend/repositories/base.py` provides generic CRUD.
- Concrete repositories extend it and inject `AsyncSession` via FastAPI `Depends()`.

### Provider Abstraction
- LLM providers implement `BaseLLMProvider` interface.
- Vector DB providers implement `BaseDenseProvider` interface.
- Swapping providers requires zero business logic changes.

### Exception Hierarchy
- `RAGuardException` is the base.
- All exceptions carry `error_code` (e.g. `AUTH_001`), `http_status`, and `message`.
- Global handlers in `backend/core/exceptions.py` convert exceptions to JSON.

### Event System
- `EventDispatcher` singleton in `backend/core/events.py`.
- Modules publish domain events without direct coupling to subscribers.

## Database Schema Overview

| Table | Module | Purpose |
|-------|--------|---------|
| `users` | auth | User accounts |
| `audit_logs` | core | Immutable audit trail |
| `retrieval_query_logs` | retrieval | Query performance tracking |
| `confidence_scores` | confidence | Per-query confidence history |
| `retry_log` | retry | Retry budget tracking |
| `alert_rules` | alerts | Rule engine configuration |
| `alert_history` | alerts | Fired alert log |
| `self_healing_policies` | reliability | Auto-recovery policies |
| `healing_action_log` | reliability | Recovery action history |
| `tenant_quotas` | analytics | Usage limits per tenant |
| `token_usage` | analytics | Token burn tracking |
| `fault_policies` | chaos | Chaos injection policies |
