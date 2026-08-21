# phase-8-implementation-plan.md
# Veritas RAG — Phase 8: Query Rewrite Engine (Production Grade)

**Version**: 1.0.0
**Date**: 2026-07-20
**Author**: Principal Software Architect
**Status**: PLANNING — Awaiting Approval
**Depends On**: Phase 5 (Hybrid Retrieval), Phase 6 (Confidence Engine), Phase 7 (Retry Controller)

---

## 1. Executive Summary

Phase 8 delivers the **production-grade Query Rewrite Engine** — the system that, when Phase 7's Retry Controller determines a retry with rewrite is needed, transforms the original query into an improved version before re-invoking the Phase 5 Hybrid Retrieval Engine.

While Phase 3 introduced a baseline `ClarificationEngine.rewrite_query()` stub using basic HyDE, Phase 8 implements a full multi-strategy rewrite pipeline: **HyDE** (Hypothetical Document Embeddings), **Query Expansion** (synonym/term expansion), **Query Decomposition** (complex → sub-queries), and **Missing Entity Recovery** (resolving pronouns and implicit references). Each strategy is independently selectable and composable.

---

## 2. Phase Objectives

1. Implement production **HyDE** — generate a hypothetical answer document to use as a retrieval embedding query.
2. Implement **Query Expansion** — expand query with synonyms, acronym resolution, and domain-specific terminology.
3. Implement **Query Decomposition** — decompose complex multi-part queries into simpler sub-queries for independent retrieval.
4. Implement **Missing Entity Recovery** — resolve pronoun references ("it", "they"), implicit entities, and co-reference chains using query context.
5. Implement **Rewrite Orchestrator** — selects and applies the optimal rewrite strategy based on `RetryDecision` signals and query analysis.
6. Expose **Query Rewrite REST API** — rewrite endpoint, strategy selection, and history.
7. Integrate with Phase 7 `RetryController` as the `RETRY_REWRITE` handler.

---

## 3. Business Goals

- **Improved Recall**: Query rewriting recovers relevant documents that the original query failed to retrieve.
- **Semantic Breadth**: HyDE and expansion increase coverage of semantically related content.
- **Complex Query Handling**: Decomposition enables multi-hop evidence gathering for complex questions.
- **Entity Clarity**: Missing entity recovery prevents retrieval failures caused by ambiguous references.
- **Strategy Transparency**: Every rewrite decision includes a rationale for debugging and user trust.

---

## 4. Technical Goals

- All 4 rewrite strategies are independently unit-testable.
- Rewrite Orchestrator selects strategy based on signals from `ConfidenceResultDTOv2`.
- HyDE uses the LLM provider (Gemini) to generate a hypothetical answer; falls back to template-based synthesis on failure.
- Query Expansion uses a local synonym dictionary + optional LLM expansion.
- Query Decomposition uses LLM for complex queries; heuristic rules for simple queries.
- Missing Entity Recovery uses pronoun/co-reference rules; optional LLM resolution.
- All rewrites are logged with original query, strategy used, rewritten query, and retrieval impact.

---

## 5. Scope

| Component | Included in Phase 8 |
|---|---|
| HyDE Strategy | ✅ |
| Query Expansion Strategy | ✅ |
| Query Decomposition Strategy | ✅ |
| Missing Entity Recovery Strategy | ✅ |
| Rewrite Orchestrator | ✅ |
| Strategy Selector | ✅ |
| Rewrite Audit Log (DB) | ✅ |
| Query Rewrite REST API | ✅ |
| Integration with Phase 7 RetryController | ✅ |
| Unit + Integration Tests | ✅ |

---

## 6. Out of Scope

- Clarification question generation (→ Phase 9)
- LLM answer generation (→ Phase 10)
- Retrieval execution (→ Phase 5, invoked after rewrite)
- Frontend UI components

---

## 7. PRD Alignment

