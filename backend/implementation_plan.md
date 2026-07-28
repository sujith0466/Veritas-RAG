# Phase C & D Implementation Plan

## Phase C (Reliability Scoring) Architectural Review

The reliability scoring system currently utilized by the production chat API (`backend/modules/chat/services/chat_orchestrator.py`) computes a final score on a 0.0 to 1.0 scale. 

**Exact Scoring Formula & Weights:**
```python
score = (
    retrieval_quality * 0.20 + 
    citation_validity * 0.25 + 
    grounding_confidence * 0.25 + 
    evidence_completeness * 0.15 + 
    context_coverage * 0.15
)
```
**Score Normalization & Min/Max:**
- Minimum Score: `0.0`
- Maximum Score: `1.0`
- Normalization: The raw additive score is bounded between 0.0 and 1.0. Before returning, the system enforces a strict `all_checks_passed` gate. If any check fails, the score is capped at `0.99` (`score = min(score, 0.99)`). 

**Perfect Score (1.0) Conditions:**
All of the following must be true:
1. `is_grounded` is `True` (all claims supported by citations mapping to non-empty chunks).
2. `retrieval_quality >= 1.0` (all requested top_k chunks retrieved successfully).
3. `citation_validity >= 1.0` (all inline markers map to valid provided evidence).
4. `evidence_completeness >= 1.0` (no empty documents retrieved).
5. `context_coverage >= 1.0` (every meaningful statement in the output has a citation).

**Verification of Business Rules:**
- **Unsupported claims cannot receive 1.0**: Verified. Missing citations cause `context_coverage < 1.0`, capping the score at 0.99.
- **Empty evidence cannot receive 1.0**: Verified. `evidence_completeness` drops, capping the score at 0.99.
- **Invalid citations cannot receive 1.0**: Verified. `citation_validity` drops, capping the score at 0.99.
- **Missing citations cannot receive 1.0**: Verified. `context_coverage` drops, capping the score at 0.99.
- **Partial grounding produces proportional scores**: Verified. Since weights are additive (e.g. 0.6 context coverage contributes `0.15 * 0.6`), partial grounding gracefully degrades the score rather than returning 0.

*Phase C Verdict*: **Phase C is Approved.** No code changes are required as it meets all strict business rules. (Note: The unused `ExecutionGateway` and `ReliabilityScorer` returning a 0-100 scale represent future or deprecated V2 components that do not affect current API endpoints).

## Phase D (LLM Audit Telemetry) Completion Plan

Currently, the `LLMAuditRecord` ORM model and the Alembic migration (0022) exist, but the telemetry capturing logic is not implemented.

**Implementation Steps:**
1. **Repository**: Create `backend/modules/generation/repositories/llm_audit_repository.py` to persist `LLMAuditRecord` into PostgreSQL.
2. **Service**: Create `backend/modules/generation/services/llm_audit_service.py` to wrap the repository and securely hash the prompt text (SHA256) and filter raw payload logging based on the `LLM_AUDIT_MODE` configuration (`hash_only` vs `full`).
3. **Integration**: Update `backend/ai/manager.py` (or the respective generation service) to asynchronously emit the audit record upon completion of an LLM call. This will ensure *zero latency impact* on the critical path of the streaming generation.
4. **Token Usage**: Ensure that the OpenRouter token usage payload is extracted from the SSE stream and populated into the database.
5. **Testing**: Run all regression tests after hooking up the telemetry to ensure chat routes are uninterrupted.

## User Feedback Required
Please review the Phase D completion plan. If approved, I will implement the missing repository/service, hook it asynchronously into the LLM manager, run the regression tests, and output the final detailed report as requested.
