# Product Requirements Document (PRD): Veritas RAG

## 1. Executive Summary
Veritas RAG is an enterprise-grade AI reliability platform designed to sit between retrieval and generation in Retrieval-Augmented Generation (RAG) systems. Unlike standard RAG wrappers, Veritas RAG acts as a reliability gatekeeper, ensuring that LLM generation only occurs when evidence is sufficient, grounded, and non-contradictory. It features a deterministic self-correction loop that rewrites queries, seeks clarification, or returns transparent low-confidence responses to eliminate silent hallucinations.

## 2. Problem Statement
Enterprise RAG systems often struggle with "messy" unstructured data (PDFs, OCR errors, inconsistent formatting), leading to:
*   **Silent Hallucinations:** LLMs generating confident but incorrect answers based on poor context.
*   **Contextual Failure:** Inability to detect when retrieved information is insufficient or contradictory.
*   **Lack of Transparency:** No measurable "trust" metric for end-users to evaluate AI output.
*   **Infinite Loops/Unpredictability:** Agentic systems that loop indefinitely or behave non-deterministically in production.

## 3. Goals & Objectives
*   **Zero Silent Hallucinations:** Ensure every response is either fully grounded, explicitly flagged as low-confidence, or replaced by a clarification request.
*   **Measurable Trust:** Provide a calibrated 0-100 Reliability Score for every interaction.
*   **Deterministic Self-Correction:** Implement a rule-based control loop to fix retrieval failures without unpredictable agentic behavior.
*   **Enterprise Hardening:** Deliver a production-ready system with integrated security, observability, and compliance controls.

## 4. Target Users / Stakeholders
*   **Enterprise AI Engineers:** Requiring a reliability layer for production RAG deployments.
*   **Compliance & Risk Officers:** Needing audit trails and hallucination metrics.
*   **End-Users:** Requiring high-integrity information from complex enterprise document corpora.

## 5. Functional Requirements

### 5.1 Query & Ingestion Intelligence (FR-1)
*   **Normalization:** Normalize messy/OCR-derived text during ingestion and query time.
*   **Intent Detection:** Extract entities and detect user intent to guide retrieval.
*   **Ambiguity Detection:** Identify queries that require user clarification before proceeding.
*   **Validation:** Use Pydantic v2 for strict request hardening and secure file upload validation.

### 5.2 Hybrid Retrieval (FR-2)
*   **Multi-Stage Search:** Execute dense (vector) and sparse (keyword) search.
*   **Fusion & Reranking:** Use Reciprocal Rank Fusion (RRF) and Cross-Encoder reranking to prioritize context.
*   **Deduplication:** Remove redundant snippets to optimize context window usage.

### 5.3 Retrieval Reliability (FR-3)
*   **Coverage Analysis:** Measure if the retrieved context actually addresses the query components.
*   **Conflict Detection:** Identify contradictory information within the retrieved set.
*   **Confidence Engine:** Aggregate coverage, evidence strength, freshness, and conflict into a pre-generation score.

### 5.4 Self-Correction & Control (FR-4)
*   **Retry Controller:** Act as the **sole decision authority** for retries, rewrites, and escalations.
*   **Bounded Loops:** Enforce a hard limit of **max 2 automatic retries** with a monotonic-improvement check.
*   **Query Rewrite:** Implement failure-specific strategies (Decomposition, HyDE, Disambiguation).
*   **Clarification:** Generate targeted questions for the user when ambiguity is detected.

### 5.5 Generation & Validation (FR-5)
*   **Grounded Generation:** Generate answers strictly from approved, high-confidence context with mandatory citations.
*   **Reflection Engine:** Perform post-generation judgment to ensure the answer aligns with the context.
*   **Answer Validation:** Extract claims and verify citation entailment using NLI models.
*   **Low-Confidence Path:** Return a response with a full Reliability Score breakdown if the retry budget is exhausted.

### 5.6 Knowledge Health & Evaluation (FR-6)
*   **Proactive Scanning:** Reuse Conflict Detection and Freshness logic to scan the corpus for duplicates and staleness.
*   **Evaluation Engine:** Maintain golden datasets and run baseline-vs-self-corrected comparisons to measure hallucination reduction.

