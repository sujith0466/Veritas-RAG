# Product Requirements Document

**Project:** Veritas RAG
**Tagline:** Enterprise Self-Correcting RAG Reliability Platform
**Document Type:** Enterprise PRD — Hackathon Round-1 Submission / Architecture Review / Staff Engineer Review
**Status:** Frozen for Round-1 Submission — Enterprise Review Enhancement Applied
**Version:** 1.1
**Prepared For:** OneInbox AI Internship Hackathon 2026 — AI Engineer Track, Problem Statement 1 (Self-Correcting RAG Pipeline)

**Version History**
- v1.0 — Initial enterprise PRD, 34 sections, approved for problem-statement alignment, product vision, architecture direction, and enterprise thinking.
- v1.1 — Enterprise PRD Review pass. No existing content removed, changed, or rescoped. Ten enterprise-governance sections added (Product Principles, Definition of Success, Requirement Traceability Matrix, Feature Priority Matrix, MVP vs. Future Release Roadmap, AI Model & Algorithm Responsibility Matrix, Evaluation Dataset Definition, Module Dependencies Matrix, Assumption Validation, and Product Design Principles — the last merged into Product Principles as a rationale column, see Summary of Improvements delivered alongside this document).

---

## Table of Contents

1. Executive Summary
2. Problem Statement
3. Industry Background
4. Current Challenges
5. Existing Solutions
6. Gap Analysis
7. Why Existing RAG Systems Fail
8. Product Vision
9. Mission
10. **Product Principles** *(new in v1.1)*
11. Objectives
12. **Definition of Success** *(new in v1.1)*
13. Success Metrics
14. Target Users
15. Personas
16. User Stories
17. Functional Requirements
18. Non-Functional Requirements
19. Detailed Feature Specifications
20. Core Modules
21. **Module Dependencies Matrix** *(new in v1.1)*
22. **AI Model & Algorithm Responsibility Matrix** *(new in v1.1)*
23. **Requirement Traceability Matrix** *(new in v1.1)*
24. Product Workflow
25. Business Rules
26. Assumptions
27. **Assumption Validation** *(new in v1.1)*
28. Constraints
29. Risks
30. Acceptance Criteria
31. **Feature Priority Matrix** *(new in v1.1)*
32. **MVP vs. Future Release Roadmap** *(new in v1.1)*
33. Out of Scope
34. Future Scope
35. Competitive Advantages
36. Why This Project Is Different
37. Innovation Highlights
38. Technical KPIs
39. Business KPIs
40. **Evaluation Dataset Definition** *(new in v1.1)*
41. Evaluation Metrics
42. Glossary
43. References

---

## 1. Executive Summary

Veritas RAG is a reliability layer that sits between retrieval and generation in enterprise Retrieval-Augmented Generation systems. It does not generate answers itself in the way a chatbot does; it decides whether an answer should be generated at all, under what conditions, and with what evidence, and it validates the result before it reaches a user.

The product directly targets Problem Statement 1 of the OneInbox AI Internship Hackathon 2026: a RAG system that identifies insufficient or conflicting context and intelligently re-queries or requests clarification instead of hallucinating, with measurable hallucination reduction as the acceptance criterion.

Veritas RAG is built as infrastructure, not as an application. It is designed to be placed in front of any existing retriever and any existing LLM, and to return either a validated, cited, reliability-scored answer, or an explicit request for clarification — never a silent guess. Every design decision in this document is filtered through one question: does this feature directly strengthen self-correcting RAG. Features that did not pass that filter during design review were removed; the resulting scope is deliberately narrower than the full universe of possible AI-reliability features, in exchange for being fully implementable and fully defensible within a hackathon timeline.

The remainder of this document specifies the product in enterprise PRD form: requirements, modules, workflows, business rules, risks, and the evaluation methodology that will be used to prove the platform's core claim — that self-correction measurably reduces hallucination relative to a baseline RAG pipeline on the same corpus, same queries, same base model.

---

## 2. Problem Statement

**Official problem statement (verbatim intent):** Build a Retrieval-Augmented Generation system that identifies insufficient or conflicting context and intelligently re-queries or asks users for clarification instead of hallucinating. Measure hallucination reduction before and after introducing the self-correction layer.

**Restated as a product problem:** Enterprise RAG systems today have no mechanism to know when they should not answer. They retrieve whatever the search index returns, above whatever similarity threshold was configured, and pass it to an LLM that will produce a fluent answer regardless of whether the retrieved evidence actually supports one. The system has no concept of "I don't have enough information" or "my sources disagree" — it has only "here is my best guess, phrased confidently." Veritas RAG exists to give the system that missing concept, and to act on it correctly: retry with a better query, ask the user a precise clarifying question, or refuse — instead of guessing.

---

## 3. Industry Background

Retrieval-Augmented Generation has become the default architecture for enterprise AI systems that need to answer questions grounded in private, proprietary, or frequently-changing information — internal knowledge bases, support documentation, policy repositories, contracts, and product documentation. The pattern is simple to describe (retrieve relevant documents, place them in context, generate an answer) and correspondingly simple to implement a first version of, which is why it has been adopted broadly and quickly across support automation, internal search, developer tooling, and compliance-adjacent question answering.

That same simplicity is the source of the industry's current reliability problem. Most production RAG deployments today are built as a single linear pipeline with no evaluation step between retrieval and generation, and no mechanism for the system to recognize its own uncertainty. As enterprises move these systems from internal pilots into customer-facing and compliance-sensitive contexts, the cost of an unflagged hallucination rises sharply — a wrong answer about a return policy, a compliance requirement, or a contractual term is not a minor UX defect, it is a liability. The market need this creates is not "a better chatbot" — it is a reliability and evaluation layer that can sit underneath any RAG application and make its failure modes visible, measurable, and correctable.

---

## 4. Current Challenges

- **Silent hallucination on sparse or narrow knowledge bases.** When retrieval returns weak or partial matches, most systems generate anyway, producing a fluent but ungrounded answer with no signal to the user that confidence was low.
- **No handling of contradictory sources.** Enterprise knowledge bases accumulate outdated and current versions of the same policy, conflicting regional variants, and draft-versus-final documents. Standard retrieval has no mechanism to detect that two retrieved chunks disagree.
- **Citations that do not verify anything.** Many RAG systems attach a citation to each generated sentence, but the citation is often only "this chunk was in context," not "this chunk actually supports this specific claim." This creates a false sense of verifiability.
- **No loop-termination discipline.** Ad hoc attempts at "try again if the answer looks bad" frequently lack a retry bound or an improvement check, creating risk of runaway cost and latency during a bad retrieval day.
- **No way to prove reliability improved.** Teams that do add safety layers rarely have a golden evaluation set or a repeatable before/after methodology, so claims of "reduced hallucination" are typically anecdotal rather than measured.
- **Knowledge base decay goes undetected.** Documents go stale, get duplicated, or develop internal contradictions over time, and nothing in a standard RAG stack proactively surfaces this — it only shows up as a downstream answer-quality problem, after the fact.

---

## 5. Existing Solutions

| Category | Examples of Approach | What They Cover |
|---|---|---|
| RAG orchestration frameworks | General-purpose retrieval-and-generation chaining libraries | Wiring retrieval to generation; minimal built-in reliability logic |
| Vector database platforms | Managed and self-hosted vector search products | Storage and similarity search; no answer-level validation |
| LLM evaluation/observability tooling | Offline evaluation and tracing libraries for LLM applications | Post-hoc scoring of groundedness/faithfulness on logged traffic; not inline, real-time self-correction |
| Guardrail/output-validation libraries | Rule- and schema-based output checking | Format and policy compliance; limited semantic groundedness checking |
| Prompt-engineering-only mitigations | "Only answer from the provided context" instructions | Reduces but does not reliably eliminate hallucination; provides no measurement or enforcement |

