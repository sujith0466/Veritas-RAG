# Audit Log WORM Architecture & Immutability Specification

**Epic**: Epic 15 — Production Hardening & Enterprise Security
**Component**: Audit Trail & Compliance Subsystem (F15.7 WORM Archival & Tamper Detection)
**Classification**: High-Integrity Security Architecture
**Status**: ACTIVE / HARDENED

---

## 1. Overview & WORM Guarantee

Veritas RAG enforces a **Write-Once, Read-Many (WORM)** append-only paradigm for all security, authentication, and tenant audit events.

Under this architecture:
- **Append-Only Creation**: Audit records can only be created (`INSERT`).
- **No In-Place Mutation**: No API, service, repository, or ORM layer provides `update` capabilities on audit records.
- **No Soft-Deletion**: Audit records cannot be marked as deleted (`is_deleted` column has been dropped from the schema).
- **No Hard-Deletion**: No API or repository method exposes `delete` or `hard_delete` on audit records.
- **Tenant Isolation**: Workspace audit records are strictly scoped by `tenant_id`. Cross-tenant queries are blocked server-side by RBAC dependencies.

---

## 2. ORM & Repository Architecture

### 2.1 Model Hierarchy (`backend/models/base.py` & `backend/models/entities/audit_log.py`)

To prevent accidental inheritance of mutable attributes, the ORM hierarchy provides two distinct base classes:

1. **`BaseModel`**: Used by standard entities requiring mutable lifecycle tracking (`id`, `created_at`, `updated_at`, `is_deleted`).
2. **`ImmutableBaseModel`**: Used exclusively by append-only WORM entities (such as `AuditLog`).
   - Fields: `id` (`UUID`), `created_at` (`DateTime(timezone=True)`).
   - **Omitted Fields**: `updated_at` (no mutation), `is_deleted` (no deletion).

```python
class ImmutableBaseModel(Base):
    """Abstract base class for append-only / immutable ORM entities."""
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
```

### 2.2 Repository Hierarchy (`backend/repositories/base.py` & `backend/repositories/implementations/audit_log_repository.py`)

The repository layer mirrors this architectural separation:

- **`BaseRepository[ModelType]`**: Provides `create`, `get_by_id`, `get_all`, `update`, `soft_delete`, `hard_delete`.
- **`ImmutableBaseRepository[ImmutableModelType]`**: Provides **ONLY** `create`, `get_by_id`, `get_all`. It explicitly does **NOT** implement `update`, `soft_delete`, or `hard_delete`.

```python
class ImmutableBaseRepository(Generic[ImmutableModelType]):
    """Generic async repository for append-only / immutable ORM entities (WORM compliant)."""

    def __init__(self, session: AsyncSession, model_class: type[ImmutableModelType]) -> None:
        self.session = session
        self.model_class = model_class

    async def get_by_id(self, entity_id: uuid.UUID) -> ImmutableModelType | None: ...
    async def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[ImmutableModelType]: ...
    async def create(self, **kwargs: Any) -> ImmutableModelType: ...
```

`AuditLogRepository` inherits directly from `ImmutableBaseRepository[AuditLog]`.

---

## 3. Database Schema & Migration

### Schema Definition (`audit_logs`)

| Column | Type | Nullable | Description |
|:---|:---|:---|:---|
| `id` | `UUID` | No | Primary Key |
| `tenant_id` | `UUID` | Yes | Scoped Workspace ID (Indexed) |
| `action` | `VARCHAR(100)` | No | Audit event identifier (Indexed) |
| `user_id` | `UUID` | Yes | Actor UUID (Indexed) |
| `resource_type`| `VARCHAR(100)` | Yes | Resource category |
| `resource_id` | `VARCHAR(255)` | Yes | Target resource identifier |
| `details` | `JSON` | Yes | Structured contextual metadata |
| `status` | `VARCHAR(50)` | No | Execution status (`success`, `failure`, etc.) |
| `created_at` | `TIMESTAMPTZ` | No | Timestamp of log event creation |

### Migration Details (`20260821_epic15_audit_log_worm.py`)