| PRD Requirement | Phase 8 Component |
|---|---|
| FR-QR-1: Hypothetical document embedding | HyDE Strategy |
| FR-QR-2: Term/synonym expansion | Query Expansion Strategy |
| FR-QR-3: Multi-part query decomposition | Query Decomposition Strategy |
| FR-QR-4: Missing entity resolution | Missing Entity Recovery Strategy |
| FR-QR-5: Strategy selection based on confidence signals | Rewrite Orchestrator |
| NFR-PERF-3: Rewrite < 200ms | Strategy timeout guards + LLM caching |

---

## 8. Architecture Alignment

- Follows ADR-005: all rewrite logic under `backend/modules/query_rewrite/`.
- Follows ADR-006: LLM and synonym providers behind abstract interfaces.
- Phase 8 extends the existing `ClarificationEngine` baseline — it does NOT replace it.
- Phase 8 output feeds back into Phase 5 `RetrievalOrchestrator`.

---

## 9. Dependency Analysis

### Upstream Dependencies
| Phase | Component | Required By Phase 8 |
|---|---|---|
| Phase 5 | `RetrievalOrchestrator` | Re-invoked post-rewrite |
| Phase 6 | `ConfidenceResultDTOv2` | Strategy selection signals |
| Phase 7 | `RetryDecision` | Trigger + strategy hint |
| Phase 3 | `ClarificationEngine` (baseline stub) | Extension target |

### Downstream Consumers
| Phase | Component | Consumes from Phase 8 |
|---|---|---|
| Phase 5 | `RetrievalOrchestrator` | `RewriteResultDTO.rewritten_query` |
| Phase 7 | `RetryController` | Receives rewritten query for re-retrieval |
| Phase 9 | `ClarificationEngine` | May receive decomposed sub-queries |

---

## 10. Existing Codebase Review

### What Already Exists (Baseline)

| Component | Location | Status |
|---|---|---|
| `ClarificationEngine.rewrite_query()` | `backend/modules/query_rewrite/services/clarification_engine.py` | Phase 8 extends |
| `RewriteRequestDTO` | `backend/modules/query_rewrite/schemas/rewrite_dto.py` | Extend with strategy selection |
| `HyDEStrategy` (stub) | `backend/modules/query_rewrite/strategies/hyde.py` | Phase 8 productionizes |
| Query Rewrite strategies dir | `backend/modules/query_rewrite/strategies/` | Phase 8 adds 3 new strategies |

---

## 11. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│            Phase 8: Query Rewrite Engine                     │
├─────────────────────────┬────────────────────────────────────┤
│  /api/v1/query-rewrite/ │  FastAPI Router                    │
│    rewrite              │                                    │
│    strategies           │                                    │
│    history              │                                    │
├─────────────────────────┴────────────────────────────────────┤
│                  RewriteOrchestrator                         │
│                                                              │
│  ┌──────────────────┐                                        │
│  │ StrategySelector │ ← ConfidenceResultDTOv2 signals        │
│  │ (signal-based)   │                                        │
│  └────────┬─────────┘                                        │
│           │ selects                                          │
│  ┌────────▼───────────────────────────────────────────────┐  │
│  │ Strategy Registry                                      │  │
│  │  ┌──────────┐  ┌────────────┐  ┌──────────────────┐   │  │
│  │  │  HyDE    │  │  Expansion │  │  Decomposition   │   │  │
│  │  │ Strategy │  │  Strategy  │  │  Strategy        │   │  │
│  │  └──────────┘  └────────────┘  └──────────────────┘   │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │  MissingEntityRecovery Strategy                  │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
│           │                                                  │
│  RewriteResultDTO → Phase 7 RetryController → Phase 5        │
└──────────────────────────────────────────────────────────────┘
```

---

## 12. Low-Level Design

### HyDE Strategy (Production)

```
Input: original_query: str, evidence_context: list[str] | None

