"""Knowledge Health Orchestrator (`KnowledgeHealthOrchestrator`).

Master service coordinating two-phase purges, orphan vector sweeps, 1:1 count parity audits,
and model rotation drift detection across all storage tiers (`ADR-005`, `ADR-M6-001`).
"""

from datetime import UTC, datetime
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.core.events.dispatcher import EventDispatcher, get_dispatcher
from backend.core.events.types import EventType
from backend.modules.knowledge_health.audits.integrity import IntegrityAuditor
from backend.modules.knowledge_health.audits.stale_scanner import StaleEmbeddingScanner
from backend.modules.knowledge_health.cleanups.orphans import OrphanCleanupEngine
from backend.modules.knowledge_health.cleanups.purge import PurgeOrchestrator
from backend.modules.knowledge_health.events.payloads import (
    KnowledgeHealthDomainEvent,
    KnowledgeHealthScanCompletedPayload,
    KnowledgeHealthScanStartedPayload,
)
from backend.modules.knowledge_health.models.health_scan import HealthScanJob
from backend.modules.knowledge_health.repositories.health_repository import HealthRepository
from backend.modules.knowledge_health.schemas.errors import InvalidScanTypeError
from backend.modules.knowledge_health.schemas.health_dto import (
    HealthScanJobDTO,
    MigrationJobDTO,
    ParityAuditDTO,
    PurgeSummaryDTO,
    ScanStatus,
    ScanType,
)
from backend.modules.vector.services.vector_service import VectorStorageService

logger = structlog.get_logger(__name__)


