"""Document Pipeline Reconciliation Engine (`DocumentReconciliationService`).

Performs deterministic, non-mutating (dry-run first) audits across Document aggregate roots,
ProcessingJobs, StorageObjects, DocumentChunks, ChunkEmbeddings, VectorIndexMetadata, and Qdrant.
Classifies records into actionable categories (Class A, Class B, Class C, Healthy Ready, Parity Drift).
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.document.models.document import Document, DocumentVersion
from backend.document.models.job import ProcessingJob
from backend.document.models.status import DocumentStatus
from backend.document.storage.preflight import StoragePreflightValidator
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.vector.models.vector_metadata import VectorIndexMetadata

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ReconciliationItem:
    """Detailed forensic classification of a single tenant document record."""

    document_id: str
    title: str
    status: str
    classification: str
    storage_valid: bool
    storage_anomaly: str | None
    chunk_count: int
    embedding_count: int
    vector_count: int
    job_status: str | None
    dispatch_state: str | None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReconciliationReport:
    """Tenant-scoped reconciliation audit findings."""

    tenant_id: str
    dry_run: bool
    scanned_at: str
    total_documents: int = 0
    healthy_count: int = 0
    class_a_count: int = 0  # Stranded with intact physical file
    class_b_count: int = 0  # Stranded with missing storage file
    class_c_count: int = 0  # Terminal processing failure
    other_discrepancy_count: int = 0
    items: list[ReconciliationItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize machine-readable report."""
        return {
            "tenant_id": self.tenant_id,
            "dry_run": self.dry_run,
            "scanned_at": self.scanned_at,
            "total_documents": self.total_documents,
            "summary": {
                "healthy_ready": self.healthy_count,
                "class_a_intact_storage": self.class_a_count,
                "class_b_missing_storage": self.class_b_count,
                "class_c_failed": self.class_c_count,
                "other_discrepancies": self.other_discrepancy_count,
            },
            "items": [asdict(item) for item in self.items],
        }

    def to_markdown(self) -> str:
        """Format human-readable audit report."""
        lines = [
            f"# Document Pipeline Reconciliation Report",
            f"- **Tenant ID:** `{self.tenant_id}`",
            f"- **Mode:** `{'DRY RUN (READ ONLY)' if self.dry_run else 'EXECUTED'}`",
            f"- **Scanned At:** `{self.scanned_at}`",
            f"- **Total Documents Scanned:** `{self.total_documents}`",
            "",
            "## Summary Breakdown",
            f"- **Healthy & Ready:** {self.healthy_count}",
            f"- **Class A (Stranded with Intact Storage):** {self.class_a_count}",
            f"- **Class B (Stranded with Missing Storage):** {self.class_b_count}",
            f"- **Class C (Failed with Diagnostics):** {self.class_c_count}",
            f"- **Other Discrepancies:** {self.other_discrepancy_count}",
            "",
            "## Forensic Item Breakdown",
            "| Document ID | Title | Status | Classification | Chunks | Vectors | Storage Valid | Anomaly |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for it in self.items[:100]:  # Limit markdown table to first 100 items
            lines.append(
                f"| `{it.document_id[:8]}...` | {it.title[:25]} | `{it.status}` | **{it.classification}** | {it.chunk_count} | {it.vector_count} | {it.storage_valid} | {it.storage_anomaly or 'None'} |"
            )
        if len(self.items) > 100:
            lines.append(f"\n*(Showing 100 of {len(self.items)} items)*")
        return "\n".join(lines)


class DocumentReconciliationService:
    """Read-only dry-run auditor and classifier for the document ingestion pipeline."""

    @classmethod
    async def scan_tenant(
        cls,
        tenant_id: str,
        session: AsyncSession,
        dry_run: bool = True,
        limit: int = 500,
    ) -> ReconciliationReport:
        """Scan and classify all documents in a tenant namespace.
        
        Args:
            tenant_id: Tenant UUID string.
            session: AsyncSession for read-only querying.
            dry_run: Must default to True.
            limit: Maximum document records to evaluate per batch.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        report = ReconciliationReport(tenant_id=tenant_id, dry_run=dry_run, scanned_at=now_iso)

        # 1. Fetch documents within tenant
        doc_stmt = (
            select(Document)
            .where(Document.tenant_id == tenant_id, Document.is_deleted.is_(False))
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        docs = list((await session.execute(doc_stmt)).scalars().all())
        report.total_documents = len(docs)

        for doc in docs:
            doc_id = doc.id

            # 2. Latest version & storage object
            ver_stmt = (
                select(DocumentVersion)
                .where(DocumentVersion.document_id == doc_id, DocumentVersion.is_deleted.is_(False))
                .order_by(DocumentVersion.version_number.desc())
                .limit(1)
            )
            version = (await session.execute(ver_stmt)).scalar_one_or_none()

            storage_valid = False
            storage_anomaly = None
            if version and version.storage_object:
                preflight = StoragePreflightValidator.validate(
                    version.storage_object, expected_tenant_id=tenant_id
                )
                storage_valid = preflight.is_valid
                storage_anomaly = preflight.anomaly_type

            # 3. Chunks count
            chunk_stmt = (
                select(func.count(DocumentChunk.id))
                .where(DocumentChunk.document_id == doc_id, DocumentChunk.is_deleted.is_(False))
            )
            chunk_count = (await session.execute(chunk_stmt)).scalar() or 0

            # 4. Embeddings count
            emb_stmt = (
                select(func.count(ChunkEmbedding.id))
                .join(DocumentChunk, ChunkEmbedding.chunk_id == DocumentChunk.id)
                .where(DocumentChunk.document_id == doc_id, ChunkEmbedding.is_deleted.is_(False))
            )
            emb_count = (await session.execute(emb_stmt)).scalar() or 0

            # 5. Vectors count
            vec_stmt = (
                select(func.count(VectorIndexMetadata.id))
                .where(VectorIndexMetadata.document_id == doc_id, VectorIndexMetadata.is_deleted.is_(False))
            )
            vec_count = (await session.execute(vec_stmt)).scalar() or 0

            # 6. Latest ProcessingJob
            job_stmt = (
                select(ProcessingJob)
                .where(ProcessingJob.document_id == doc_id, ProcessingJob.is_deleted.is_(False))
                .order_by(ProcessingJob.created_at.desc())
                .limit(1)
            )
            job = (await session.execute(job_stmt)).scalar_one_or_none()
            job_status = job.status if job else None
            dispatch_state = job.dispatch_state if job else None

            # 7. Classification logic
            if doc.status == DocumentStatus.READY:
                if chunk_count > 0 and (chunk_count == vec_count or (chunk_count - vec_count) <= 1):
                    classification = "HEALTHY_READY"
                    report.healthy_count += 1
                else:
                    classification = "READY_PARITY_DRIFT"
                    report.other_discrepancy_count += 1
            elif doc.status == DocumentStatus.FAILED:
                classification = "CLASS_C_FAILED_WITH_DIAGNOSTICS"
                report.class_c_count += 1
            elif doc.status == DocumentStatus.UPLOADED:
                if storage_valid:
                    classification = "CLASS_A_STRANDED_WITH_STORAGE"
                    report.class_a_count += 1
                else:
                    classification = "CLASS_B_STRANDED_MISSING_STORAGE"
                    report.class_b_count += 1
            else:
                classification = f"INTERMEDIATE_{doc.status}"
                report.other_discrepancy_count += 1

            item = ReconciliationItem(
                document_id=str(doc.id),
                title=getattr(doc, "title", None) or getattr(doc, "filename", "Untitled"),
                status=doc.status,
                classification=classification,
                storage_valid=storage_valid,
                storage_anomaly=storage_anomaly,
                chunk_count=chunk_count,
                embedding_count=emb_count,
                vector_count=vec_count,
                job_status=job_status,
                dispatch_state=dispatch_state,
                details={
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "has_version": version is not None,
                },
            )
            report.items.append(item)

        return report
