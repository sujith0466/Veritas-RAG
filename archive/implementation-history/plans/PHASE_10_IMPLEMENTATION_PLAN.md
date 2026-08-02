# phase-10-implementation-plan.md
# RAGuard AI — Phase 10: Grounded Answer Generation (Production Grade)

**Version**: 1.0.0
**Date**: 2026-07-20
**Author**: Principal Software Architect
**Status**: PLANNING — Awaiting Approval
**Depends On**: Phase 5 (Hybrid Retrieval), Phase 6 (Confidence Engine), Phase 7 (Retry Controller)

---

## 1. Executive Summary

Phase 10 delivers the **production-grade Grounded Answer Generation** engine. This is the final stage of the RAGuard AI pipeline, invoked only when the Confidence Engine (Phase 6) and Retry Controller (Phase 7) authorize a PROCEED action.

While Phase 3 included a basic generation service, Phase 10 implements strict prompt engineering templates, mandatory inline citations, structured output formatting, hallucination prevention guardrails, and streaming response support via Server-Sent Events (SSE).

---

## 2. Phase Objectives

1. Implement **Prompt Template Engine** — dynamic assembly of the system prompt, retrieved evidence blocks, and user query.
2. Implement **Citation Engine** — enforces strict inline citations (e.g. [1], [2]) mapped directly to retrieved evidence chunks.
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
- LLM interaction is abstracted behind the BaseLLMProvider interface (supporting Google LLMProvider (Gemini Implementation) and RerankerProvider (Cohere Implementation)).
- Streaming responses use FastAPI's StreamingResponse.
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

- Answer Validation / Reflection (This was completed in Phase 3 ReflectionEngine)
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

- Follows ADR-005: all generation logic under ackend/modules/generation/.
- Integrates into ExecutionGateway v2 as the final terminal state.

---

## 9. Dependency Analysis

### Upstream Dependencies
| Phase | Component | Required By Phase 10 |
|---|---|---|
| Phase 7 | RetryController | Must yield PROCEED |
| Phase 5 | RetrievalResultDTOv2 | Provides the actual text context |

---

## 10. High-Level Architecture

``
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
``

---

## 11. Low-Level Design

### Prompt Template Engine

``
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
``

### Citation Engine (Post-Processing)

``
1. LLM generates output text with [Document 1] style citations.
2. CitationEngine parses output using Regex \[Document (\d+)\].
3. Validates that the index exists in the provided evidence array.
4. Replaces [Document {index}] with structured metadata linking to the actual Chunk ID and Document ID.
5. Builds a list[CitationDTO] to append to the final response.
``

---

## 12. Component Design

| File | Type | Purpose |
|---|---|---|
| ackend/modules/generation/services/template_engine.py | NEW | PromptTemplateEngine |
| ackend/modules/generation/services/citation_engine.py | NEW | CitationEngine |
| ackend/modules/generation/services/generation_service.py | MODIFY | Productionize generation |
| ackend/modules/generation/schemas/generation_dto.py | MODIFY | Add streaming DTOs, CitationDTO |

---

## 13. API Design

The primary API entry point for the whole system is in the Scoring module (ExecutionGateway). Phase 10 modifies the response format of the main execution endpoint.

### POST /api/v1/scoring/execute

**Request**:
`json
{
  "query": "What is the return policy?",
  "stream": true
}
`

**Response (Streaming SSE)**:
`	ext
data: {"chunk": "The return policy is "}
data: {"chunk": "30 days "}
data: {"chunk": "[Document 1]."}
data: {"citations": [{"doc_id": "...", "chunk_id": "...", "index": 1}], "confidence": 85.0}
`

---

## 14. Testing Strategy

- **Unit Tests**: Template variable replacement; Citation regex parsing and validation; Guardrail trigger (mocking LLM refusal).
- **Integration Tests**: Full ExecutionGateway flow with streaming enabled. Ensure SSE format is correct.
- **Metrics**:
aguard_generation_duration_seconds,
aguard_generation_tokens_total,
aguard_generation_refusal_total.

---

## Provider Abstraction