- **Revision**: `e15a0d179001`
- **Revises**: `f1302e18ea08`
- **Action**: Drops `is_deleted` and `updated_at` columns from `audit_logs`.
- **Downgrade**: Full reversible downgrade restoring columns with safe defaults if necessary.

---

## 4. API Endpoints & Authorization

1. **`GET /api/v1/audit-logs`**:
   - Authorized roles: `ADMIN`, `OWNER`, `PLATFORM_ADMIN`.
   - Server-side scope: Filtered by `auth.tenant_id`.
   - Ordering: `created_at DESC`.

2. **`GET /security/v1/audit/{tenant_id}`**:
   - Authorized roles: `PLATFORM_ADMIN` (strictly enforced server-side).
   - Scope: Platform administrative compliance auditing.

---

## 5. Cryptographic Archival & Tamper Detection Lifecycle (F15.7)

### 5.1 Canonical Serialization
To guarantee that cryptographic hashes are independent of memory formatting, whitespace, or dict key ordering, every `AuditLog` row is converted to a deterministic pipe-delimited payload:
$$\text{Payload} = \text{id} \parallel \text{created\_at} \parallel \text{tenant\_id} \parallel \text{action} \parallel \text{user\_id} \parallel \text{resource\_type} \parallel \text{resource\_id} \parallel \text{details\_json} \parallel \text{status}$$
where `details_json` is serialized with sorted keys and zero extraneous whitespace: `json.dumps(details, sort_keys=True, separators=(',', ':'))`.

### 5.2 SHA-256 Chained Hash & Manifest Root
Archives utilize a cryptographic blockchain-style hash chain (`SHA256-CHAIN-v1`):
$$H_0 = \text{0000000000000000000000000000000000000000000000000000000000000000}$$
$$H_i = \text{SHA256}(H_{i-1} \parallel \text{SHA256}(\text{CanonicalRecord}_i))$$
$$\text{Manifest Root Hash} = H_n$$

The resulting archive package consists of:
1. `audit_archive_{tenant_id}_{period}.json`: array of serialized records with per-record hashes.
2. `audit_archive_{tenant_id}_{period}.manifest.json`: manifest containing `archive_id`, `tenant_id`, `period_start`, `period_end`, `record_count`, `algorithm`, `root_hash`, and `created_at`.

### 5.3 Deterministic Verification & Tamper Detection
When `AuditLogArchivalService.verify_archive_integrity(records, manifest)` executes:
1. It confirms `len(records) == manifest.record_count`.
2. It independently recomputes the SHA-256 hash of each record. If any field was modified, it detects the exact index ($i$).
3. It recalculates the hash chain $H_0 \to H_n$. If any record was injected, omitted, or reordered, $H_n \neq \text{manifest.root\_hash}$ and verification fails.

---

## 6. Immutability & Storage Tier Classification

| Immutability Layer | Mechanism | Current Status |
|:---|:---|:---:|
| **Application Layer** | `ImmutableBaseModel` + `ImmutableBaseRepository` | ✅ IMPLEMENTED & TESTED |
| **Database Layer** | PostgreSQL schema without `is_deleted` or `updated_at` | ✅ MIGRATION READY |
| **Archival Layer** | Cryptographic SHA-256 chained hashing & tamper detection | ✅ IMPLEMENTED & TESTED |
| **Object Storage WORM** | S3 / MinIO Object Lock (Compliance Mode / Legal Hold) | ⏳ Staging/Cloud Infra Required |

---

## 7. Verification & Automated Test Coverage

- **Repository WORM Tests** ([`backend/tests/unit/repositories/test_audit_log_worm.py`](file:///d:/Veritas RAG/backend/tests/unit/repositories/test_audit_log_worm.py)):
  - Validates `AuditLog` inheritance, missing deletion/mutation attributes, and SQL generator omission of `is_deleted`.
- **Archival & Tamper Detection Tests** ([`backend/tests/unit/services/test_audit_log_archival.py`](file:///d:/Veritas RAG/backend/tests/unit/services/test_audit_log_archival.py)):
  - Validates pristine archive verification, payload tampering detection, record deletion/injection detection, reordering detection, forged root hash rejection, and tenant boundary protection.
