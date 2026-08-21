# Veritas RAG — Phase 2 Milestone 1: Chunking & Document Processing Foundation Architecture Plan

**Date**: 2026-07-19
**Status**: Proposed — Awaiting User Sign-Off (Phase 2 Milestone 1 Step 4 & 5)
**Author**: Principal AI & System Architect

---

## 1. Context & Architectural Alignment

Following the successful completion and freeze of all Phase 1 Foundation Milestones (M1–M6), **Phase 2 (`Knowledge Layer & Retrieval Foundation`)** establishes the intelligent ingestion, embedding, vector storage, and hybrid retrieval stack.

**Milestone 1 (`Chunking & Document Processing Foundation`)** is the mandatory first step of Phase 2. Its sole objective is to transform normalized document text (`text.txt` generated during Phase 1 M6) into clean, highly structured, doubly-linked, and validated `DocumentChunk` entities using specialized, content-aware splitting strategies.

### Strict Boundary Invariants (NO Leakage)
- 🚫 **Strictly NO Embeddings**: No embedding API calls (`OpenAI`, `Gemini`, `FastEmbed`) or embedding vector columns/generation in Milestone 1.
- 🚫 **Strictly NO Vector DB Operations**: No writes or reads to `Qdrant` in Milestone 1.
- 🚫 **Strictly NO Retrieval or LLM Generation**: No search pipelines or LLM answering in Milestone 1.

---

## 2. Domain Oriented Module Layering (`ADR-005`)

All capabilities will reside cleanly within `backend/modules/chunking/`, adhering to the modular architecture contract:

```
backend/modules/chunking/
    __init__.py
    models/
        __init__.py
        chunk.py              # DocumentChunk & ChunkRelationship entity models
    schemas/
        __init__.py
        chunk.py              # DTOs: ChunkDTO, ChunkCreateRequest, ChunkResponse, ChunkListResponse, StrategyInfoDTO
        errors.py             # Domain exception hierarchy & error code taxonomy (CHK_xxx)
    strategies/
        __init__.py
        base.py               # Abstract BaseChunkSplitter interface
        recursive.py          # RecursiveChunkSplitter
        markdown.py           # MarkdownChunkSplitter (header hierarchy ATX # aware)
        sentence.py           # SentenceChunkSplitter (NLP boundary preserving)
        paragraph.py          # ParagraphChunkSplitter (double newline block aware)
        table.py              # TableChunkSplitter (header preservation per row/group)
        code.py               # CodeChunkSplitter (AST/syntax definition respecting)
        semantic.py           # SemanticChunkSplitterPlaceholder (clean stub raising Phase 2 M2 requirement)
        factory.py            # SplitterStrategyFactory (automatic MIME routing + override)
    services/
        __init__.py
        chunk_service.py      # ChunkingService orchestration & lifecycle logic
    validators/
        __init__.py
        validator.py          # ChunkValidator (size, hash uniqueness, empty check)
        contract.py           # ChunkProcessingContract invariant enforcement
    events/
        __init__.py
        payloads.py           # Versioned domain event payloads (schema_version: "1.0.0")
    repositories/
        __init__.py
        chunk_repository.py   # DocumentChunkRepository with async SQLAlchemy queries
    api/
        __init__.py
        routes.py             # FastAPI endpoints mounted at /api/v1/chunks
    workers/
        __init__.py
        tasks.py              # Celery async chunking pipeline worker with backoff retry
```

---

## 3. Detailed Component & Entity Design

### 3.1 Database Entity Models (`backend/modules/chunking/models/chunk.py`)

#### `DocumentChunk` (`document_chunks` table)
- **`id`**: `UUID` primary key.
- **`tenant_id`**: `String(255)` (indexed for strict multi-tenant isolation).
- **`document_id`**: `UUID` foreign key -> `documents.id` (`ondelete="CASCADE"`).
- **`document_version_id`**: `UUID` foreign key -> `document_versions.id` (`ondelete="CASCADE"`).
- **`chunk_index`**: `Integer` (0-indexed sequence order within the document version).
- **`content`**: `Text` (NFC UTF-8 cleaned chunk body).
- **`content_hash`**: `String(64)` (SHA-256 of normalized text + critical metadata for deduplication).
- **`strategy_used`**: `String(50)` (`recursive`, `markdown`, `sentence`, `paragraph`, `table`, `code`).
- **`token_count`**: `Integer` (estimated token count using standard heuristics/tiktoken ratio).
- **`character_count`**: `Integer` (exact character length).
- **`parent_chunk_id`**: `UUID` nullable foreign key -> `document_chunks.id` (hierarchical parent).
- **`previous_chunk_id`**: `UUID` nullable foreign key -> `document_chunks.id` (doubly-linked prev link).
- **`next_chunk_id`**: `UUID` nullable foreign key -> `document_chunks.id` (doubly-linked next link).
- **`page_numbers`**: `JSONB` list of integer pages `[1, 2]`.
- **`section_path`**: `JSONB` heading breadcrumbs `["# Architecture", "## Database"]`.
- **`metadata_json`**: `JSONB` (custom tags, table column headers, code language, bounding box data).
- **`is_embedded`**: `Boolean` (defaults `False` — reserved for Milestone 2).
- **`created_at` / `updated_at`**: Inherited from `BaseModel`.