The LLM logic uses a provider abstraction strategy, insulating the generation pipeline from vendor lock-in. A BaseLLMProvider interface handles both standard generation and streaming generation. Implementations are registered dynamically (e.g., GeminiProvider, CohereProvider).

## Architecture Decision Records (ADR)

- **ADR-P10-001**: Use FastAPI StreamingResponse for SSE.
- **ADR-P10-002**: Adopt Jinja2 for prompt templating over simple string interpolation for advanced logical operations.
- **ADR-P10-003**: Citation extraction occurs post-generation via Regex rather than structured object generation to reduce token latency.

## Versioning Strategy

All prompt templates are versioned explicitly (e.g., 1.0-strict-citations). Major updates to prompt engineering require a new version to prevent breaking changes to existing dependent services.

## Feature Flags

- FF_ENABLE_STREAMING: Toggles SSE output vs. batch JSON response.
- FF_ENABLE_STRICT_HALLUCINATION_GUARDRAILS: Enforces prompt directives that restrict output strictly to context.

## Performance Budgets

- **Time to First Token (TTFT)**: < 400ms.
- **Generation Token Throughput**: > 30 tokens/second.
- **Citation Post-Processing Latency**: < 50ms.

## Sequence Diagrams

`mermaid
sequenceDiagram
    participant Client
    participant ExecutionGateway
    participant GenerationOrchestrator
    participant PromptEngine
    participant LLMProvider
    participant CitationEngine

    Client->>ExecutionGateway: POST /execute (stream=true)
    ExecutionGateway->>GenerationOrchestrator: PROCEED with Evidence
    GenerationOrchestrator->>PromptEngine: build_prompt(Query, Evidence)
    PromptEngine-->>GenerationOrchestrator: Rendered Prompt
    GenerationOrchestrator->>LLMProvider: generate_stream(Prompt)

    loop Stream Yield
        LLMProvider-->>ExecutionGateway: yield token
        ExecutionGateway-->>Client: SSE data: {"chunk": "..."}
    end

    LLMProvider-->>GenerationOrchestrator: Final Complete Text
    GenerationOrchestrator->>CitationEngine: parse(Text, Evidence)
    CitationEngine-->>GenerationOrchestrator: List of CitationDTO
    GenerationOrchestrator-->>ExecutionGateway: ExecutionResultDTO (Metadata)
    ExecutionGateway-->>Client: SSE data: {"citations": [...]}
`

## Failure Recovery Matrix

| Scenario | Detection Mechanism | Recovery Action |
|---|---|---|
| LLM Provider Timeout | Connection Error / Max Latency | Fallback to secondary provider (e.g., RerankerProvider (Cohere Implementation) -> LLMProvider (Gemini Implementation)). |
| Rate Limit Reached | 429 Too Many Requests | Exponential backoff retry (up to 3 times) before throwing RateLimitException. |
| Invalid Citation Format | Regex mismatch in post-processing | Strip malformed citations and log WARNING. Proceed with delivery. |

## Dependency Graph

`mermaid
graph TD
    A[ExecutionGateway v2] --> B[GenerationOrchestrator]
    B --> C[PromptTemplateEngine]
    B --> D[CitationEngine]
    B --> E[BaseLLMProvider]
    E --> F[GeminiProvider]
    E --> G[CohereProvider]
`

## Rollback Strategy

In the event of critical failures (e.g., sudden increase in hallucinations or latency spikes):
1. Revert ExecutionGateway to invoke Phase 3 Generation pipeline.
2. Toggle feature flag FF_ENABLE_STREAMING to alse if SSE connections are dropping.

## Success Metrics

- **Hallucination Rate**: < 1% (measured via post-generation evaluation).
- **Citation Accuracy**: > 98% of citations resolve to valid retrieved chunks.
- **Streaming Reliability**: > 99.9% of SSE sessions complete without dropping.

---

## 15. Completion Criteria

- [ ] All new components created.
- [ ] Streaming API functional and tested.
- [ ] Citation parsing working accurately.
- [ ] All unit and integration tests pass.
- [ ] Git commit: "Phase 10 Complete: Grounded Answer Generation".
- [ ] Progress tracker: 11/23 stages.