Algorithm:
  1. Build HyDE prompt:
     "Generate a short factual document that would answer: '{query}'.
      Use formal, factual language. 1-3 sentences maximum."

  2. Call LLMProvider.generate(prompt, max_tokens=150)
     Timeout: 2000ms
     On timeout/failure: use template synthesis:
       hypothetical_doc = f"This document discusses {query} in the context of {domain}."

  3. Embed hypothetical_doc using EmbeddingProvider.embed_query()

  4. Return HyDEResultDTO:
     original_query: str
     hypothetical_document: str
     embedding_query: str (the hypothetical doc, used as embedding input)
     strategy: "hyde"
     confidence_improvement_estimate: float (heuristic)
```

### Query Expansion Strategy

```
Input: original_query: str, domain: str | None

Algorithm:
  1. Tokenize query → terms
  2. For each term:
     a. Local synonym lookup (SynonymDictionary): term → list[str] synonyms
     b. Acronym expansion (AcronymRegistry): e.g. "ML" → "Machine Learning"
     c. Domain-specific expansion: if domain provided, use domain glossary
  3. Construct expanded_query:
     original_terms + top-2 synonyms per term (weighted)
     f"({original_term} OR {synonym_1} OR {synonym_2})"
  4. Optional LLM expansion (if enabled):
     "List 3 alternative phrasings of: '{query}'"
     Merge with synonym-expanded query.

  Return QueryExpansionResultDTO:
    original_query: str
    expanded_query: str
    expanded_terms: list[str]
    strategy: "expansion"
```

### Query Decomposition Strategy

```
Input: original_query: str

Algorithm:
  1. Complexity Detection:
     Heuristic rules:
       - Contains "and" + "?" → likely compound
       - Contains comparison words ("compare", "difference between") → decompose
       - Word count > 20 → likely complex
       - Contains multiple question marks → multi-part

     If not complex → return original_query unchanged

  2. Decomposition (LLM-based):
     Prompt: "Decompose this question into 2-3 independent simpler questions.
              Return ONLY a JSON array of strings: ['q1', 'q2', 'q3']
              Question: '{original_query}'"
     Parse response → list[str] sub_queries
     On LLM failure: split on " and " / "?" heuristically

  3. Return QueryDecompositionResultDTO:
     original_query: str
     sub_queries: list[str]
     is_decomposed: bool
     strategy: "decomposition"
     # Note: Phase 5 retrieval is invoked per sub-query; results merged by FusionEngine
```

### Missing Entity Recovery Strategy

```
Input: original_query: str, conversation_context: ConversationContext | None

Algorithm:
  1. Pronoun Detection:
     Patterns: ["it", "they", "them", "this", "that", "these", "those", "he", "she"]
     Check if query contains pronouns without clear antecedents

  2. Implicit Reference Detection:
     Patterns: ["the policy", "the contract", "the document", "the above"]
     → references that require context to resolve

  3. Resolution:
     If conversation_context provided:
       - Extract most recent noun phrase from context
       - Substitute pronoun with resolved entity
     If no context:
       - LLM prompt: "What specific entity does '{query}' refer to?"
       - On failure: mark as UNRESOLVED; proceed with original query

  4. Return MissingEntityResultDTO:
     original_query: str
     resolved_query: str
     resolved_entities: list[EntityResolutionDTO]
     is_resolved: bool
     strategy: "entity_recovery"
```

### Strategy Selector

```
Signal → Strategy Mapping:

ConfidenceResultDTOv2 signals:
  low coverage (coverage_score < 0.5) → HyDE (semantic breadth)
  uncovered_clauses > 0 → Expansion (term coverage)
  complex_query_detected → Decomposition
  pronoun_detected → MissingEntityRecovery
  generic low confidence → HyDE (default)

RetryDecision.strategy_hint (from Phase 7):
  "hyde" → HyDE
  "expansion" → Expansion
  "decomposition" → Decomposition
  "entity_recovery" → MissingEntityRecovery
  "auto" → StrategySelector uses signal-based routing

Priority: RetryDecision.strategy_hint > signal-based routing > HyDE default
```

---

## 13. Component Design

### 13.1 HyDEStrategy
```
class HyDEStrategy(BaseRewriteStrategy):
  - rewrite(request: RewriteRequestDTO) → HyDEResultDTO
  - _generate_hypothetical_doc(query, llm, timeout_ms) → str
  - _template_synthesis_fallback(query) → str
  - _embed_hypothetical_doc(doc, embedding_provider) → str
