import datetime
import uuid
import pytest
from sqlalchemy import select

from backend.database.engine import get_session_factory
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace
from backend.modules.analytics.models.token_usage import TokenUsageORM
from backend.modules.analytics.models.workspace_usage import WorkspaceUsage
from backend.modules.analytics.models.workspace_user_usage import WorkspaceUserUsage
from backend.modules.analytics.repositories.usage_repository import UsageRepository
from backend.modules.analytics.repositories.user_quota_repository import UserQuotaRepository
from backend.modules.analytics.services.quota import QuotaGovernor


@pytest.mark.asyncio
async def test_record_token_usage_and_deduplication():
    """Verify recording token usage creates TokenUsageORM and increments durable counters,
    while duplicate correlation_id is rejected to prevent double counting."""
    governor = QuotaGovernor()

    async with get_session_factory()() as session:
        # Create workspace and user
        suffix = uuid.uuid4().hex[:6]
        user = User(
            id=uuid.uuid4(),
            email=f"b8_user_{suffix}@example.com",
            hashed_password="pw",
            display_name="B8 User",
            is_active=True,
            is_verified=True,
        )
        ws = Workspace(
            id=uuid.uuid4(),
            name=f"B8 Workspace {suffix}",
            slug=f"b8-ws-{suffix}",
            public_id=f"ws-b8-{suffix}",
            storage_prefix=f"workspaces/ws-b8-{suffix}",
            qdrant_namespace=f"raguard_knowledge_ws-b8-{suffix}",
        )
        session.add_all([user, ws])
        await session.commit()

        correlation_id = f"corr-b8-{uuid.uuid4().hex}"

        # 1. First recording
        record, was_new = await governor.record_token_usage(
            workspace_id=ws.id,
            tenant_id=str(ws.id),
            prompt_tokens=150,
            completion_tokens=50,
            correlation_id=correlation_id,
            provider="openai",
            model_name="gpt-4o",
            total_cost_usd=0.002,
            user_id=user.id,
            session=session,
        )

        assert was_new is True
        assert record.id is not None
        assert record.prompt_tokens == 150
        assert record.completion_tokens == 50
        assert record.correlation_id == correlation_id
        assert record.user_id == user.id

        # Verify durable counters
        ws_used = await governor.get_durable_usage(ws.id, session=session)
        assert ws_used == 200

        user_used = await governor.get_user_durable_usage(ws.id, user.id, session=session)
        assert user_used == 200

        # 2. Duplicate recording with the same correlation_id
        dup_record, dup_was_new = await governor.record_token_usage(
            workspace_id=ws.id,
            tenant_id=str(ws.id),
            prompt_tokens=150,
            completion_tokens=50,
            correlation_id=correlation_id,
            provider="openai",
            model_name="gpt-4o",
            total_cost_usd=0.002,
            user_id=user.id,
            session=session,
        )

        assert dup_was_new is False
        assert dup_record.id == record.id

        # Verify durable counters did NOT double count!
        ws_used_after = await governor.get_durable_usage(ws.id, session=session)
        assert ws_used_after == 200

        user_used_after = await governor.get_user_durable_usage(ws.id, user.id, session=session)
        assert user_used_after == 200