---

## 6. Gap Analysis

| Capability Needed by PS-1 | Covered by Existing Category | Gap |
|---|---|---|
| Detect insufficient context before generating | Partially (evaluation tools, offline only) | No inline, pre-generation gating in production traffic |
| Detect conflicting evidence across sources | Not covered | No existing mainstream tool performs pairwise contradiction detection across retrieved chunks |
| Intelligent query rewriting tied to a specific failure reason | Not covered | Rewriting exists in some frameworks but is not failure-reason-aware |
| Bounded, monotonic retry logic | Not covered | Ad hoc retry loops exist; formal termination guarantees do not |
| Post-generation claim-level citation verification | Partially (evaluation tooling, offline) | Rarely enforced inline before the answer reaches the user |
| Explainable, decomposed reliability score per answer | Not covered | Existing tools report aggregate offline metrics, not a per-response transparent score |
| Proactive knowledge base health monitoring tied to the same conflict/freshness signals used at query time | Not covered | Corpus quality tooling, where it exists, is disconnected from the query-time reliability engine |
| Repeatable, automated before/after hallucination measurement | Partially | Golden-set evaluation exists as a practice but is rarely built as a first-class, always-on product capability |

Veritas RAG's scope is defined precisely as the set of rows in this table — it exists to close these specific gaps, not to replace the categories above wholesale.

---

## 7. Why Existing RAG Systems Fail

Existing RAG systems fail for a structural reason, not an implementation-quality reason: they treat retrieval as a black box and generation as unconditional. There is no decision point between the two where the system asks "is this good enough to answer from." Confidence, where it exists at all, is usually a single similarity score, which conflates several distinct failure modes (insufficiency, conflict, staleness, ambiguity) into one number that cannot distinguish them and therefore cannot drive a correct corrective action. Without that distinction, the only available behaviors are "answer" or "refuse everything below a threshold" — neither of which is what a production system needs. Veritas RAG is precisely designed around: separate detection of each failure mode, and a distinct corrective action mapped to each one.

---

## 8. Product Vision

Enterprise AI systems should never answer with more confidence than their evidence supports. Veritas RAG's vision is a reliability layer, adoptable by any RAG application, that continuously evaluates retrieval quality, resolves what can be resolved automatically, asks for clarification when it cannot, validates every generated claim against cited evidence, and reports a transparent, explainable reliability score for every response — turning "can the AI answer" into "should the AI answer," as the default operating question of enterprise RAG.

---

## 9. Mission

To make Retrieval-Augmented Generation systems reliable, explainable, self-correcting, and observable by default, so that enterprises can deploy AI-driven question answering in compliance-sensitive and customer-facing contexts with a measurable, auditable basis for trust.

---

## 10. Product Principles *(new in v1.1)*

Each principle below is stated as an operating rule, paired with the design rationale for why it exists (fulfilling both "Product Principles" and "Product Design Principles" as a single, non-redundant section — see Summary of Improvements), and traced to the requirement(s) that enforce it so the principle is not aspirational language but a verifiable constraint.

| # | Principle | Why It Exists | Enforced By |
|---|---|---|---|
| 1 | **Never hallucinate silently.** An answer is only returned when its claims are supported; otherwise the system says so explicitly. | The core failure mode of enterprise RAG is not "wrong answer" — it's "wrong answer delivered with the same confidence as a right one." Silence about uncertainty is the actual defect being fixed. | FR-GEN-3, FR-VAL-4 |
| 2 | **Evidence before generation.** Generation is gated on a confidence threshold computed from retrieval-reliability signals; the LLM is never invoked on evidence the system already knows is inadequate. | Fixing hallucination after the fact is strictly harder and less reliable than preventing an ungrounded generation attempt in the first place. | FR-REL-5, FR-GEN-1 |
| 3 | **Retry before guessing.** When a failure is mechanically addressable (coverage gap, weak evidence, over-broad results), the system corrects the query before it considers the evidence insufficient. | Many "insufficient context" situations are retrieval problems, not knowledge-gap problems — the fix is a better search, not a lower bar for answering. | FR-SC-1, FR-SC-2 |
| 4 | **Clarify before assuming.** Genuine ambiguity or an unresolved conflict is surfaced to the user as a specific question, never silently resolved by picking one interpretation. | An assumed interpretation that turns out wrong is functionally identical to a hallucination from the user's perspective, even if every citation is individually accurate. | FR-SC-5, FR-SC-6 |
| 5 | **Trust must be measurable.** Every reliability claim the platform makes is backed by a decomposed score and a golden-set measurement — never asserted without a number behind it. | "Trust us, it's more reliable" is not an engineering claim; a claim that cannot be measured cannot be improved, regressed against, or defended under review. | FR-SCORE-1, FR-EVAL-2, AC-5 |
| 6 | **Explain every answer.** The Reliability Score and its signal breakdown accompany every response returned to a user or operator, not just internal logs. | Explainability that only engineers can see does not build enterprise trust; the person consuming the answer needs the same visibility. | FR-SCORE-3 |
| 7 | **One score, one truth.** The Reliability Score and the pre-generation Confidence Score are the same calibrated computation, re-scored with post-generation signals — the platform does not maintain two unreconciled numbers that claim to measure the same thing. | Parallel, disconnected metrics are a common source of enterprise mistrust in AI systems ("why does the dashboard say 90% but the answer felt wrong") — this principle closes that gap by construction. | FR-SCORE-2 |
| 8 | **Bounded correction, not infinite pursuit.** The self-correction loop has a hard retry ceiling and a monotonic-improvement check; it does not retry indefinitely chasing a passing score. | An unbounded retry loop is a production incident, not a reliability feature — cost and latency must be provably bounded for this to be deployable. | FR-SC-3, FR-SC-4 |
| 9 | **Reuse before duplicate.** Knowledge Health reuses Retrieval Reliability's conflict and freshness detection logic rather than shipping a second, disconnected corpus-quality system. | Every duplicated subsystem is a second thing that can drift out of sync with the first; reuse keeps the platform's reliability logic singular and auditable. | FR-KH-3, BR-6 |

---

## 11. Objectives

**Primary Objectives**
1. Detect insufficient retrieval before generation occurs.
2. Detect conflicting evidence across retrieved sources.
3. Rewrite poorly-performing queries using a failure-reason-specific strategy.
4. Ask precise, minimal clarification questions when automatic correction cannot resolve ambiguity or conflict.
5. Validate every generated claim against cited evidence before returning an answer.
6. Produce a transparent, decomposed reliability score for every response.
7. Measure hallucination rate before and after the self-correction layer on a shared golden evaluation set.
8. Continuously improve confidence calibration and retrieval quality using feedback and retry outcomes.

**Secondary Objectives**
1. Maintain latency within a defined production budget even with the added reliability pipeline.
2. Support enterprise multi-tenancy with isolated corpora and configurable thresholds per tenant.
3. Optimize LLM and compute cost through tiered model usage and caching.
4. Provide a dashboard-level view of system reliability suitable for non-technical stakeholders.
5. Enable straightforward integration in front of an existing retriever/LLM stack.

---

## 12. Definition of Success *(new in v1.1)*

Success for Veritas RAG is defined narrowly and deliberately, so it cannot be satisfied by activity that doesn't move the actual needle:

**Product success** means an enterprise team can place Veritas RAG in front of an existing retriever and LLM, with integration effort proportional to wiring one API call, and observe a measurable reduction in hallucination rate on their own traffic without materially degrading response latency below an interactive-use threshold.

**Engineering success** means the self-correction loop is provably bounded (verified by automated tests, not convention), every reliability claim the platform surfaces traces to a specific, inspectable signal rather than an opaque model output, and no module violates its documented input/output contract — meaning any single module (the reranker, the NLI model, the LLM provider) can be swapped without redesigning adjacent layers.

**Hackathon/Round-1 success** means a judge can independently verify the hallucination-reduction claim by inspecting the golden-set comparison methodology and its results, and the architecture withstands live cross-examination on its hardest questions without needing a reframe — specifically: who has retry authority (FR-SC-7), how the Reliability Score differs from the Confidence Score (FR-SCORE-2), and how a contradiction is actually detected rather than assumed away (FR-REL-4).

**Success is explicitly not**: the largest possible feature set, the highest raw answer-coverage rate (answering more often is not the goal if it comes at the cost of ungrounded answers), or an architecture that is impressive to describe but not fully inspectable. A version of this product that answers fewer questions but never answers one it shouldn't have is a successful outcome under this definition; a version that answers more questions with unmeasured hallucination risk is not.

---

## 13. Success Metrics

| Metric | Definition | Target for Round-1 Demo |
|---|---|---|
| Hallucination Rate Reduction | Relative decrease in unsupported-claim rate, self-correcting pipeline vs. baseline, on the golden set | Statistically demonstrable reduction, reported with actual numbers, not assumed |
| Clarification Precision | Fraction of clarification requests that were genuinely necessary (query was truly ambiguous/conflicting) | High precision — clarification should not be triggered by recoverable retrieval problems |
| Retry Success Rate | Fraction of retries that raised confidence above the acceptance threshold | Majority of retries should be productive; unproductive retry patterns should be visible in the dashboard, not hidden |
| Citation Accuracy | Fraction of citations that genuinely support their attached claim | Near-total accuracy on the golden set, enforced by rejection of unsupported claims |
| Reliability Score Correlation | Correlation between the platform's reliability score and human judgment of answer trustworthiness on the golden set | Demonstrated positive correlation on a sampled evaluation |
| End-to-End Latency | p95 latency for a fully-resolved query (no retry) | Within the budget defined in Non-Functional Requirements |

---

## 14. Target Users

- **Enterprise platform/AI engineering teams** building or operating internal RAG systems (support automation, internal knowledge search, developer documentation Q&A) who need a reliability layer they can adopt without rebuilding their retriever or LLM integration.
- **Compliance and knowledge management stakeholders** who need an auditable basis for trusting AI-generated answers in policy, legal, or regulated-content contexts.
- **Product teams shipping customer-facing RAG features** who need to reduce hallucination-driven support escalations and reputational risk.
- **Hackathon judges and technical reviewers** evaluating engineering depth, correctness of the self-correction mechanism, and rigor of the evaluation methodology.

---

## 15. Personas

**Persona 1 — Ananya, AI Platform Engineer**
Owns the internal RAG stack at a mid-size enterprise. Needs a reliability layer she can drop in front of her existing Qdrant-based retriever without re-architecting it. Primary concern: integration effort and added latency.

**Persona 2 — Marcus, Head of Enterprise Knowledge Management**
Owns the correctness of policy and compliance documentation surfaced through AI search. Primary concern: auditability — being able to show why the system trusted (or refused to trust) a given answer.

**Persona 3 — Priya, Product Manager for a Customer Support AI Feature**
Ships a customer-facing support assistant. Primary concern: hallucination-driven escalations and the user experience cost of over-frequent clarification requests.

**Persona 4 — Daniel, Hackathon Judge / Staff Engineer Reviewer**
Evaluates the submission for engineering rigor, correctness of the self-correction decision logic, and whether the hallucination-reduction claim is actually measured rather than asserted.

---

## 16. User Stories

| ID | As a... | I want... | So that... |
|---|---|---|---|
| US-01 | Platform Engineer | to place Veritas RAG in front of my existing retriever | I don't have to rebuild my retrieval stack to gain reliability guarantees |
| US-02 | Platform Engineer | to see why a query was rejected or sent to retry | I can debug retrieval quality issues instead of guessing |
| US-03 | Knowledge Manager | to see a decomposed reliability score for every answer | I can audit which answers are trustworthy without re-reading source documents myself |
| US-04 | Knowledge Manager | to be notified when the knowledge base has stale or conflicting documents | I can fix the source problem instead of only patching symptoms downstream |
| US-05 | Product Manager | to configure the clarification threshold for my tenant | I can balance answer availability against hallucination risk for my specific use case |
| US-06 | End User (via the application built on Veritas RAG) | to receive a precise clarifying question instead of a wrong confident answer | I get the right answer faster instead of acting on incorrect information |
| US-07 | Hackathon Judge | to see hallucination rate measured before and after the self-correction layer on the same query set | I can verify the core claim of the submission rather than take it on faith |
| US-08 | Platform Engineer | to see retry attempts capped and monotonically justified | I know the system cannot enter a runaway cost loop in production |
| US-09 | Compliance Stakeholder | to see every citation validated against its claim before the answer is returned | I can trust that "cited" means "actually supported," not just "was in context" |
| US-10 | Platform Engineer | to see per-tenant isolation of corpora and thresholds | I can operate the platform safely across multiple internal teams or customers |

---

## 17. Functional Requirements

### Query Understanding (FR-QU)
- **FR-QU-1:** The system shall classify query intent (factual lookup, comparison, procedural, out-of-scope) prior to retrieval.
- **FR-QU-2:** The system shall extract entities from the query to support downstream coverage checking.
- **FR-QU-3:** The system shall normalize the query (casing, abbreviation expansion, spelling correction) while preserving the original query for reference.
- **FR-QU-4:** The system shall detect queries that are inherently ambiguous before committing a retrieval round, using conversation context where available.

### Hybrid Retrieval (FR-RET)
- **FR-RET-1:** The system shall retrieve candidates using both dense (vector) and sparse (keyword/BM25) search.
- **FR-RET-2:** The system shall support metadata filtering for tenant isolation and access control prior to ranking.
- **FR-RET-3:** The system shall fuse dense and sparse result sets using rank-based fusion.
- **FR-RET-4:** The system shall re-rank the fused candidate set using a cross-encoder model prior to reliability evaluation.
- **FR-RET-5:** The system shall remove near-duplicate chunks prior to evidence scoring to prevent artificially inflated confidence.

### Retrieval Reliability (FR-REL)
- **FR-REL-1:** The system shall compute a coverage score indicating whether all sub-questions/entities in the query are addressed by retrieved evidence.
- **FR-REL-2:** The system shall compute an evidence-strength score per retrieved chunk relative to the query.
- **FR-REL-3:** The system shall compute a freshness score for retrieved documents relative to a configurable staleness threshold.
- **FR-REL-4:** The system shall detect contradictions between retrieved chunks and produce a conflict score.
- **FR-REL-5:** The system shall combine coverage, evidence, freshness, conflict, and source-trust signals into a single calibrated confidence score.