```

### 13.2 QueryExpansionStrategy
```
class QueryExpansionStrategy(BaseRewriteStrategy):
  - rewrite(request: RewriteRequestDTO) → QueryExpansionResultDTO
  - _tokenize(query) → list[str]
  - _synonym_lookup(term) → list[str]
  - _acronym_expand(term) → str | None
  - _domain_expand(term, domain) → list[str]
  - _construct_expanded_query(original, expansions) → str
```

### 13.3 QueryDecompositionStrategy
```
class QueryDecompositionStrategy(BaseRewriteStrategy):
  - rewrite(request: RewriteRequestDTO) → QueryDecompositionResultDTO
  - _detect_complexity(query) → bool
  - _llm_decompose(query, llm, timeout_ms) → list[str]
  - _heuristic_decompose(query) → list[str]
```

### 13.4 MissingEntityRecoveryStrategy
```
class MissingEntityRecoveryStrategy(BaseRewriteStrategy):
  - rewrite(request: RewriteRequestDTO) → MissingEntityResultDTO
  - _detect_pronouns(query) → list[str]
  - _detect_implicit_references(query) → list[str]
  - _resolve_from_context(pronoun, context) → str | None
  - _llm_resolve(query, llm, timeout_ms) → str | None
```

### 13.5 RewriteOrchestrator
```
class RewriteOrchestrator:
  - rewrite(request: RewriteRequestDTOv2) → RewriteResultDTO
  - _select_strategy(confidence_result, retry_decision) → BaseRewriteStrategy
  - _execute_strategy(strategy, request) → RewriteResultDTO
  - _log_rewrite(result) → None (async)
```

### 13.6 BaseRewriteStrategy (abstract)
```
class BaseRewriteStrategy(ABC):
  @abstractmethod
  def rewrite(self, request: RewriteRequestDTO) → RewriteResultDTO
  def get_strategy_name(self) → str
```

---

## 14. Module Responsibilities

| Component | Responsibility |
|---|---|
| `HyDEStrategy` | Generate hypothetical doc → use as embedding query |
| `QueryExpansionStrategy` | Expand terms with synonyms/acronyms/domain terms |
| `QueryDecompositionStrategy` | Break complex queries into independent sub-queries |
| `MissingEntityRecoveryStrategy` | Resolve pronouns and implicit entity references |
| `StrategySelector` | Route to correct strategy based on signals |
| `RewriteOrchestrator` | Coordinate strategy selection + execution + logging |
| `SynonymDictionary` | Local synonym lookup (domain-agnostic) |
| `AcronymRegistry` | Acronym expansion lookup |
| `RewriteRepository` | Persist rewrite audit logs |

---

## 15. Data Flow

```
Phase 7 RetryDecision (trigger_rewrite=True, strategy_hint="auto")
              │
              ▼
    RewriteOrchestrator.rewrite(request)
              │
    ┌─────────▼──────────┐
    │  StrategySelector   │ ← ConfidenceResultDTOv2 signals
    │  (signal routing)   │ ← RetryDecision.strategy_hint
    └─────────┬──────────┘
              │ selects strategy
    ┌─────────▼──────────────────────────────────┐
    │  Strategy Execution                        │
    │  HyDE | Expansion | Decomposition | Entity │
    └─────────┬──────────────────────────────────┘
              │
    RewriteResultDTO
    {original_query, rewritten_query, strategy, rationale}
              │
              ▼
    Phase 5 RetrievalOrchestrator (re-invoked with rewritten_query)
```

---

## 16. Sequence Flow

```
1. Phase 7 RetryController → RewriteOrchestrator.rewrite(request)
2. StrategySelector.select(confidence_result, retry_decision) → BaseRewriteStrategy
3. Strategy.rewrite(original_query, options) → RewriteResultDTO
   - HyDE: LLM.generate(prompt) → hypothetical_doc → embed
   - Expansion: SynonymDict + AcronymRegistry + optional LLM
   - Decomposition: complexity check → LLM decompose → sub_queries list
   - Entity: pronoun detect → context resolve → LLM fallback
