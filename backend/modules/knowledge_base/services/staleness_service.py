from datetime import datetime
import math
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models import Document
from backend.core.events.dispatcher import EventDispatcher
from backend.modules.knowledge_base.schemas.staleness_dto import (
    BulkRemediationRequestDTO,
    BulkRemediationResultDTO,
    StaleDocumentItemDTO,
    StalenessPolicyDTO,
    StalenessReportDTO,
)


class StalenessService:
    def __init__(self, session: AsyncSession, event_dispatcher: EventDispatcher):
        self.session = session
        self.event_dispatcher = event_dispatcher

    def _calculate_exponential_decay(self, age_days: int, max_age_days: int) -> float:
        """Exponential decay curve."""
        if age_days >= max_age_days:
            return 0.0
        # λ controls the decay rate, typically ~3.0 for 95% decay at max_age
        lambda_val = 3.0
        decay = math.exp(-lambda_val * (age_days / max_age_days))
        return decay * 100.0

    def _calculate_linear_decay(self, age_days: int, max_age_days: int) -> float:
        """Linear decay curve."""
        if age_days >= max_age_days:
            return 0.0
        return max(0.0, (1.0 - (age_days / max_age_days)) * 100.0)

    async def evaluate_workspace_staleness(self, workspace_id: UUID, policy: StalenessPolicyDTO | None = None) -> None:
        """Evaluates staleness for all documents in a workspace and updates their metadata.
        If policy is not provided, resolves it from WorkspaceSettings.
        """
        if policy is None:
            from backend.repositories.workspace_settings import WorkspaceSettingsRepository
            from backend.repositories.workspace_settings_history import WorkspaceSettingsHistoryRepository
            from backend.repositories.workspace import WorkspaceRepository
            from backend.repositories.workspace_member import WorkspaceMemberRepository
            from backend.services.workspace.settings_service import WorkspaceSettingsService

            # Since evaluate_workspace_staleness is often run in background, we might not have a user_id
            # But get_settings takes user_id for authorization. We can just use the repository to bypass auth for internal service.
            settings_repo = WorkspaceSettingsRepository(self.session)
            settings = await settings_repo.get_by_workspace_id(workspace_id)
            if settings and "staleness" in settings.settings_json:
                policy = StalenessPolicyDTO(**settings.settings_json["staleness"])
            else:
                policy = StalenessPolicyDTO()

        stmt = select(Document).where(
            Document.tenant_id == str(workspace_id),
            Document.is_deleted.is_(False)
        )
        res = await self.session.execute(stmt)
        docs = res.scalars().all()

        from datetime import UTC
        now = datetime.now(UTC)
        for doc in docs:
            age_td = now - (doc.updated_at or doc.created_at)
            age_days = age_td.days

            if policy.decay_model == "linear":
                score = self._calculate_linear_decay(age_days, policy.max_age_days)
            else:
                score = self._calculate_exponential_decay(age_days, policy.max_age_days)

            is_stale = False
            if policy.auto_stale_flagging and age_days >= policy.inactivity_threshold_days:
                is_stale = True

            meta: dict[str, Any] = dict(doc.user_metadata) if doc.user_metadata else {}

            was_stale = meta.get("is_stale", False)

            meta["freshness_score"] = round(score, 2)
            meta["is_stale"] = is_stale
            meta["age_days"] = age_days
            doc.user_metadata = meta

            if is_stale and not was_stale:
                await self.event_dispatcher.dispatch(
                    "KNOWLEDGE_DOCUMENT_STALE_DETECTED",
                    {
                        "workspace_id": str(workspace_id),
                        "document_id": str(doc.id),
                        "freshness_score": score,
                        "age_days": age_days
                    }
                )

        await self.session.commit()

    async def get_staleness_report(self, workspace_id: UUID) -> StalenessReportDTO:
        """Generates a staleness report for the workspace."""
        stmt = select(Document).where(
            Document.tenant_id == str(workspace_id),
            Document.is_deleted.is_(False)
        )
        res = await self.session.execute(stmt)
        docs = res.scalars().all()

        total = len(docs)
        stale_count = 0
        stale_items = []
        distribution = {"0-30 days": 0, "31-90 days": 0, ">90 days": 0}

        for doc in docs:
            meta = doc.user_metadata or {}
            is_stale = meta.get("is_stale", False)
            age = meta.get("age_days", 0)
            score = meta.get("freshness_score", 100.0)

            if age <= 30:
                distribution["0-30 days"] += 1
            elif age <= 90:
                distribution["31-90 days"] += 1
            else:
                distribution[">90 days"] += 1

            if is_stale:
                stale_count += 1
                stale_items.append(
                    StaleDocumentItemDTO(
                        document_id=doc.id,
                        filename=doc.filename,
                        age_days=age,
                        freshness_score=score,
                        is_expired=age >= 90, # default max age assumption
                        last_updated_at=doc.updated_at or doc.created_at
                    )
                )

        stale_ratio = (stale_count / total) * 100 if total > 0 else 0.0

        return StalenessReportDTO(
            workspace_id=workspace_id,
            total_documents=total,
            stale_count=stale_count,
            stale_ratio=round(stale_ratio, 2),
            aging_distribution=distribution,
            stale_documents=stale_items
        )

    async def execute_bulk_remediation(
        self, workspace_id: UUID, request: BulkRemediationRequestDTO
    ) -> BulkRemediationResultDTO:
        """Executes bulk remediation actions on stale documents."""
        stmt = select(Document).where(
            Document.tenant_id == workspace_id,
            Document.id.in_(request.document_ids),
            not Document.is_deleted
        )
        res = await self.session.execute(stmt)
        docs = res.scalars().all()

        result = BulkRemediationResultDTO()
        now = datetime.utcnow()

        for doc in docs:
            if request.action == "MARK_REVIEWED":
                # Resets the updated_at timestamp effectively resetting age to 0
                doc.updated_at = now
                meta = dict(doc.user_metadata) if doc.user_metadata else {}
                meta["is_stale"] = False
                meta["freshness_score"] = 100.0
                meta["age_days"] = 0
                doc.user_metadata = meta
                result.modified_count += 1

            elif request.action == "ARCHIVE":
                # Soft-archive
                doc.status = "ARCHIVED"
                result.archived_count += 1

            elif request.action == "REPROCESS":
                # Change status to TRIGGER_EXTRACTION so worker picks it up
                doc.status = "PENDING"
                # The actual queuing would be handled by triggering the job service
                # We'll just mark the count here for simulation
                result.queued_count += 1

        await self.session.commit()
        return result
