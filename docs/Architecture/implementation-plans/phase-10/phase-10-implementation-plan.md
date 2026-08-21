# phase-10-implementation-plan.md
# Veritas RAG — Phase 10: Grounded Answer Generation (Production Grade)

**Version**: 1.0.0
**Date**: 2026-07-20
**Author**: Principal Software Architect
**Status**: PLANNING — Awaiting Approval
**Depends On**: Phase 5 (Hybrid Retrieval), Phase 6 (Confidence Engine), Phase 7 (Retry Controller)

---

## 1. Executive Summary

Phase 10 delivers the **production-grade Grounded Answer Generation** engine. This is the final stage of the Veritas RAG pipeline, invoked only when the Confidence Engine (Phase 6) and Retry Controller (Phase 7) authorize a `PROCEED` action.

While Phase 3 included a basic generation service, Phase 10 implements strict prompt engineering templates, mandatory inline citations, structured output formatting, hallucination prevention guardrails, and streaming response support via Server-Sent Events (SSE).

---

## 2. Phase Objectives

1. Implement **Prompt Template Engine** — dynamic assembly of the system prompt, retrieved evidence blocks, and user query.
2. Implement **Citation Engine** — enforces strict inline citations (e.g. `[1]`, `[2]`) mapped directly to retrieved evidence chunks.
3. Implement **Hallucination Guardrails** — system prompt directives instructing the LLM to refuse answering if the context is insufficient (last line of defense).
4. Expose **Streaming API** — return generated text incrementally to the client for better perceived latency.
5. Produce **ExecutionResultDTO** — the final payload containing the answer, citations, confidence score, and tracing metadata.

---

## 3. Business Goals

- **Zero Hallucination Tolerance**: The LLM must explicitly state "I don't know" rather than fabricating information not present in the context.
- **Verifiability**: Every claim in the generated answer must cite the specific source document and chunk.
- **Latency**: Use streaming to provide immediate feedback to the user while the full answer generates.

---

## 4. Technical Goals

- Prompt construction uses Jinja2 templates for maintainability.
- LLM interaction is abstracted behind the `BaseLLMProvider` interface (supporting Google Gemini and Cohere).
- Streaming responses use FastAPI's `StreamingResponse`.
- Generated citations are post-processed to ensure they match valid chunk IDs.

---

## 5. Scope

| Component | Included in Phase 10 |
|---|---|
| Prompt Template Engine | ✅ |
| Citation Engine | ✅ |
| Hallucination Guardrails (Prompting) | ✅ |
| Streaming Generation API (SSE) | ✅ |
| ExecutionResultDTO Assembly | ✅ |
| Unit + Integration Tests | ✅ |

---

## 6. Out of Scope

- Answer Validation / Reflection (This was completed in Phase 3 `ReflectionEngine`)
- Frontend UI components

---

## 7. PRD Alignment

| PRD Requirement | Phase 10 Component |
|---|---|
| FR-GN-1: Evidence-grounded generation | Prompt Template Engine |
| FR-GN-2: Inline citations | Citation Engine |
| FR-GN-3: Refusal on lack of context | Hallucination Guardrails |
| NFR-PERF-4: Streaming output | Streaming API |

---

## 8. Architecture Alignment

- Follows ADR-005: all generation logic under `backend/modules/generation/`.
- Integrates into `ExecutionGateway` v2 as the final terminal state.

---

## 9. Dependency Analysis

### Upstream Dependencies
| Phase | Component | Required By Phase 10 |
|---|---|---|
| Phase 7 | `RetryController` | Must yield `PROCEED` |
| Phase 5 | `RetrievalResultDTOv2` | Provides the actual text context |

---

## 10. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│           Phase 10: Grounded Answer Generation               │
├──────────────────────────────────────────────────────────────┤
│                   ExecutionGateway v2                        │
│                           │ (PROCEED)                        │
│  ┌────────────────────────▼───────────────────────────────┐  │
│  │                GenerationOrchestrator                  │  │
│  │                                                        │  │
│  │  ┌────────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │ PromptTemplate │  │ Citation    │  │ LLMProvider │  │  │
│  │  │ Engine         │  │ Engine      │  │ (Streaming) │  │  │
│  │  └────────┬───────┘  └──────┬──────┘  └──────┬──────┘  │  │
│  │           │                 │                │         │  │
│  └───────────┴─────────────────┴────────────────┴─────────┘  │
│                                                              │
│  StreamingResponse (SSE) or ExecutionResultDTO returned      │
└──────────────────────────────────────────────────────────────┘
```

---

## 11. Low-Level Design

### Prompt Template Engine

```
Template variables:
- {query}: The user's query (or rewritten query).
- {evidence_blocks}: Formatted list of evidence.

Evidence Block Format:
[Document {index}]
Source: {document_name}
Content: {content}

System Prompt Instructions:
1. You are a precise corporate AI assistant.
2. Answer the question ONLY using the provided evidence.
3. If the evidence does not contain the answer, say "The provided context does not contain the answer." Do not guess.
4. Cite your sources using the [Document {index}] format inline.
```

### Citation Engine (Post-Processing)

```
1. LLM generates output text with [Document 1] style citations.
2. CitationEngine parses output using Regex `\[Document (\d+)\]`.
3. Validates that the index exists in the provided evidence array.
4. Replaces `[Document {index}]` with structured metadata linking to the actual Chunk ID and Document ID.
5. Builds a `list[CitationDTO]` to append to the final response.
```

---

## 12. Component Design

| File | Type | Purpose |
|---|---|---|
| `backend/modules/generation/services/template_engine.py` | NEW | `PromptTemplateEngine` |
| `backend/modules/generation/services/citation_engine.py` | NEW | `CitationEngine` |
| `backend/modules/generation/services/generation_service.py` | MODIFY | Productionize generation |
| `backend/modules/generation/schemas/generation_dto.py` | MODIFY | Add streaming DTOs, CitationDTO |

---

## 13. API Design

The primary API entry point for the whole system is in the Scoring module (`ExecutionGateway`). Phase 10 modifies the response format of the main execution endpoint.

### POST /api/v1/scoring/execute

**Request**:
```json
{
  "query": "What is the return policy?",
  "stream": true
}
```

**Response (Streaming SSE)**:
```text
data: {"chunk": "The return policy is "}
data: {"chunk": "30 days "}
data: {"chunk": "[Document 1]."}
data: {"citations": [{"doc_id": "...", "chunk_id": "...", "index": 1}], "confidence": 85.0}
```

---

## 14. Testing Strategy

- **Unit Tests**: Template variable replacement; Citation regex parsing and validation; Guardrail trigger (mocking LLM refusal).
- **Integration Tests**: Full ExecutionGateway flow with streaming enabled. Ensure SSE format is correct.
- **Metrics**: `raguard_generation_duration_seconds`, `raguard_generation_tokens_total`, `raguard_generation_refusal_total`.

---

## 15. Completion Criteria

- [ ] All new components created.
- [ ] Streaming API functional and tested.
- [ ] Citation parsing working accurately.
- [ ] All unit and integration tests pass.
- [ ] Git commit: `"Phase 10 Complete: Grounded Answer Generation"`.
- [ ] Progress tracker: 11/23 stages.