4. RewriteOrchestrator constructs RewriteResultDTO
5. asyncio.create_task(RewriteRepository.log_rewrite(result))
6. Return RewriteResultDTO to RetryController
7. RetryController re-invokes Phase 5 with rewritten_query
   (For Decomposition: Phase 5 invoked per sub-query; results merged via FusionEngine)
```

---

## 17. Folder Structure Changes

```
backend/modules/query_rewrite/
├── api/                               [NEW]
│   ├── __init__.py                    [NEW]
│   ├── routes.py                      [NEW] rewrite, strategies, history
│   └── dependencies.py                [NEW]
├── schemas/
│   ├── __init__.py
│   ├── rewrite_dto.py                 [MODIFY] add v2 DTOs
│   └── errors.py                      [MODIFY or NEW]
├── services/
│   ├── clarification_engine.py        [MODIFY] extend; keep backward compat
│   ├── rewrite_orchestrator.py        [NEW] RewriteOrchestrator
│   └── strategy_selector.py           [NEW] StrategySelector
├── strategies/
│   ├── __init__.py                    [NEW]
│   ├── base.py                        [NEW] BaseRewriteStrategy
│   ├── hyde.py                        [MODIFY] productionize HyDE
│   ├── expansion.py                   [NEW] QueryExpansionStrategy
│   ├── decomposition.py               [NEW] QueryDecompositionStrategy
│   └── entity_recovery.py             [NEW] MissingEntityRecoveryStrategy
├── resources/                         [NEW]
│   ├── synonym_dictionary.json        [NEW] domain-agnostic synonyms
│   └── acronym_registry.json          [NEW] common acronym expansions
├── models/
│   ├── __init__.py                    [NEW]
│   └── rewrite_log.py                 [NEW] RewriteAuditLog ORM
├── repositories/
│   ├── __init__.py                    [NEW]
│   └── rewrite_repository.py          [NEW]
└── events/
    ├── __init__.py                    [NEW]
    └── payloads.py                    [NEW] QueryRewrittenPayload
```

---

## 18. File Creation Plan

| File | Type | Purpose |
|---|---|---|
| `strategies/base.py` | NEW | `BaseRewriteStrategy` abstract class |
| `strategies/expansion.py` | NEW | `QueryExpansionStrategy` |
| `strategies/decomposition.py` | NEW | `QueryDecompositionStrategy` |
| `strategies/entity_recovery.py` | NEW | `MissingEntityRecoveryStrategy` |
| `services/rewrite_orchestrator.py` | NEW | `RewriteOrchestrator` |
| `services/strategy_selector.py` | NEW | `StrategySelector` |
| `resources/synonym_dictionary.json` | NEW | ~500 common synonym pairs |
| `resources/acronym_registry.json` | NEW | ~200 common acronyms |
| `models/rewrite_log.py` | NEW | `RewriteAuditLog` ORM |
| `repositories/rewrite_repository.py` | NEW | `RewriteRepository` |
| `events/payloads.py` | NEW | Domain events |
| `api/routes.py` | NEW | REST endpoints |
| `api/dependencies.py` | NEW | FastAPI dependencies |
| `tests/unit/backend/modules/query_rewrite/test_rewrite_v2.py` | NEW | Phase 8 unit tests |

---

## 19. Database Changes

### Alembic Migration: `0012_query_rewrite_schema.py`

```sql
CREATE TABLE query_rewrite_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           VARCHAR(255) NOT NULL,
    correlation_id      VARCHAR(255) NOT NULL,
    original_query      TEXT NOT NULL,
    rewritten_query     TEXT NOT NULL,
    strategy_used       VARCHAR(50) NOT NULL,
    sub_queries         JSONB,
    resolved_entities   JSONB,
    expansion_terms     JSONB,
    confidence_before   FLOAT,
    confidence_after    FLOAT,
    duration_ms         FLOAT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_query_rewrite_logs_tenant
    ON query_rewrite_logs(tenant_id, created_at DESC);