## 6. Non-Functional Requirements
*   **Performance:** Latency tracking for every pipeline stage; use of Redis for session and inference caching.
*   **Scalability:** Horizontal scaling for Query Intelligence, Retrieval, and Validation services.
*   **Reliability:** Fault isolation via microservice boundaries; deterministic logic in the Retry Controller.
*   **Observability:** Full OpenTelemetry integration with distributed tracing and correlation IDs.

## 7. System Architecture Overview
The system is organized into four logical layers:
1.  **Ingress & Edge Layer:** Handles secure entry, authentication, and session management.
2.  **Core Reliability Services:** The "Brain" containing the Retry Controller, Confidence Engine, and Validation logic.
3.  **Governance & Evaluation Layer:** Manages long-term system health, benchmarking, and analytics.
4.  **Data Persistence Layer:** Encrypted storage for vectors, relational metadata, and cache.

## 8. Tech Stack
*   **Backend Framework:** Python, FastAPI.
*   **AI/ML Models:** OpenAI GPT-4o (Generation), GPT-4o-mini (Rewriting/Reflection), HuggingFace NLI (Validation), Sentence-Transformers (Embeddings/Reranking).
*   **Databases:** Qdrant (Vector), PostgreSQL (Relational/Audit), Redis (Cache).
*   **Security & Infrastructure:** Kong (Gateway), TLS 1.3, AES-256, Pydantic v2, OpenTelemetry.
*   **Frontend:** ReactJS, TypeScript, Grafana (Dashboard).

## 9. Data Requirements
*   **Vector Store (Qdrant):** Stores document embeddings with metadata filtering for tenant isolation.
*   **Relational DB (Postgres):** Stores audit logs of every retry/decision, golden datasets, and compliance metadata.
*   **Cache (Redis):** Stores session state for the Retry Controller and model inference results to reduce latency.
*   **Encryption:** All data at rest must use AES-256; all data in transit must use TLS 1.3.

## 10. API Specifications
*   **POST /v1/query:** Primary endpoint for user queries; returns answer + Reliability Score.
*   **POST /v1/ingest:** Secure endpoint for document ingestion and normalization.
*   **GET /v1/health/knowledge:** Returns corpus-level conflict and freshness metrics.
*   **GET /v1/eval/metrics:** Streams hallucination and groundedness metrics to the dashboard.

## 11. Security Requirements
*   **Transport Security:** Mandatory TLS 1.3 for all external and mTLS for internal communications.
*   **Application Security:** OWASP API Security Controls; Prompt Injection Shield on generation services.
*   **Validation:** Strict Pydantic v2 schema enforcement for all inputs.
*   **Secret Management:** Externalized secret management (e.g., Vault) for API keys and DB credentials.

## 12. Deployment & Infrastructure
*   **Containerization:** All modules deployed as independent Docker containers.
*   **Orchestration:** Kubernetes-ready with defined resource limits and horizontal pod autoscaling.
*   **CI/CD:** Automated testing for NLI entailment and retrieval coverage during deployment.

## 13. Success Metrics
*   **Hallucination Rate Reduction:** % decrease in unsupported claims compared to baseline RAG.
*   **Groundedness Score:** Average NLI entailment score across all generated claims.
*   **Retry Success Rate:** % of low-confidence retrievals successfully "fixed" by the Query Rewrite service.
*   **Reliability Calibration:** Correlation between the Reliability Score and actual answer accuracy.

## 14. Timeline & Milestones
*   **Phase 1 (MVP):** Core Retrieval and Generation with basic Answer Validation.
*   **Phase 2 (Reliability):** Integration of the Retry Controller, Confidence Engine, and Query Rewrite.
*   **Phase 3 (Hardening):** Implementation of TLS 1.3, AES-256, OpenTelemetry, and Knowledge Health scanning.
*   **Phase 4 (Analytics):** Deployment of the Evaluation Engine and Analytics Dashboard.

## 15. Open Questions & Risks
*   **Latency Trade-off:** The multi-stage validation and retry loop increases time-to-first-token; requires aggressive caching.
*   **Calibration Complexity:** Ensuring the Confidence Score is accurately calibrated across diverse document types.
*   **OCR Limitations:** Extremely poor quality OCR may still bypass normalization, requiring manual intervention flags.

---
**End of PRD**
