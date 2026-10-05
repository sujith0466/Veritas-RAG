"""Unit tests for WS-B6: Per-User Quota & Usage Attribution."""

import datetime
from datetime import UTC
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.engine import get_session_factory
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.modules.analytics.models.token_usage import TokenUsageORM
from backend.modules.analytics.models.workspace_user_quota import WorkspaceUserQuotaORM
from backend.modules.analytics.models.workspace_user_usage import WorkspaceUserUsage
from backend.modules.analytics.repositories.user_quota_repository import UserQuotaRepository


@pytest.mark.asyncio
async def test_user_quota_creation_and_null_semantics():
    """Verify user quota creation, NULL budget semantics, and update behavior."""
    async with get_session_factory()() as session:
        ws_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Seed workspace and user
        ws = Workspace(
            id=ws_id,
            name="Quota WS",
            slug=f"qws-{uuid.uuid4().hex[:6]}",
            public_id=f"QWS-{uuid.uuid4().hex[:6].upper()}",
            storage_prefix=f"workspaces/{ws_id}",
            qdrant_namespace=f"raguard_knowledge_{ws_id}",
            status=WorkspaceStatus.ACTIVE.value,
        )
        user = User(
            id=user_id,
            email=f"user_{uuid.uuid4().hex[:6]}@veritas.rag",
            is_active=True,
        )
        session.add(ws)
        session.add(user)
        await session.commit()

        repo = UserQuotaRepository(session)

        # 1. By default, no user quota exists
        initial = await repo.get_user_quota(ws_id, user_id)
        assert initial is None

        # 2. Set user quota with NULL budget (unbounded, inherits workspace quota)
        quota_null = await repo.set_user_quota(
            workspace_id=ws_id,
            user_id=user_id,
            monthly_token_budget=None,
            is_hard_enforced=True,
            warning_threshold_pct=0.80,
        )
        assert quota_null.monthly_token_budget is None
        assert quota_null.is_hard_enforced is True
        assert quota_null.warning_threshold_pct == 0.80

        # Verify retrieval
        fetched = await repo.get_user_quota(ws_id, user_id)
        assert fetched is not None
        assert fetched.monthly_token_budget is None

        # 3. Update to explicit quota cap (e.g. 500,000 tokens)
        updated = await repo.set_user_quota(
            workspace_id=ws_id,
            user_id=user_id,
            monthly_token_budget=500_000,
            is_hard_enforced=True,
            warning_threshold_pct=0.85,
        )
        assert updated.monthly_token_budget == 500_000
        assert updated.warning_threshold_pct == 0.85

        # Verify list_user_quotas
        quotas = await repo.list_user_quotas(ws_id)
        assert len(quotas) == 1
        assert quotas[0].user_id == user_id


@pytest.mark.asyncio
async def test_user_usage_increment_and_aggregation():
    """Verify durable per-user usage tracking and atomic increments."""
    async with get_session_factory()() as session:
        ws_id = uuid.uuid4()
        user_id = uuid.uuid4()

        ws = Workspace(
            id=ws_id,
            name="Usage WS",
            slug=f"usg-{uuid.uuid4().hex[:6]}",
            public_id=f"USG-{uuid.uuid4().hex[:6].upper()}",
            storage_prefix=f"workspaces/{ws_id}",
            qdrant_namespace=f"raguard_knowledge_{ws_id}",
            status=WorkspaceStatus.ACTIVE.value,
        )
        user = User(
            id=user_id,
            email=f"user_{uuid.uuid4().hex[:6]}@veritas.rag",
            is_active=True,
        )
        session.add(ws)
        session.add(user)
        await session.commit()

        repo = UserQuotaRepository(session)
        today = datetime.datetime.now(UTC).date().replace(day=1)

        # Increment 1: 1,500 tokens, 1 query
        u1 = await repo.increment_user_usage(ws_id, user_id, tokens=1500, queries=1, period_start=today)
        assert u1.used_tokens == 1500
        assert u1.used_queries == 1

        # Increment 2: 2,500 tokens, 2 queries
        u2 = await repo.increment_user_usage(ws_id, user_id, tokens=2500, queries=2, period_start=today)
        assert u2.used_tokens == 4000
        assert u2.used_queries == 3

        # Read back
        fetched_usage = await repo.get_user_usage(ws_id, user_id, period_start=today)
        assert fetched_usage is not None
        assert fetched_usage.used_tokens == 4000
        assert fetched_usage.used_queries == 3


@pytest.mark.asyncio
async def test_token_usage_attribution_record():
    """Verify TokenUsageORM correctly stores user_id and workspace_id."""
    async with get_session_factory()() as session:
        ws_id = uuid.uuid4()
        user_id = uuid.uuid4()

        ws = Workspace(
            id=ws_id,
            name="Attr WS",
            slug=f"att-{uuid.uuid4().hex[:6]}",
            public_id=f"ATT-{uuid.uuid4().hex[:6].upper()}",
            storage_prefix=f"workspaces/{ws_id}",
            qdrant_namespace=f"raguard_knowledge_{ws_id}",
            status=WorkspaceStatus.ACTIVE.value,
        )
        user = User(
            id=user_id,
            email=f"user_{uuid.uuid4().hex[:6]}@veritas.rag",
            is_active=True,
        )
        session.add(ws)
        session.add(user)
        await session.commit()

        record = TokenUsageORM(
            id=uuid.uuid4(),
            tenant_id=str(ws_id),
            workspace_id=ws_id,
            user_id=user_id,
            correlation_id=f"corr-{uuid.uuid4().hex[:8]}",
            provider="openai",
            model_name="gpt-4o-mini",
            prompt_tokens=120,
            completion_tokens=80,
            total_cost_usd=0.0003,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)

        assert record.workspace_id == ws_id
        assert record.user_id == user_id
        assert record.prompt_tokens == 120
        assert record.completion_tokens == 80