Composite Indexes:
- `ix_document_chunks_tenant_doc_ver_idx` on `(tenant_id, document_id, document_version_id, chunk_index)`
- `ix_document_chunks_tenant_hash` on `(tenant_id, content_hash)`

#### `ChunkRelationship` (`chunk_relationships` table)
- Self-referential graph junction model enabling hierarchical parent-child, table cell grouping, and cross-reference links across chunks:
  - `source_chunk_id`: `UUID` FK -> `document_chunks.id`
  - `target_chunk_id`: `UUID` FK -> `document_chunks.id`
  - `relationship_type`: `String(50)` (`parent_child`, `sequential`, `table_cell`, `cross_ref`)

---

### 3.2 Splitting Strategies (`backend/modules/chunking/strategies/`)

Every strategy implements `BaseChunkSplitter.split(text: str, metadata: dict, max_characters: int, overlap: int) -> list[ChunkDTO]` while preserving semantic context:

1. **`RecursiveChunkSplitter`**: Configurable separator hierarchy `["\n\n", "\n", ". ", " ", ""]` ensuring splits occur at the highest possible semantic boundary before descending to character breaks.
2. **`MarkdownChunkSplitter`**: Tracks markdown header levels (`#`, `##`, `###`) to assign `section_path` metadata to each child chunk. Never splits inside markdown code fences or tables.
3. **`SentenceChunkSplitter`**: Regex/NLP boundary detection combining full sentences up to `max_characters` without severing sentences halfway.
4. **`ParagraphChunkSplitter`**: Splits cleanly on double newline blocks (`\n\n`), merging short paragraphs or separating large blocks.
5. **`TableChunkSplitter`**: Parses Markdown/CSV tables. Extracts the header row (`<th>`) and prefixes every chunked row or group of rows with the column headers so downstream retrieval maintains exact schema context.
6. **`CodeChunkSplitter`**: Detects programming language (`python`, `typescript`, `go`, `sql`, `json`) and splits along class/function/block definitions.
7. **`SemanticChunkSplitterPlaceholder`**: Explicit architectural placeholder that throws `SemanticChunkingNotReadyException` pointing out that semantic similarity splitting requires the Embedding Pipeline (Phase 2 M2).
8. **`SplitterStrategyFactory`**: Automatic resolution engine mapping MIME types (`text/markdown`, `application/pdf`, `text/csv`, `application/x-python`) to the optimal strategy.

---

### 3.3 Domain Exceptions & Taxonomy (`backend/modules/chunking/schemas/errors.py`)

All errors extend `RAGuardException` and map to `ErrorSeverity` (`RECOVERABLE` vs `FATAL`):
- `CHK_001` (`ChunkValidationError`): Chunk exceeds maximum size or fails content checks (`FATAL`, HTTP 400).
- `CHK_002` (`ChunkStrategyNotFound`): Requested strategy ID unsupported (`FATAL`, HTTP 400).
- `CHK_003` (`ChunkingExecutionError`): Unexpected failure during text splitting (`FATAL`, HTTP 500).
- `CHK_004` (`ChunkContractViolationError`): Chunking invariant check failed (`RECOVERABLE`, HTTP 500).
- `CHK_005` (`ChunkNotFoundException`): Chunk ID not found in database (`RECOVERABLE`, HTTP 404).

---

### 3.4 Event Payloads (`backend/modules/chunking/events/payloads.py`)

All domain events enforce `schema_version: "1.0.0"`:
- `EVENT_DOCUMENT_CHUNKED = "DocumentChunked"`:
  ```json
  {
    "schema_version": "1.0.0",
    "event_type": "DocumentChunked",
    "tenant_id": "tenant-acme",
    "document_id": "uuid",
    "document_version_id": "uuid",
    "data": {
      "chunk_count": 42,
      "strategy_used": "markdown",
      "total_tokens": 12400,
      "processing_duration_ms": 184.2
    }
  }
  ```