### Self-Correction (FR-SC)
- **FR-SC-1:** The system shall retry retrieval with a rewritten query when confidence is below the acceptance threshold and retries remain.
- **FR-SC-2:** The query rewrite strategy shall be selected based on the specific detected failure reason (insufficiency, ambiguity, over-breadth), not applied generically.
- **FR-SC-3:** The system shall enforce a maximum of two automatic retries per query.
- **FR-SC-4:** The system shall require a minimum confidence improvement after each retry to continue retrying; on plateau or decline, it shall escalate rather than retry again.
- **FR-SC-5:** The system shall route to clarification when ambiguity or conflict cannot be resolved by retrieval correction alone.
- **FR-SC-6:** The system shall generate clarification questions that are specific to the detected gap (missing entity, conflicting sources) rather than generic.
- **FR-SC-7:** The retry/escalate decision authority shall reside solely in the Self-Correction Orchestration function; no other module may unilaterally trigger a retry.

### Answer Generation (FR-GEN)
- **FR-GEN-1:** The system shall generate answers strictly from context that has passed the confidence threshold.
- **FR-GEN-2:** Every factual claim in a generated answer shall carry an attached citation to a specific retrieved chunk.
- **FR-GEN-3:** The system shall reject generation attempts that would require content not present in the approved context.

### Answer Validation (FR-VAL)
- **FR-VAL-1:** The system shall extract atomic factual claims from the generated answer.
- **FR-VAL-2:** The system shall verify that each claim's cited chunk actually entails that claim, not merely co-occurs with it.
- **FR-VAL-3:** The system shall compute a groundedness score across all claims in the answer.
- **FR-VAL-4:** The system shall flag and reject answers containing unsupported claims, routing them back to self-correction rather than returning them to the user.

### Reliability Scoring (FR-SCORE)
- **FR-SCORE-1:** The system shall compute a single 0–100 Reliability Score per response, decomposed into its constituent signal scores (coverage, evidence, citation accuracy, freshness, conflict, groundedness).
- **FR-SCORE-2:** The Reliability Score shall be derived from the same calibrated model used for pre-generation confidence, re-scored with post-generation signals — it shall not be an independently invented second scoring system.
- **FR-SCORE-3:** The Reliability Score and its breakdown shall be returned alongside every answer, not only logged internally.

### Knowledge Health (FR-KH)
- **FR-KH-1:** The system shall periodically scan the knowledge base for duplicate documents.
- **FR-KH-2:** The system shall periodically identify documents approaching or past a configured staleness threshold.
- **FR-KH-3:** The system shall proactively surface document-level conflicts using the same conflict-detection logic used at query time, rather than a separate mechanism.
- **FR-KH-4:** The system shall report knowledge health findings to a corpus owner without requiring a user query to have triggered the discovery.

### Evaluation (FR-EVAL)
- **FR-EVAL-1:** The system shall maintain a golden evaluation set covering standard, insufficient-context, conflicting-context, and stale-context query cases.
- **FR-EVAL-2:** The system shall support running the same golden set through a baseline (no self-correction) and a self-correcting configuration for direct comparison.
- **FR-EVAL-3:** The system shall report hallucination rate, groundedness, citation accuracy, and retrieval precision/recall for both configurations.

### Analytics/Observability (FR-OBS)
- **FR-OBS-1:** The system shall expose a dashboard reporting reliability score distribution, hallucination rate, retry rate, clarification rate, and knowledge health status.
- **FR-OBS-2:** The system shall log the specific failure reason for every non-first-pass resolution (retry or clarification), queryable by category.

---

## 18. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Latency** | p95 end-to-end latency for a first-pass (no-retry) resolution shall remain within a defined interactive-use budget; a retried query is permitted additional latency proportional to one extra retrieval-and-evaluation cycle, and this cost shall be visible in observability, not hidden. |
| **Availability** | Core query-resolution path shall degrade gracefully (e.g., fall back to sparse-only retrieval, or skip non-critical scoring signals) rather than fail completely if a single downstream dependency (reranker, NLI model) is unavailable. |
| **Reliability** | The self-correction control loop shall be provably bounded — no query may retry beyond the configured maximum, verified by automated tests, not by convention alone. |
| **Security** | Retrieved content shall be treated as untrusted input; the platform shall isolate tenant corpora and access-control metadata at the retrieval layer, not only at the application layer. |
| **Scalability** | Retrieval, reranking, and reliability-scoring components shall scale horizontally and independently of one another. |
| **Maintainability** | Each of the ten architectural layers shall expose a clear input/output contract so that any individual module (e.g., the reranker) can be replaced without redesigning adjacent layers. |
| **Observability** | Every stage of the pipeline shall emit structured, traceable telemetry sufficient to reconstruct why any individual query received the resolution it did. |
| **Performance** | The reliability and validation layers shall be designed so that their added computational cost is dominated by cacheable or batchable operations wherever possible, to avoid becoming the primary latency bottleneck. |
| **Cost** | LLM usage shall be tiered — cheaper models for classification-type tasks (intent, ambiguity), higher-capability models reserved for generation and judgment-heavy validation calls. |

---

## 19. Detailed Feature Specifications

**Self-Correction Decision Loop.** On receiving a query, the system computes a confidence score from retrieval-reliability signals before allowing generation. If confidence meets the acceptance threshold, generation proceeds. If not, and if the specific failure reason is mechanically addressable (coverage gap, weak evidence, over-broad results) and a retry budget remains, the Query Rewrite function produces a new query targeted at that specific failure reason, and retrieval runs again. If the failure reason is genuine ambiguity in user intent, or a conflict that cannot be resolved by freshness or source-trust comparison, the system does not retry — it routes directly to clarification. After each retry, confidence must improve by at least a minimum threshold to justify a further retry; if it does not, the system escalates to clarification rather than retrying again. The retry budget is hard-capped at two automatic attempts.

**Answer Validation.** After generation, the system does not treat the LLM's output as final. It extracts each atomic factual claim, matches it to its cited evidence chunk, and verifies entailment between the two. Claims that are not supported by their citation cause the answer to be rejected and routed back into the self-correction loop rather than returned to the user, even if the initial pre-generation confidence was high — this is the platform's check against the case where retrieval was adequate but generation still drifted from the evidence.

**Reliability Scoring.** Every returned answer carries a 0–100 Reliability Score with a visible breakdown across coverage, evidence strength, citation accuracy, freshness, conflict status, and groundedness. This is the same calibrated confidence computation used to gate generation, re-run with post-generation signals folded in — it is presented differently for end-user and dashboard consumption, but it is not a second, independently-invented scoring mechanism.

**Knowledge Health Monitoring.** Independently of user queries, the platform periodically re-applies its own conflict-detection and freshness-analysis logic across the corpus as a whole, surfacing duplicate, stale, and internally-conflicting documents to the corpus owner. This directly improves future retrieval quality and is explicitly scoped to reuse existing detection logic rather than introduce a separate analysis system.

**Clarification Generation.** When the system cannot resolve ambiguity or conflict automatically, it generates a clarification question grounded in the specific detected gap — naming the missing entity, or presenting the specific conflicting claims and their sources — rather than a generic "can you rephrase that."

---

## 20. Core Modules