```

---

## 20. API Design

### 20.1 POST /api/v1/query-rewrite/rewrite

**Request** (`RewriteRequestDTOv2`):
```json
{
  "query": "What was the impact on our Q3 revenue?",
  "strategy": "auto",
  "confidence_result": { "...ConfidenceResultDTOv2..." },
  "conversation_context": { "last_entity": "Enterprise License Agreement" },
  "options": {
    "hyde_max_tokens": 150,
    "expansion_max_synonyms": 2,
    "decomposition_max_sub_queries": 3,
    "timeout_ms": 2000
  }
}
```

**Response** (`RewriteResultDTO`):
```json
{
  "original_query": "What was the impact on our Q3 revenue?",
  "rewritten_query": "What was the financial impact on Q3 2025 revenue from the Enterprise License Agreement?",
  "strategy_used": "entity_recovery",
  "rationale": "Resolved pronoun 'our' to 'Enterprise License Agreement' from conversation context",
  "sub_queries": null,
  "expansion_terms": null,
  "hyde_hypothetical_doc": null,
  "confidence_improvement_estimate": 0.15,
  "duration_ms": 34.2
}
```

### 20.2 GET /api/v1/query-rewrite/strategies

Returns list of available rewrite strategies with descriptions.

### 20.3 GET /api/v1/query-rewrite/history

Paginated `RewriteAuditLog` for authenticated tenant.

---

## 21. Configuration Changes

```python
class QueryRewriteSettings(BaseModel):
    hyde_enabled: bool = True
    hyde_max_tokens: int = 150
    hyde_timeout_ms: int = 2000
    expansion_enabled: bool = True
    expansion_max_synonyms_per_term: int = 2
    decomposition_enabled: bool = True
    decomposition_max_sub_queries: int = 3
    decomposition_timeout_ms: int = 3000
    entity_recovery_enabled: bool = True
    entity_recovery_timeout_ms: int = 1000
    default_strategy: str = "hyde"