- `EVENT_CHUNKING_FAILED = "ChunkingFailed"`

---

### 3.5 Celery Async Worker (`backend/modules/chunking/workers/tasks.py`)

- **`process_document_chunking_task(tenant_id, document_id, version_id, strategy_override, max_chars, overlap)`**:
  - Celery background worker with automatic retry (`max_retries=3`, exponential backoff) for transient database errors.
  - Automatically transitions document status from `PROCESSED` -> `CHUNKING` -> `CHUNKED` (or `CHUNKING_FAILED`).
  - Hooks directly into existing `DocumentEventLog` and emits domain events.

---

### 3.6 API Router (`backend/modules/chunking/api/routes.py`)

Mounted at `/api/v1/chunks`:
- `GET /api/v1/chunks/strategies`: Returns all registered strategies with supported MIME types and parameters.
- `POST /api/v1/chunks/process/{document_id}`: Triggers synchronous or asynchronous chunking for a document.
- `GET /api/v1/chunks/document/{document_id}`: Paginated chunk list filtered by `document_version_id` or `strategy_used`, returning `previous_chunk_id`, `next_chunk_id`, and `section_path`.
- `GET /api/v1/chunks/{chunk_id}`: Single chunk detail view with full metadata and relationship graph.
- `DELETE /api/v1/chunks/document/{document_id}`: Deletes all chunks for a document or specific version.

---

## 4. Frontend Infrastructure UI (`frontend/src/pages/chunks/`)

A premium, enterprise-grade React 18 UI utilizing our Design System, Framer Motion transitions, and Lucide icons:
1. **`ChunksPage.tsx`**: Route `/chunks` with PageHeader, stats overview, and document selector.
2. **`ChunkStrategySelector.tsx`**: Interactive card-based selector allowing users to choose splitting algorithms (`Recursive`, `Markdown`, `Sentence`, `Paragraph`, `Table`, `Code`) with slider controls for `Max Characters` (200–5000) and `Overlap Characters` (0–500).
3. **`ChunkListTable.tsx`**: Table displaying chunk sequence index, character/token gauges, strategy badges, heading section breadcrumbs (`# Chapter 1 > ## Section A`), and relationship indicator icons.
4. **`ChunkDetailDrawer.tsx`**: Side drawer for deep-dive inspection of chunk content, doubly-linked neighbor buttons (`Next Chunk ->`, `<- Previous Chunk`), and raw metadata JSON.
5. **`ChunkMetricsCard.tsx`**: KPI cards displaying Total Chunks, Average Token Density, Strategy Breakdown chart, and Validation pass rates.

---

## 5. Verification & Quality Plan

1. **Unit Tests (`tests/unit/backend/modules/chunking/`)**:
   - Test every splitter (`Recursive`, `Markdown`, `Sentence`, `Paragraph`, `Table`, `Code`) against edge cases (empty strings, huge tables, nested code blocks, Unicode emojis).
   - Test doubly-linked sequential chain creation (`prev_chunk_id` <-> `next_chunk_id`).
   - Test `StrategyFactory` MIME resolution and `ChunkProcessingContract.verify()`.
   - Test `ChunkValidator` size quotas and hash uniqueness check.
2. **API & Repository Tests**:
   - Verify all endpoints under `/api/v1/chunks` via FastAPI `TestClient` and `pytest-asyncio`.
3. **Regression Check**:
   - Verify `python -m pytest tests/unit -v` runs all existing 140+ unit tests with zero regression across Milestones 1–6.
4. **Frontend Typecheck**:
   - Verify `npx tsc --noEmit` cleanly compiles all new UI components.

---

## 6. Implementation Checklist & Next Steps

Upon your approval (`STEP 5`), we will immediately execute `STEP 6 — Implement iteratively` in the exact sequence outlined above:
1. Create database entities & Alembic migration.
2. Build strategies (`base`, `recursive`, `markdown`, `sentence`, `paragraph`, `table`, `code`, `semantic stub`, `factory`).
3. Build `ChunkValidator`, `ChunkProcessingContract`, and domain error hierarchy.
4. Build `ChunkingService` and repository layer.
5. Build Celery worker task and versioned domain events.
6. Build FastAPI endpoints & mount on `/api/v1/router.py`.
7. Build `frontend/src/pages/chunks/` UI and route integration.
8. Execute verification tests & documentation freeze.