@pytest.mark.asyncio
async def test_get_aggregated_usage_with_user_breakdown_and_boundaries():
    """Verify get_aggregated_usage groups by workspace and user and respects period boundaries."""
    governor = QuotaGovernor()

    async with get_session_factory()() as session:
        suffix = uuid.uuid4().hex[:6]
        user1 = User(
            id=uuid.uuid4(),
            email=f"b8_u1_{suffix}@example.com",
            hashed_password="pw",
            display_name="User One",
            is_active=True,
            is_verified=True,
        )
        user2 = User(
            id=uuid.uuid4(),
            email=f"b8_u2_{suffix}@example.com",
            hashed_password="pw",
            display_name="User Two",
            is_active=True,
            is_verified=True,
        )
        ws = Workspace(
            id=uuid.uuid4(),
            name=f"B8 Agg Workspace {suffix}",
            slug=f"b8-agg-{suffix}",
            public_id=f"ws-b8-agg-{suffix}",
            storage_prefix=f"workspaces/ws-b8-agg-{suffix}",
            qdrant_namespace=f"raguard_knowledge_ws-b8-agg-{suffix}",
        )
        session.add_all([user1, user2, ws])
        await session.commit()

        # In current period
        now = datetime.datetime.now(datetime.timezone.utc)
        period_start = datetime.date(now.year, now.month, 1)

        # User 1 call
        await governor.record_token_usage(
            workspace_id=ws.id,
            tenant_id=str(ws.id),
            prompt_tokens=100,
            completion_tokens=40,
            correlation_id=f"corr-agg-1-{uuid.uuid4().hex}",
            user_id=user1.id,
            total_cost_usd=0.001,
            created_at=now,
            session=session,
        )

        # User 2 call
        await governor.record_token_usage(
            workspace_id=ws.id,
            tenant_id=str(ws.id),
            prompt_tokens=200,
            completion_tokens=60,
            correlation_id=f"corr-agg-2-{uuid.uuid4().hex}",
            user_id=user2.id,
            total_cost_usd=0.003,
            created_at=now,
            session=session,
        )

        # Another user 1 call
        await governor.record_token_usage(
            workspace_id=ws.id,
            tenant_id=str(ws.id),
            prompt_tokens=50,
            completion_tokens=10,
            correlation_id=f"corr-agg-3-{uuid.uuid4().hex}",
            user_id=user1.id,
            total_cost_usd=0.0005,
            created_at=now,
            session=session,
        )

        # Usage from previous period (should not be included in current period aggregation)
        last_month_dt = (period_start - datetime.timedelta(days=5))
        last_month_created = datetime.datetime(
            last_month_dt.year, last_month_dt.month, 15, 12, 0, 0, tzinfo=datetime.timezone.utc
        )
        await governor.record_token_usage(
            workspace_id=ws.id,
            tenant_id=str(ws.id),
            prompt_tokens=500,
            completion_tokens=500,
            correlation_id=f"corr-old-{uuid.uuid4().hex}",
            user_id=user1.id,
            total_cost_usd=0.01,
            created_at=last_month_created,
            session=session,
        )

        # Aggregate for current period
        agg = await governor.get_aggregated_usage(workspace_id=ws.id, period_start=period_start, session=session)

        assert agg["workspace_id"] == ws.id
        assert agg["billing_period_start"] == period_start
        assert agg["total_prompt_tokens"] == (100 + 200 + 50)  # 350
        assert agg["total_completion_tokens"] == (40 + 60 + 10)  # 110
        assert agg["total_tokens"] == 460
        assert agg["total_invocations"] == 3
        assert pytest.approx(agg["total_cost_usd"], 0.0001) == 0.0045

        # Check user breakdown
        users_map = {u["user_id"]: u for u in agg["user_breakdown"]}
        assert user1.id in users_map
        assert user2.id in users_map

        u1_data = users_map[user1.id]
        assert u1_data["prompt_tokens"] == 150
        assert u1_data["completion_tokens"] == 50
        assert u1_data["total_tokens"] == 200
        assert u1_data["total_invocations"] == 2

        u2_data = users_map[user2.id]
        assert u2_data["prompt_tokens"] == 200
        assert u2_data["completion_tokens"] == 60
        assert u2_data["total_tokens"] == 260
        assert u2_data["total_invocations"] == 1


@pytest.mark.asyncio
async def test_reconcile_usage_and_sync():
    """Verify reconcile_usage identifies drift between durable counters and token logs,
    and synchronizes counters when sync=True."""
    governor = QuotaGovernor()

    async with get_session_factory()() as session:
        suffix = uuid.uuid4().hex[:6]
        user = User(
            id=uuid.uuid4(),
            email=f"b8_rec_{suffix}@example.com",
            hashed_password="pw",
            display_name="Rec User",
            is_active=True,
            is_verified=True,
        )
        ws = Workspace(
            id=uuid.uuid4(),
            name=f"B8 Rec Workspace {suffix}",
            slug=f"b8-rec-{suffix}",
            public_id=f"ws-b8-rec-{suffix}",
            storage_prefix=f"workspaces/ws-b8-rec-{suffix}",
            qdrant_namespace=f"raguard_knowledge_ws-b8-rec-{suffix}",
        )
        session.add_all([user, ws])
        await session.commit()

        now = datetime.datetime.now(datetime.timezone.utc)
        period_start = datetime.date(now.year, now.month, 1)

        # Record 1 call: 300 tokens
        await governor.record_token_usage(
            workspace_id=ws.id,
            tenant_id=str(ws.id),
            prompt_tokens=200,
            completion_tokens=100,
            correlation_id=f"corr-rec-1-{uuid.uuid4().hex}",
            user_id=user.id,
            created_at=now,
            session=session,
        )

        # Consistent check
        report = await governor.reconcile_usage(workspace_id=ws.id, period_start=period_start, sync=False, session=session)
        assert report["is_consistent"] is True
        assert report["drift"] == 0
        assert report["durable_tokens"] == 300
        assert report["aggregated_tokens"] == 300

        # Simulate drift: artificially bump durable workspace counter by 500
        repo = UsageRepository(session)
        await repo.atomic_increment(ws.id, tokens=500, queries=2, period_start=period_start)

        # Drift check without sync
        report_drift = await governor.reconcile_usage(workspace_id=ws.id, period_start=period_start, sync=False, session=session)
        assert report_drift["is_consistent"] is False
        assert report_drift["drift"] == 500
        assert report_drift["durable_tokens"] == 800
        assert report_drift["aggregated_tokens"] == 300
        assert report_drift["synced"] is False

        # Now run with sync=True
        report_synced = await governor.reconcile_usage(workspace_id=ws.id, period_start=period_start, sync=True, session=session)
        assert report_synced["synced"] is True

        # Check that durable counter was resynchronized to 300
        ws_used_synced = await governor.get_durable_usage(ws.id, session=session)
        assert ws_used_synced == 300
