"""Celery Beat Quota Alert Worker — WP-3B / GAP-QTA-03.

Periodically evaluates workspace token consumption against 80% and 95% spend thresholds.
Records immutable audit trail entries in `audit_logs` with idempotency deduplication
per workspace and billing period to prevent alert spam across periodic scheduler ticks.
"""
import asyncio
from datetime import date, datetime, timezone
from typing import Any
import uuid

from celery import shared_task
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from backend.database.engine import get_session_factory
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.workspace import Workspace
from backend.modules.analytics.repositories.usage_repository import UsageRepository
from backend.modules.analytics.services.quota import QuotaGovernor

logger = get_logger(__name__)

ACTION_WARNING_80 = "workspace.quota.warning_80"
ACTION_CRITICAL_95 = "workspace.quota.critical_95"


async def check_workspace_quota_alerts(
    session: AsyncSession, as_of_date: date | None = None
) -> list[dict[str, Any]]:
    """Scan all active workspaces for 80% and 95% token budget thresholds.

    Emits idempotent audit log records for newly breached thresholds.
    Returns list of newly generated alert records.
    """
    now = datetime.now(timezone.utc)
    target_date = as_of_date or now.date()
    period_start = UsageRepository.get_current_period_start(target_date)

    governor = QuotaGovernor()

    # Query all non-deleted workspaces
    stmt = select(Workspace).where(Workspace.is_deleted == False)
    result = await session.execute(stmt)
    workspaces = result.scalars().all()

    generated_alerts: list[dict[str, Any]] = []

    for ws in workspaces:
        try:
            quota_settings = await governor.get_quota_settings(
                workspace_id=ws.id, session=session
            )
            limit = quota_settings.monthly_token_limit if quota_settings else governor.DEFAULT_TOKEN_LIMIT
            if limit <= 0:
                continue

            used_tokens = await governor.get_durable_usage(
                workspace_id=ws.id, session=session, period_start=period_start
            )

            pct = used_tokens / float(limit)

            # Determine target threshold
            target_action = None
            threshold_label = None
            if pct >= 0.95:
                target_action = ACTION_CRITICAL_95
                threshold_label = "95%"
            elif pct >= 0.80:
                target_action = ACTION_WARNING_80
                threshold_label = "80%"
            else:
                continue

            # Idempotency check: verify if an alert for this action was already generated this period
            period_dt = datetime.combine(period_start, datetime.min.time(), tzinfo=timezone.utc)
            dup_stmt = select(AuditLog.id).where(
                and_(
                    AuditLog.tenant_id == ws.id,
                    AuditLog.action == target_action,
                    AuditLog.created_at >= period_dt,
                )
            ).limit(1)
            dup_res = await session.execute(dup_stmt)
            if dup_res.scalar_one_or_none() is not None:
                # Alert already recorded for this threshold and period
                logger.debug(
                    "Quota alert suppressed (duplicate for current period)",
                    workspace_id=str(ws.id),
                    action=target_action,
                )
                continue

            alert_details = {
                "workspace_id": str(ws.id),
                "workspace_name": ws.name,
                "used_tokens": used_tokens,
                "monthly_token_limit": limit,
                "usage_percentage": round(pct * 100.0, 2),
                "threshold_level": threshold_label,
                "period_start": str(period_start),
                "notification_external_delivered": False,
            }

            audit_entry = AuditLog(
                id=uuid.uuid4(),
                tenant_id=ws.id,
                action=target_action,
                resource_type="workspace_quota",
                resource_id=str(ws.id),
                details=alert_details,
                status="success",
            )
            session.add(audit_entry)
            generated_alerts.append(alert_details)

            logger.info(
                "Generated quota threshold alert event",
                workspace_id=str(ws.id),
                action=target_action,
                pct=round(pct * 100.0, 2),
            )
        except Exception as ws_exc:
            logger.error(
                "Error evaluating workspace quota alert",
                workspace_id=str(ws.id),
                error=str(ws_exc),
            )

    if generated_alerts:
        await session.commit()

    return generated_alerts


@shared_task(
    bind=True,
    queue="default",
    name="backend.modules.analytics.workers.quota_alerts.check_quota_threshold_alerts_task",
)
def check_quota_threshold_alerts_task(self: Any | None = None) -> dict[str, Any]:
    """Celery Beat task running periodic evaluation of workspace token quotas."""
    return asyncio.run(_async_check_quota_threshold_alerts_task())


async def _async_check_quota_threshold_alerts_task() -> dict[str, Any]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        alerts = await check_workspace_quota_alerts(session)
        return {
            "status": "success",
            "alerts_generated": len(alerts),
            "alerts": alerts,
        }
