# ADR-002: Hybrid Retrieval Strategy (Dense + Sparse + Reranking)

**Status**: Accepted
**Date**: 2026-07-17
**Author**: AI Infrastructure Engineer
**Phase**: Phase 0 — Architecture Freeze

---

## Context

Veritas RAG's core value proposition is detecting insufficient or conflicting context before generation. The retrieval quality directly determines whether the Confidence Engine has meaningful signals to evaluate. A single-strategy retrieval (dense-only or sparse-only) has well-documented failure modes that prevent accurate confidence scoring.

## Decision

We will implement **Hybrid Retrieval** combining:
1. Dense vector search (semantic similarity via embeddings stored in Qdrant)
2. Sparse keyword search (BM25 / keyword matching)
3. Reciprocal Rank Fusion (RRF) for result merging
4. Cross-encoder reranking for final ordering
5. Near-duplicate removal before evidence scoring

## Rationale

Dense search excels at semantic matching but fails on exact keyword queries and out-of-distribution queries. Sparse search handles exact terms but misses paraphrases. RRF combines ranked lists without requiring score normalization. Cross-encoder reranking re-evaluates top-k candidates with the full query context, materially improving precision at small k values — which is the k that feeds the Confidence Engine.

This directly satisfies FR-RET-1 through FR-RET-5.

## Consequences

**Positive:**
- Materially higher retrieval precision/recall than single-strategy retrieval.
- Deduplication prevents artificially inflated confidence from repeated evidence.
- Modular — each stage is independently replaceable per the maintainability NFR.

**Negative:**
- Higher latency than single-pass retrieval (mitigated by Redis caching of frequent queries).
- Cross-encoder reranking is the primary compute bottleneck (mitigated by bounded top-k).

## References
- PRD Section 5.2: Hybrid Retrieval (FR-2)
- PRD Section 22: AI Model & Algorithm Responsibility Matrix