| Module | Explanation |
|---|---|
| **Query Intelligence** | Understands the query before any retrieval occurs — intent, entities, normalization, ambiguity — producing an optimized search query and the signals needed for later coverage checking. |
| **Hybrid Retrieval** | Retrieves and ranks the best available evidence using dense and sparse search, fusion, cross-encoder reranking, and deduplication. |
| **Retrieval Reliability** | Determines whether the retrieved evidence is good enough to generate from, via coverage, evidence-strength, freshness, and conflict analysis, aggregated into a calibrated confidence score. |
| **Self-Correction** | The decision authority of the platform. Owns the retry/rewrite/clarify/proceed decision, the retry bound, and the monotonic-improvement check. |
| **Reflection** | Post-generation judgment of whether the answer, as generated, is actually grounded — distinct from pre-generation confidence, which only judges the evidence, not the eventual answer. |
| **Query Rewrite** | Produces a corrected query targeted at a specific detected failure reason (decomposition, disambiguation, broadening, narrowing), invoked only by the Self-Correction module. |
| **Clarification** | Produces a precise, gap-specific question to the user when automatic correction cannot resolve the issue. |
| **Answer Validation** | Extracts claims from the generated answer, verifies each against its citation, and computes groundedness — rejecting answers that fail. |
| **Reliability Scoring** | Computes and exposes the decomposed 0–100 Reliability Score for every response. |
| **Knowledge Health** | Proactively scans the corpus for duplication, staleness, and conflict using the same detection logic as the query-time pipeline. |
| **Evaluation** | Maintains the golden evaluation set and runs baseline-vs-self-corrected comparisons to measure the platform's core claim. |
| **Analytics** | Surfaces reliability score distribution, hallucination rate, retry/clarification rates, and knowledge health status to operators. |

---

## 21. Module Dependencies Matrix *(new in v1.1)*

| Module | Upstream Dependencies (needs input from) | Downstream Consumers (feeds output to) | Dependency Type |
|---|---|---|---|
| Query Intelligence | Session/conversation context (for disambiguation) | Hybrid Retrieval | Data |
| Hybrid Retrieval | Query Intelligence (optimized query) | Retrieval Reliability | Data |
| Retrieval Reliability | Hybrid Retrieval (ranked, deduplicated candidates) | Self-Correction (confidence + failure reason), Answer Generation (approved context, if proceeding) | Data + Control (gates generation) |
| Self-Correction | Retrieval Reliability (confidence/failure signal), Reflection (post-generation verdict) | Query Rewrite (invocation), Clarification (invocation), Hybrid Retrieval (loop-back on retry), Answer Generation (proceed signal) | Control (sole decision authority — FR-SC-7) |
| Query Rewrite | Self-Correction (specific failure reason) | Hybrid Retrieval (re-invocation with new query) | Data, invoked only by Self-Correction |
| Clarification | Self-Correction (routing decision + gap details) | API/response layer (returned to user) | Data, invoked only by Self-Correction |
| Answer Generation | Self-Correction (proceed decision), Retrieval Reliability (approved context) | Answer Validation | Data |
| Answer Validation | Answer Generation (draft answer), original retrieved evidence | Reflection (claim-level verdicts), Self-Correction (rejection path), Reliability Scoring (groundedness input) | Data + Control (rejection path) |
| Reflection | Answer Validation (claim-citation verdicts) | Self-Correction (accept/reject signal) | Control |
| Reliability Scoring | Retrieval Reliability (confidence computation), Answer Validation (groundedness) | Analytics, API response payload | Data |
| Knowledge Health | Retrieval Reliability (reused conflict/freshness logic, run corpus-wide rather than per-query) | Analytics | Data, offline/scheduled |
| Evaluation | Golden Dataset, full pipeline (baseline and self-correcting runs) | Retrieval Reliability (calibration feedback), Analytics/reporting | Calibration feedback loop, offline/CI |
| Analytics | Reliability Scoring, Self-Correction logs, Knowledge Health reports, Evaluation reports | None (terminal consumer) | Data (read-only aggregation) |

This matrix confirms there are no circular runtime dependencies in the query-resolution hot path: the only loop in the system is the explicit, bounded Self-Correction → Query Rewrite → Hybrid Retrieval cycle, which is intentional and governed by FR-SC-3/FR-SC-4, not an accidental architectural cycle.

---

## 22. AI Model & Algorithm Responsibility Matrix *(new in v1.1)*