```

---

## 22. Environment Variables

```bash
# Phase 8 Query Rewrite Configuration
QUERY_REWRITE_HYDE_ENABLED=true
QUERY_REWRITE_HYDE_MAX_TOKENS=150
QUERY_REWRITE_HYDE_TIMEOUT_MS=2000
QUERY_REWRITE_EXPANSION_ENABLED=true
QUERY_REWRITE_EXPANSION_MAX_SYNONYMS=2
QUERY_REWRITE_DECOMPOSITION_ENABLED=true
QUERY_REWRITE_DECOMPOSITION_MAX_SUB_QUERIES=3
QUERY_REWRITE_ENTITY_RECOVERY_ENABLED=true
QUERY_REWRITE_DEFAULT_STRATEGY=hyde
```

---

## 23. Security Considerations

1. LLM-generated rewritten queries are sanitized before re-use in retrieval to prevent prompt injection propagation.
2. `conversation_context` is strictly scoped per `tenant_id` — no cross-tenant context bleed.
3. HyDE hypothetical documents are ephemeral — not stored in retrieval indexes.
4. `synonym_dictionary.json` and `acronym_registry.json` are static, version-controlled files — no dynamic injection.
5. Sub-queries from decomposition are individually validated before Phase 5 invocation.

---

## 24. Performance Considerations

1. HyDE LLM call: 2000ms timeout with template fallback.
2. Query Expansion: in-memory dictionary lookup — O(n) where n = token count. < 5ms.
3. Query Decomposition: complexity detection heuristic first (< 1ms); LLM only for complex queries.
4. Missing Entity Recovery: pronoun pattern matching first (< 1ms); LLM only for unresolved.
5. Total rewrite target: < 200ms (including LLM call when needed).
6. Rewrite audit log write: fire-and-forget async task.

---

## 25. Monitoring Strategy

### New Prometheus Metrics (Phase 8)

```
raguard_query_rewrite_total (counter, labels: strategy, outcome)
raguard_query_rewrite_duration_seconds (histogram, labels: strategy)
raguard_query_rewrite_hyde_fallback_total (counter)
raguard_query_rewrite_decomposition_sub_queries (histogram)
raguard_query_rewrite_entity_resolution_total (counter, labels: resolved)
```

---

## 26. Error Handling Strategy

| Error Code | Exception | HTTP Status | Description |
|---|---|---|---|
| QR_001 | `InvalidQueryRewriteRequest` | 400 | Empty query or invalid strategy |
| QR_002 | `HyDEGenerationError` | 200* | LLM failed; template fallback used |
| QR_003 | `DecompositionParseError` | 200* | LLM decomposition parse failed; heuristic fallback |
| QR_004 | `EntityResolutionFailed` | 200* | Entity unresolved; original query used |
| QR_005 | `StrategyNotEnabled` | 400 | Requested strategy disabled in config |

*Soft failures — degraded response, not error HTTP status.

---

## 27. Testing Strategy

### Unit Tests
- `HyDEStrategy`: successful LLM call, LLM timeout → template fallback, empty query.
- `QueryExpansionStrategy`: single-term expansion, multi-term, acronym resolution, domain expansion.
- `QueryDecompositionStrategy`: simple query → no decomposition, complex → decomposed, LLM failure → heuristic.
- `MissingEntityRecoveryStrategy`: pronoun detected + context resolved, pronoun + no context → LLM, no pronoun → no change.
- `StrategySelector`: signal routing for all 4 strategies, strategy_hint override.
- `RewriteOrchestrator`: end-to-end with mock strategy.

### Integration Tests
- POST /query-rewrite/rewrite with HyDE strategy.
- Retry loop → rewrite → re-retrieval → improved confidence.
- Decomposition produces 3 sub-queries; all sent to retrieval; results merged.

---

## 28. Unit Testing Plan

| Test Class | Tests |
|---|---|
| `TestHyDEStrategy` | `test_llm_success`, `test_llm_timeout_fallback`, `test_empty_query_rejected`, `test_hypothetical_doc_embedded`, `test_long_query_truncated` |
| `TestQueryExpansionStrategy` | `test_synonym_expansion`, `test_acronym_resolution`, `test_domain_expansion`, `test_no_synonyms_unchanged`, `test_max_synonyms_bounded` |
| `TestQueryDecompositionStrategy` | `test_simple_query_not_decomposed`, `test_compound_query_decomposed`, `test_llm_failure_heuristic_fallback`, `test_max_sub_queries_bounded`, `test_json_parse_error_recovery` |
| `TestMissingEntityRecovery` | `test_pronoun_it_resolved_from_context`, `test_pronoun_no_context_llm_fallback`, `test_no_pronoun_unchanged`, `test_implicit_reference_detected`, `test_llm_resolution_failure_original` |
| `TestStrategySelector` | `test_low_coverage_selects_hyde`, `test_uncovered_clauses_selects_expansion`, `test_complex_query_selects_decomposition`, `test_pronoun_selects_entity_recovery`, `test_strategy_hint_overrides_signal` |
| `TestRewriteOrchestrator` | `test_successful_rewrite`, `test_strategy_selection_delegation`, `test_audit_log_created`, `test_timeout_handled` |

---

## 29. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| HyDE hypothetical doc misleads retrieval | Medium | Medium | Confidence comparison before/after; rollback if worse |
| Decomposition creates too many sub-queries | Low | Medium | Hard cap at 3; merge via FusionEngine |
| Entity recovery resolves to wrong entity | Medium | High | Confidence comparison; original used if worse |
| LLM quota exceeded during heavy retry | Medium | High | LLM call budget tracking per request |
| Expanded query too long for embedding | Low | Low | Token budget cap on expanded query |

---

## 30. Acceptance Criteria

- [ ] All 4 rewrite strategies produce valid `RewriteResultDTO` for standard inputs.
- [ ] HyDE fallback triggers on LLM timeout and returns template-based rewrite.
- [ ] Decomposition correctly identifies complex queries (word count > 20, "and ... ?").
- [ ] Missing Entity Recovery resolves "it" from conversation context when provided.
- [ ] `StrategySelector` routes correctly for all 4 signal conditions.
- [ ] All rewrites logged in `query_rewrite_logs` table.
- [ ] Phase 7 → Phase 8 → Phase 5 retry loop works end-to-end.

---

## 31. Completion Criteria

- [ ] All new files created per §17.
- [ ] Alembic migration `0012` generated and tested.
- [ ] All unit tests pass (no regressions).
- [ ] Integration tests pass.
- [ ] Git commit: `"Phase 8 Complete: Query Rewrite Engine"`.
- [ ] Progress tracker: 9/23 stages (39.1%).

---

## 32. Milestone Breakdown

### Milestone 8.1 — Base Strategy Interface & Schema
**Components**: `strategies/base.py`, `rewrite_dto.py` (v2 extensions).

### Milestone 8.2 — HyDE Strategy (Production)
**Components**: `strategies/hyde.py` (v2), LLM provider integration.

### Milestone 8.3 — Query Expansion Strategy
**Components**: `strategies/expansion.py`, `synonym_dictionary.json`, `acronym_registry.json`.

### Milestone 8.4 — Query Decomposition Strategy
**Components**: `strategies/decomposition.py`.

### Milestone 8.5 — Missing Entity Recovery Strategy
**Components**: `strategies/entity_recovery.py`.

### Milestone 8.6 — Orchestrator, API, Audit, & Integration
**Components**: `rewrite_orchestrator.py`, `strategy_selector.py`, `api/routes.py`, `models/rewrite_log.py`, migration 0012.

### Milestone 8.7 — Final Verification
**Testing**: All unit + integration tests, regression suite, frontend build.

---

## 33. Implementation Checklist

- [ ] Create `backend/modules/query_rewrite/strategies/__init__.py`
- [ ] Create `backend/modules/query_rewrite/strategies/base.py`
- [ ] Modify `backend/modules/query_rewrite/strategies/hyde.py` (v2)
- [ ] Create `backend/modules/query_rewrite/strategies/expansion.py`
- [ ] Create `backend/modules/query_rewrite/strategies/decomposition.py`
- [ ] Create `backend/modules/query_rewrite/strategies/entity_recovery.py`
- [ ] Create `backend/modules/query_rewrite/services/rewrite_orchestrator.py`
- [ ] Create `backend/modules/query_rewrite/services/strategy_selector.py`
- [ ] Create `backend/modules/query_rewrite/resources/synonym_dictionary.json`
- [ ] Create `backend/modules/query_rewrite/resources/acronym_registry.json`
- [ ] Create `backend/modules/query_rewrite/models/rewrite_log.py`
- [ ] Create `backend/modules/query_rewrite/repositories/rewrite_repository.py`
- [ ] Create `backend/modules/query_rewrite/events/payloads.py`
- [ ] Create `backend/modules/query_rewrite/api/routes.py`
- [ ] Create `backend/modules/query_rewrite/api/dependencies.py`
- [ ] Modify `backend/modules/query_rewrite/schemas/rewrite_dto.py` (v2)
- [ ] Register `/api/v1/query-rewrite` router in `backend/api/v1/router.py`
- [ ] Generate Alembic migration `0012_query_rewrite_schema.py`
- [ ] Write unit tests (~30 tests across 6 classes)
- [ ] Write integration tests (~3 tests)
- [ ] Run full regression suite + frontend build
- [ ] Update `task.md` and `walkthrough.md`

---

## 34. Phase Completion Checklist

- [ ] All milestones 8.1–8.7 completed and verified.
- [ ] Full backend test suite passes.
- [ ] Frontend production build passes.
- [ ] Alembic migration 0012 applied.
- [ ] Git commit: `"Phase 8 Complete: Query Rewrite Engine"`.
- [ ] GitHub push to `main`.
- [ ] Progress tracker: 9/23 stages (39.1%).