class KnowledgeHealthOrchestrator:
    """Master domain service coordinating Knowledge Health scans, audits, and purges (`ADR-005`)."""

    def __init__(
        self,
        session: AsyncSession,
        vector_service: VectorStorageService | None = None,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self.session = session
        self.vector_service = vector_service or VectorStorageService(session)
        self.dispatcher = dispatcher or get_dispatcher()
        self.repo = HealthRepository(session)
        self.purge_engine = PurgeOrchestrator(
            session, self.vector_service, self.dispatcher
        )
        self.orphan_engine = OrphanCleanupEngine(session, self.vector_service)
        self.auditor = IntegrityAuditor(
            session, self.vector_service.provider, self.dispatcher
        )
        self.stale_scanner = StaleEmbeddingScanner(session, self.repo, self.dispatcher)

    async def run_health_scan(
        self,
        tenant_id: str,
        scan_type: ScanType = ScanType.ALL,
        active_provider: str = "openai",
        active_model: str = "text-embedding-3-large",
    ) -> HealthScanJobDTO:
        """Execute scheduled or manual health scan across PostgreSQL and Qdrant (`ADR-M6-001`)."""
        t0 = time.perf_counter()
        log = logger.bind(tenant_id=tenant_id, scan_type=str(scan_type))
        log.info("Initiating Knowledge Health scan job")

        if scan_type not in {
            ScanType.ORPHAN_SWEEP,
            ScanType.PARITY_AUDIT,
            ScanType.STALE_DETECTOR,
            ScanType.ALL,
        }:
            raise InvalidScanTypeError(tenant_id=tenant_id, scan_type=str(scan_type))

        # 1. Create and log HealthScanJob in PROCESSING state
        job = HealthScanJob(
            tenant_id=tenant_id,
            scan_type=str(scan_type),
            status=ScanStatus.PROCESSING.value,
        )
        job_id = await self.repo.log_scan_job(job)

        start_payload = KnowledgeHealthScanStartedPayload(
            job_id=job_id,
            tenant_id=tenant_id,
            scan_type=str(scan_type),
        )
        await self.dispatcher.publish(
            KnowledgeHealthDomainEvent(
                event_type=EventType.KNOWLEDGE_HEALTH_SCAN_STARTED,
                payload=start_payload.to_dict(),
            )
        )

        orphans_purged = 0
        stale_chunks_found = 0
        parity_status = "UNKNOWN"
        error_msg = None

        try:
            # Phase A: Orphan Sweep
            if scan_type in {ScanType.ORPHAN_SWEEP, ScanType.ALL}:
                orphans_purged = await self.orphan_engine.sweep_orphaned_chunks(
                    tenant_id
                )

            # Phase B: Parity Check
            if scan_type in {ScanType.PARITY_AUDIT, ScanType.ALL}:
                audit_dto = await self.auditor.verify_tenant_parity(tenant_id)
                parity_status = audit_dto.parity_status

            # Phase C: Stale Embedding Drift Detection
            if scan_type in {ScanType.STALE_DETECTOR, ScanType.ALL}:
                stale_records = await self.stale_scanner.detect_stale_embeddings(
                    tenant_id=tenant_id,
                    active_provider=active_provider,
                    active_model=active_model,
                )
                stale_chunks_found = len(stale_records)

            duration_ms = (time.perf_counter() - t0) * 1000.0

            # Update job progress to COMPLETED
            updated_job = await self.repo.update_scan_progress(
                job_id=job_id,
                status=ScanStatus.COMPLETED.value,
                stats={
                    "orphans_found": orphans_purged,
                    "orphans_purged": orphans_purged,
                    "stale_chunks_found": stale_chunks_found,
                    "parity_status": parity_status,
                    "duration_ms": duration_ms,
                },
            )

            end_payload = KnowledgeHealthScanCompletedPayload(
                job_id=job_id,
                tenant_id=tenant_id,
                scan_type=str(scan_type),
                status=ScanStatus.COMPLETED.value,
                orphans_purged=orphans_purged,
                parity_status=parity_status,
            )
            await self.dispatcher.publish(
                KnowledgeHealthDomainEvent(
                    event_type=EventType.KNOWLEDGE_HEALTH_SCAN_COMPLETED,
                    payload=end_payload.to_dict(),
                )
            )

            log.info(
                "Completed Knowledge Health scan job successfully",
                duration_ms=duration_ms,
            )
            return HealthScanJobDTO.model_validate(updated_job)

        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            error_msg = str(exc)
            log.error("Knowledge Health scan job failed", error=error_msg)

            await self.repo.update_scan_progress(
                job_id=job_id,
                status=ScanStatus.FAILED.value,
                stats={"duration_ms": duration_ms, "error_message": error_msg},
            )

            end_payload = KnowledgeHealthScanCompletedPayload(
                job_id=job_id,
                tenant_id=tenant_id,
                scan_type=str(scan_type),
                status=ScanStatus.FAILED.value,
                orphans_purged=orphans_purged,
                parity_status=parity_status,
            )
            await self.dispatcher.publish(
                KnowledgeHealthDomainEvent(
                    event_type=EventType.KNOWLEDGE_HEALTH_SCAN_COMPLETED,
                    payload=end_payload.to_dict(),
                )
            )
            raise

    async def execute_two_phase_purge(
        self, document_id: UUID, tenant_id: str
    ) -> PurgeSummaryDTO:
        """Execute two-phase transactional purge (`ADR-M6-001`)."""
        return await self.purge_engine.execute_two_phase_purge(document_id, tenant_id)

    async def verify_parity(self, tenant_id: str) -> ParityAuditDTO:
        """Execute immediate real-time 1:1 count parity check."""
        return await self.auditor.verify_tenant_parity(tenant_id)

    async def rotate_tenant_embedding_model(
        self,
        tenant_id: str,
        new_provider: str,
        new_model: str,
    ) -> MigrationJobDTO:
        """Initiate model rotation campaign, detecting stale chunks and triggering shadow re-index (`ADR-M6-002`)."""
        t0 = time.perf_counter()
        log = logger.bind(
            tenant_id=tenant_id, target_provider=new_provider, target_model=new_model
        )
        log.info("Initiating model rotation campaign")

        stale_records = await self.stale_scanner.detect_stale_embeddings(
            tenant_id=tenant_id,
            active_provider=new_provider,
            active_model=new_model,
        )

        job_id = await self.stale_scanner.trigger_shadow_reindex(
            tenant_id=tenant_id,
            records=stale_records,
            target_provider=new_provider,
            target_model=new_model,
        )

        return MigrationJobDTO(
            job_id=job_id,
            tenant_id=tenant_id,
            target_provider=new_provider,
            target_model=new_model,
            stale_chunks_enqueued=len(stale_records),
            status="PROCESSING",
            started_at=datetime.now(UTC),
        )

    async def list_scan_jobs(
        self,
        tenant_id: str,
        scan_type: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[HealthScanJobDTO], int]:
        """Fetch paginated scan job history for a tenant."""
        items, total = await self.repo.list_scan_jobs(
            tenant_id, scan_type=scan_type, page=page, size=size
        )
        dtos = [HealthScanJobDTO.model_validate(item) for item in items]
        return dtos, total