| Module | Uses LLM | Uses Embeddings | Uses Rules | Uses ML (non-LLM) | Uses Retrieval | Uses Reranker | Notes |
|---|---|---|---|---|---|---|---|
| Query Intelligence | Yes (lightweight, intent/ambiguity classification) | Yes (entity/ambiguity similarity) | Yes (normalization rules) | Optional (small classifier) | No | No | Deliberately uses the cheapest model tier available — this is a high-volume, low-complexity classification task |
| Hybrid Retrieval | No | Yes (dense search) | Yes (metadata filter logic) | No | Yes (core function) | Yes (cross-encoder reranking) | The reranker here is the primary latency/compute bottleneck of the retrieval stack |
| Retrieval Reliability | Yes (claim extraction for evidence/conflict scoring) | Yes (similarity-based signals) | Yes (freshness decay function, thresholds) | Yes (NLI entailment model; calibration model for confidence) | No (consumes retrieval output) | No | The calibration model is fit against labeled data, not hand-tuned weights (see FR-REL-5) |
| Self-Correction | No | Yes (rewrite-diversity check via embedding similarity) | Yes (retry ceiling, monotonicity check, routing policy) | No | No | No | Deliberately rule-based and deterministic — no LLM sits inside the decision authority itself, so the control loop remains auditable and reproducible (FR-SC-7) |
| Query Rewrite | Yes (rewrite generation, HyDE) | Yes (HyDE embedding) | Yes (strategy-selection mapping by failure reason) | No | No (produces the query fed to retrieval) | No | |
| Clarification | Yes (question phrasing) | No | Yes (template library per failure type) | No | No | No | Templates constrain the LLM to avoid vague, unhelpful clarifications |
| Answer Generation | Yes (core function) | No | Yes (citation-forcing structured output format) | No | No (consumes approved context) | No | |
| Answer Validation | Yes (claim extraction, borderline-case judge escalation) | No | Yes (rejection thresholds) | Yes (NLI entailment model, shared with Retrieval Reliability) | No | No | Deterministic NLI check is preferred over a full LLM judge call wherever possible, for cost and auditability |
| Reflection | Yes (structured rubric judge) | No | Yes (rule-based gates run before any LLM judge call) | No (reuses Answer Validation's NLI where applicable) | No | No | Majority of rejections are caught by rule-based gates alone, before the LLM judge is invoked |
| Reliability Scoring | No | No | Yes (aggregation formula) | Yes (same calibration model as Retrieval Reliability) | No | No | Confirms FR-SCORE-2 — no separate model is introduced for this module |
| Knowledge Health | No new model | Yes (duplicate-detection clustering) | Yes (staleness thresholds) | No new model | No | No | Explicitly reuses Retrieval Reliability's conflict/freshness models rather than training or hosting new ones |
| Evaluation | Yes (automated scoring, judge-consistency checks) | Yes | Yes (golden-set comparison methodology) | Yes (calibration validation) | Yes (replays queries through retrieval) | Yes (replays through full pipeline) | The only module that exercises the full pipeline end-to-end for measurement purposes |
| Analytics | No | No | Yes (aggregation/visualization logic only) | No | No | No | Pure read-side consumer; introduces no new inference of any kind |

---

## 23. Requirement Traceability Matrix *(new in v1.1)*

| Requirement | Module | Service/Component | Evaluation Metric |
|---|---|---|---|
| FR-QU-1 | Query Intelligence | Intent Classifier | Retrieval Precision (indirect, via routing) |
| FR-QU-2 | Query Intelligence | Entity Extractor | Coverage |
| FR-QU-3 | Query Intelligence | Query Normalizer | Retrieval Precision/Recall |
| FR-QU-4 | Query Intelligence | Ambiguity Detector | Clarification Precision |
| FR-RET-1 | Hybrid Retrieval | Vector Search + BM25 Search | Retrieval Precision/Recall |
| FR-RET-2 | Hybrid Retrieval | Metadata Filter | Retrieval Precision (tenant-scoped), Security/isolation audit |
| FR-RET-3 | Hybrid Retrieval | Retrieval Fusion (RRF) | Retrieval Precision/Recall |
| FR-RET-4 | Hybrid Retrieval | Cross-Encoder Reranker | Retrieval Precision, Context Utilization |
| FR-RET-5 | Hybrid Retrieval | Deduplicator | Context Utilization |
| FR-REL-1 | Retrieval Reliability | Coverage Analyzer | Coverage |
| FR-REL-2 | Retrieval Reliability | Evidence Scoring Engine | Groundedness (pre-generation proxy) |
| FR-REL-3 | Retrieval Reliability | Freshness Analyzer | Freshness Score |
| FR-REL-4 | Retrieval Reliability | Conflict Detection Engine | Conflict Detection Precision/Recall |
| FR-REL-5 | Retrieval Reliability | Confidence Engine | Confidence Score, Reliability Score Correlation |
| FR-SC-1 to FR-SC-4 | Self-Correction | Self-Correction Orchestrator | Retry Success Rate |
| FR-SC-5, FR-SC-6 | Self-Correction | Clarification routing logic | Clarification Precision |
| FR-SC-7 | Self-Correction | Self-Correction Orchestrator | Reliability (loop-bound test coverage, not a runtime metric) |
| FR-GEN-1 to FR-GEN-3 | Answer Generation | Answer Generator | Hallucination Rate, Citation Accuracy (recall side) |
| FR-VAL-1, FR-VAL-2 | Answer Validation | Claim Extractor / Citation Verifier | Citation Accuracy (precision side), Groundedness |
| FR-VAL-3, FR-VAL-4 | Answer Validation | Groundedness Scorer / Rejection Gate | Groundedness, Hallucination Rate |
| FR-SCORE-1 to FR-SCORE-3 | Reliability Scoring | Reliability Score Engine | Reliability Score Correlation |
| FR-KH-1 to FR-KH-4 | Knowledge Health | Knowledge Health Scanner | Conflict Score (corpus-level), Freshness Score (corpus-level) |
| FR-EVAL-1 to FR-EVAL-3 | Evaluation | Golden Set Runner | Hallucination Rate Reduction (primary claim metric, AC-5) |
| FR-OBS-1, FR-OBS-2 | Analytics | Dashboard / Structured Logging | All Technical KPIs (Section 38) |

---

## 24. Product Workflow

```
User Query
   │
   ▼
API Gateway → Authentication → Rate Limiting
   │
   ▼
Query Intelligence (intent, entities, normalization, ambiguity)
   │
   ▼
Hybrid Retrieval (dense + sparse + fusion + rerank + dedup)
   │
   ▼
Retrieval Reliability (coverage, evidence, freshness, conflict → confidence)
   │
   ├── confidence sufficient ──────────────► Answer Generation
   │                                              │
   │                                              ▼
   │                                        Answer Validation
   │                                              │
   │                                    ┌─────────┴─────────┐
   │                                    │                   │
   │                              claims grounded     claims unsupported
   │                                    │                   │
   │                                    ▼                   ▼
   │                         Reliability Scoring     Self-Correction (retry/clarify)
   │                                    │
   │                                    ▼
   │                              Final Response
   │
   └── confidence insufficient ──► Self-Correction
                                        │
                        ┌───────────────┼───────────────┐
                        │               │               │
                 retry (budget      clarify         escalate/refuse
                 remains, gain       (ambiguity/      (out of scope,
                 expected)           conflict         budget exhausted)
                        │            unresolved)             │
                        ▼               │                    ▼
                 Query Rewrite ─────────┘             Return to user with
                        │                              explicit refusal
                        ▼                              or clarification
                 Hybrid Retrieval (loop, max 2x)
```

All resolutions — successful answer, clarification, or refusal — flow into Analytics and, where applicable, into the Evaluation module's golden-set comparison and the Knowledge Health module's corpus-level signal accumulation.

---

## 25. Business Rules

- BR-1: Maximum of two automatic retries per query; no exceptions without explicit tenant-level configuration override.
- BR-2: A retry is only permitted if it is expected to improve confidence for a mechanically addressable failure reason; genuine ambiguity or unresolved conflict routes directly to clarification, never to a blind retry.
- BR-3: An answer shall never be returned to the user if it contains a claim that failed citation verification.
- BR-4: The Reliability Score shown to the user or operator shall always include its decomposition; an undecomposed score is not a valid output of this system.
- BR-5: Tenant corpora and thresholds are isolated; no cross-tenant retrieval or threshold leakage is permitted.
- BR-6: Knowledge Health findings shall reuse Retrieval Reliability's conflict and freshness logic; a separate, disconnected corpus-analysis implementation is out of scope.
- BR-7: All confidence and reliability scoring weights are calibrated against the golden evaluation set and versioned; changes to calibration require a corresponding evaluation re-run before deployment.

---

## 26. Assumptions

- A representative document corpus and a labeled golden evaluation set (including insufficient-context, conflicting-context, and stale-context cases) can be constructed or approximated within the hackathon timeline.
- The underlying LLM and embedding provider are stable and available for the duration of development and demo.
- Tenant/document metadata (timestamps, source trust tier) is available or can be reasonably simulated for the freshness and source-trust signals.
- A hackathon-scale deployment (single-tenant demo, moderate document volume) is sufficient to demonstrate the architecture; full enterprise-scale load is a future-scope concern, not a Round-1 build requirement.

---

## 27. Assumption Validation *(new in v1.1)*

| Assumption | Validation Method | Owner / Timing | Risk If Invalid |
|---|---|---|---|
| A representative corpus and labeled golden set can be built within the hackathon timeline | Construct the golden set's adversarial cases (insufficient/conflicting/stale) first, before general build work, and dry-run the evaluation harness end-to-end early rather than at the end | Build-phase, before feature work begins on Self-Correction | AC-5 (the core measured claim) cannot be demonstrated at submission time |
| The LLM/embedding provider is stable for the build and demo window | Pin a single provider and model version for the duration of the project; identify and document one fallback provider in advance | Build-phase setup | A provider outage during the live demo blocks the presentation entirely if no fallback is pre-configured |
| Tenant/document metadata (timestamps, trust tier) is available for freshness/trust signals | Where real metadata is unavailable, inject clearly-labeled synthetic metadata into the demo corpus rather than omitting the signal silently | Corpus preparation phase | Freshness-based conflict resolution becomes untestable, and a judge may reasonably question whether it works at all if it's never exercised |
| Hackathon-scale deployment is sufficient to demonstrate the architecture | Explicitly scope the Round-1 demo to single-tenant, moderate corpus volume, and present full-scale claims as designed-but-not-built, clearly labeled as such in the architecture review materials | Documentation/demo-prep phase | A reviewer may conflate an unbuilt scale claim with a demonstrated capability if the distinction is not made explicit, damaging credibility on claims that are actually solid |

---

## 28. Constraints

- Hackathon timeline limits the depth of implementation for lower-priority modules (Knowledge Health, full Analytics dashboard) relative to the core self-correction and validation loop, which is the primary judged capability.
- Compute budget constrains the use of large, self-hosted cross-encoder and NLI models; hosted API alternatives may be substituted for the MVP with the tradeoff explicitly documented.
- Dependency footprint should remain minimal for the demo deployment environment to avoid installation/runtime issues under constrained container resources.

---

## 29. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Golden evaluation set is too small to produce statistically credible before/after numbers | Medium | High — undermines the core measured claim | Deliberately construct adversarial insufficient/conflicting/stale cases rather than relying only on organic queries, to ensure the self-correction paths are actually exercised and measurable |
| Reflection/validation judge itself produces an incorrect verdict | Medium | Medium | Constrain judge output to structured, per-claim, evidence-referenced format; prefer deterministic NLI checks over free-form LLM judgment where possible |
| Added pipeline latency undermines interactive usability | Medium | Medium | Cache aggressively, bound retrieval breadth fed into expensive reranking/NLI stages, measure and disclose latency honestly rather than hiding it |
| Retry loop misconfiguration causes runaway cost | Low | High | Hard-coded retry ceiling enforced in the Self-Correction module, covered by automated tests |
| Scope creep re-introduces features that don't strengthen PS-1 | Medium | Medium | Every feature is checked against the explicit filter question in this document before inclusion; Knowledge Health and Reliability Scoring are deliberately scoped thin |
| Reliability Score is perceived as duplicating Confidence Score with no clear distinction | Low | Medium | Documented explicitly in this PRD (FR-SCORE-2) as the same calibrated computation, presented differently — not a second system |

---

## 30. Acceptance Criteria

- **AC-1:** Given a query with genuinely insufficient retrieved context, the system shall not generate an answer; it shall either retry with a rewritten query or return a clarification request.
- **AC-2:** Given two retrieved documents that directly contradict each other on the query's topic, the system shall detect the conflict and either resolve it via freshness/source-trust or surface it explicitly in a clarification question.
- **AC-3:** Given a query that resolves successfully, every factual claim in the returned answer shall carry a citation that passes entailment verification against its source chunk.
- **AC-4:** Given the retry budget is exhausted without reaching the confidence threshold, the system shall escalate to clarification, not return a low-confidence answer silently.
- **AC-5:** Given the golden evaluation set, the system shall produce a measured hallucination rate for both a baseline (no self-correction) and self-correcting configuration, with the self-correcting configuration showing a demonstrable reduction.
- **AC-6:** Given any returned answer, the system shall expose a Reliability Score with its full signal breakdown, not an opaque number.

---

## 31. Feature Priority Matrix *(new in v1.1)*

| Feature / Capability | Priority | Justification | Maps To |
|---|---|---|---|
| Ambiguity-aware Query Intelligence | P0 | Directly required for the clarification path to be gap-specific rather than generic | FR-QU-4 |
| Hybrid Retrieval (dense + sparse + fusion + rerank) | P0 | Foundation for every downstream reliability signal; without it, confidence scoring has nothing meaningful to evaluate | FR-RET-1 to FR-RET-5 |
| Retrieval Reliability (coverage, evidence, freshness, conflict, confidence) | P0 | This is the detection layer PS-1 explicitly requires | FR-REL-1 to FR-REL-5 |
| Self-Correction loop (retry/rewrite/clarify, bounded) | P0 | This is the correction layer PS-1 explicitly requires | FR-SC-1 to FR-SC-7 |
| Answer Generation with mandatory citation | P0 | Without enforced citation, claim-level validation has nothing to check | FR-GEN-1 to FR-GEN-3 |
| Answer Validation (claim-citation entailment) | P0 | Directly prevents the specific failure mode of a confidently generated but ungrounded answer | FR-VAL-1 to FR-VAL-4 |
| Reliability Scoring (basic decomposed score) | P0 | Required by AC-6 and by the "explain every answer" principle | FR-SCORE-1 to FR-SCORE-3 |
| Evaluation (golden set + baseline comparison) | P0 | This is literally the official problem statement's stated acceptance criterion | FR-EVAL-1 to FR-EVAL-3, AC-5 |
| Knowledge Health Engine (thin scope: duplicate/stale/conflict scan) | P1 | Strengthens the platform's proactive story but is not required to satisfy PS-1's core acceptance criteria | FR-KH-1 to FR-KH-4 |
| Analytics Dashboard | P1 | High demo value, but is a visualization layer over metrics the P0 items already compute — not blocking for the core claim | FR-OBS-1 |
| Multiple query-rewrite strategies (decomposition, HyDE, broadening, narrowing) | P1 | A single generic rewrite strategy would satisfy FR-SC-2 minimally; the full strategy set materially improves retry success rate | FR-SC-2 |
| Freshness/source-trust automatic conflict resolution | P1 | Improves user experience (fewer unnecessary clarifications) but the system is still PS-1-compliant if all conflicts route to clarification | FR-REL-4 |
| Multi-LLM ensemble validation | P2 | Explicitly deferred — cost/complexity not justified for MVP; documented in Future Scope | Not mapped to a current FR |
| Adaptive, auto-tuned per-tenant thresholds | P2 | Requires operating history/data the hackathon timeline cannot produce | Not mapped to a current FR |
| Full multi-region, load-tested scaling implementation | P2 | Architecturally described but explicitly out of scope for Round-1 build | Not mapped to a current FR |
| Knowledge-graph-backed persistent conflict tracking | P2 | Future-scope enhancement to Knowledge Health, not required for its P1 scope | Not mapped to a current FR |

---

## 32. MVP vs. Future Release Roadmap *(new in v1.1)*

| Release | Scope | Key Modules Included | Explicit Exclusions |
|---|---|---|---|
| **MVP (Round-1 Submission)** | Single-tenant demo, moderate corpus volume, all P0 features functional end-to-end, hand-calibrated or minimally-trained confidence weights acceptable if the golden-set comparison is real | Query Intelligence (ambiguity focus), Hybrid Retrieval, Retrieval Reliability, Self-Correction, Answer Generation, Answer Validation, Reliability Scoring, Evaluation | Knowledge Health, full Analytics Dashboard, multi-tenant isolation enforcement, fully ML-calibrated confidence model |
| **Version 1 (Round-2 Implementation / initial post-hackathon release)** | Full P0 + P1 feature set; confidence model calibrated against labeled data rather than hand-tuned; Knowledge Health running on a real schedule | All MVP modules, plus Knowledge Health, Analytics Dashboard, full query-rewrite strategy set, freshness/trust-based automatic conflict resolution | Multi-LLM ensemble, adaptive threshold auto-tuning, multi-region scaling |
| **Version 2 (near-term future)** | Production hardening for real multi-tenant load | Multi-tenant enforcement at scale, self-hosted reranker/NLI infrastructure sized for production throughput, expanded golden set with continuous CI-integrated evaluation | Knowledge-graph-backed conflict tracking, agentic multi-hop retrieval |
| **Future (long-term, per Section 34)** | Advanced capabilities beyond the current architecture's core scope | Multi-LLM ensemble validation, adaptive per-tenant threshold auto-tuning, knowledge-graph-backed persistent conflict tracking, agentic multi-hop retrieval, federated retrieval | — |

---

## 33. Out of Scope

- General-purpose chatbot or conversational assistant functionality unrelated to grounded, evidence-based question answering.
- Multi-LLM ensemble validation as a default execution path (documented as future scope, not a Round-1 build target).
- Full enterprise-scale multi-region deployment and load-tested horizontal scaling (architecturally described, not fully implemented, for Round-1).
- General corpus management features (document upload/versioning UI, content authoring tools) beyond what Knowledge Health strictly requires to detect duplication, staleness, and conflict.
- Voice, multimodal, or non-text retrieval modalities.

---

## 34. Future Scope

- Adaptive, per-tenant confidence thresholds tuned automatically from observed clarification-abandonment and retry-success data.
- Knowledge-graph-backed conflict detection for corpus-wide, persistent contradiction tracking rather than per-query recomputation.
- Multi-LLM ensemble validation for high-stakes tenants, at a configurable cost/latency tradeoff.
- Agentic, multi-hop retrieval for queries that genuinely require synthesizing evidence across multiple retrieval rounds by design, not only as a failure-correction path.
- Federated retrieval across multiple, separately-governed knowledge bases with cross-source trust weighting.

---

## 35. Competitive Advantages

- Detects and distinguishes four distinct retrieval failure modes (insufficiency, conflict, staleness, ambiguity) rather than collapsing them into a single similarity threshold — enabling the correct corrective action for each, rather than one blunt refusal/answer decision.
- Claim-level citation verification that checks entailment, not mere co-occurrence — a meaningfully stronger trust guarantee than "a source was included."
- A single calibrated confidence computation reused consistently as both the pre-generation gate and the post-generation Reliability Score, avoiding score-proliferation and the credibility problem of unexplained parallel metrics.
- Knowledge Health monitoring that reuses the platform's own conflict/freshness detection rather than shipping a second, disconnected corpus-quality tool.
- A built-in, repeatable evaluation methodology (golden set, baseline-vs-self-corrected comparison) rather than an assumed or anecdotal reliability claim.

---

## 36. Why This Project Is Different

Veritas RAG is infrastructure, not an application — it is designed to sit in front of an existing retriever and LLM rather than replace them, and its entire value proposition is the decision layer between retrieval and generation that most RAG systems do not have at all. It does not compete on answer quality or conversational polish; it competes on making the difference between "the system answered" and "the system should have answered" visible, measurable, and enforced.

---

## 37. Innovation Highlights

1. Failure-reason-specific query rewriting, rather than a single generic "try again" strategy.
2. A bounded, monotonicity-checked self-correction loop with explicit, sole decision authority in one module — eliminating the "who is actually in charge of the retry" ambiguity common to ad hoc self-correction implementations.
3. Claim-level entailment verification of citations, rejecting answers post-generation even when pre-generation confidence was high.
4. A single reused calibrated scoring model presented as both an internal confidence gate and an externally-visible, decomposed Reliability Score.
5. Knowledge Health monitoring that is explicitly a reuse of existing conflict/freshness detection, not a second system — proactive rather than only reactive reliability.
6. A built-in baseline-vs-self-corrected evaluation methodology designed to directly answer the official problem statement's measurement requirement.

---

## 38. Technical KPIs

- p95 end-to-end latency for first-pass resolution (target defined per deployment environment; reported, not assumed)
- Retry success rate (fraction of retries that cross the confidence threshold)
- Citation verification pass rate
- Conflict detection precision/recall against the golden set's seeded-conflict cases
- Reranker and NLI-stage queue depth / throughput under load
- Confidence calibration drift over time (agreement between predicted confidence and human-labeled outcome, tracked on a rolling basis)

---

## 39. Business KPIs

- Reduction in hallucination-driven support escalations for applications built on Veritas RAG
- Reduction in time-to-resolution for compliance/audit reviews of AI-generated answers, enabled by the Reliability Score breakdown
- Adoption ease, measured as integration time for a team placing Veritas RAG in front of an existing retriever
- Clarification rate trending toward an acceptable balance point per tenant (neither over-triggering nor under-triggering)

---

## 40. Evaluation Dataset Definition *(new in v1.1)*

| Dataset | Purpose | Construction Method | Used By |
|---|---|---|---|
| **Benchmark Dataset** | Measures baseline retrieval and generation quality independent of self-correction-specific scenarios | Standard QA pairs representative of typical, well-covered queries against the target corpus | Retrieval Precision/Recall, baseline Hallucination Rate comparison |
| **Conflict Dataset** | Specifically tests Conflict Detection and clarification quality | Deliberately seeded pairs/sets of contradictory documents (e.g., superseded vs. current policy versions), with labeled correct resolution (which source should win, or that clarification is the correct behavior) | Conflict Detection Precision/Recall, Clarification Precision |
| **Golden Dataset** | The primary evaluation asset for the core PS-1 claim | Curated, human-labeled set combining standard, insufficient-context, conflicting-context, and stale-context cases, per FR-EVAL-1 | AC-5 (baseline-vs-self-corrected hallucination comparison), Groundedness, Citation Accuracy |
| **Ground Truth** | The correctness reference against which all automated scoring is checked | For each Golden Dataset item: the correct answer (or the correct "insufficient/clarify/refuse" label), the correct supporting document ID(s), and, for conflict cases, the correct resolution | Automated scorer validation, human-annotation cross-check |
| **Evaluation Corpus** | The underlying, version-pinned document set retrieval operates against during evaluation | Kept separate and versioned independently from any live/demo corpus so evaluation results remain reproducible across pipeline changes | All evaluation metrics; required for the Evaluation module's CI-style re-runs (BR-7) |

---

## 41. Evaluation Metrics

| Metric | Definition |
|---|---|
| **Hallucination Rate** | Fraction of generated claims unsupported by cited evidence, measured on the golden set via automated entailment checking, cross-validated against human annotation on a sample |
| **Groundedness** | Fraction of answer sentences with at least one citation whose entailment score exceeds a validated threshold |
| **Faithfulness** | Whether the answer contradicts the retrieved context, even where not directly cited — a check distinct from groundedness |
| **Citation Accuracy** | Precision (citations that genuinely support their claim) and recall (claims that should carry a citation and do) |
| **Latency** | End-to-end and per-stage timing, tracked separately for first-pass, retried, and clarified resolutions |
| **Cost** | Token and compute cost per resolved query, per clarified query, and per escalated query, tracked separately |
| **Reliability** | The decomposed 0–100 Reliability Score and its correlation with human judgment on a sampled evaluation |
| **Confidence** | The pre-generation calibrated score and its distribution across resolved, retried, and clarified queries |
| **Coverage** | Fraction of query sub-questions/entities addressed by retrieved evidence |
| **Retry Success Rate** | Fraction of retries that achieved the minimum required confidence improvement |

---

## 42. Glossary

- **Confidence Score** — the pre-generation, calibrated aggregation of retrieval-reliability signals that gates whether generation is permitted to proceed.
- **Reliability Score** — the same calibrated computation, re-scored with post-generation signals and presented to users/operators with a full breakdown.
- **Groundedness** — the degree to which generated claims are supported by their cited evidence.
- **Faithfulness** — the absence of contradiction between the generated answer and the retrieved context as a whole.
- **Coverage** — the extent to which retrieved evidence addresses every sub-question or entity present in the query.
- **Conflict Detection** — the process of identifying contradictory claims across retrieved documents.
- **Self-Correction Loop** — the bounded retry/rewrite/clarify decision process governing query resolution.
- **Golden Set / Golden Dataset** — the labeled evaluation dataset used to measure hallucination rate and related metrics before and after self-correction.
- **Ground Truth** — the correctness reference (correct answer, correct source, or correct refusal/clarification label) against which the Golden Dataset is scored.
- **Evaluation Corpus** — the version-pinned document set used during evaluation runs, kept independent of any live/demo corpus for reproducibility.
- **Knowledge Health** — proactive, corpus-level monitoring for duplication, staleness, and conflict, independent of individual user queries.

---

## 43. References

This document consolidates and formalizes the architecture, feature scope, and naming decisions established during the project's design review process for OneInbox AI Internship Hackathon 2026, Problem Statement 1 (Self-Correcting RAG Pipeline, AI Engineer track). It supersedes prior informal architecture drafts, and this v1.1 revision supersedes v1.0 by addition only. It is intended as the single source of truth for subsequent HLD, LLD, agent design, database design, API design, and implementation work.

---

*End of Product Requirements Document — Version 1.1.*
