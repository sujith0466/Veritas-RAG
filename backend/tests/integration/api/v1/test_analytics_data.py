import uuid
from datetime import UTC, datetime
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.core.auth.context import UserContext
from backend.core.permissions.rbac import Role
from backend.core.dependencies.auth import get_optional_user, get_current_user
from backend.modules.analytics.models.query_analytics import QueryAnalyticsRecord
from backend.core.dependencies.database import get_db

import os
from dotenv import load_dotenv

load_dotenv("backend/.env")
load_dotenv(".env")
DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_async_engine(DATABASE_URL, poolclass=__import__('sqlalchemy.pool').pool.NullPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

app = create_app()

@pytest.fixture
def client():
    return TestClient(app)

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_data():
    async with TestingSessionLocal() as db:
        # Create unique tenant IDs for this test run
        tenant_a = f"Workspace-A-{uuid.uuid4()}"
        tenant_b = f"Workspace-B-{uuid.uuid4()}"

        # Workspace A Data
        record_a1 = QueryAnalyticsRecord(
            tenant_id=tenant_a,
            correlation_id=str(uuid.uuid4()),
            query_text="unique_lexeme_alpha",
            outcome="SUCCESS",
            total_duration_ms=100.0,
            confidence_score=0.9,
            reliability_score=90.0,
            retry_attempts=0,
            is_safe_to_serve=True,
            created_at=datetime.now(UTC)
        )
        record_a2 = QueryAnalyticsRecord(
            tenant_id=tenant_a,
            correlation_id=str(uuid.uuid4()),
            query_text="unique_lexeme_alpha",
            outcome="CLARIFICATION_REQUIRED", # Unanswered
            total_duration_ms=100.0,
            confidence_score=0.9,
            reliability_score=90.0,
            retry_attempts=0,
            is_safe_to_serve=True,
            created_at=datetime.now(UTC)
        )
        record_a3 = QueryAnalyticsRecord(
            tenant_id=tenant_a,
            correlation_id=str(uuid.uuid4()),
            query_text="unrelated_term",
            outcome="ABORTED_LOW_CONFIDENCE", # Unanswered
            total_duration_ms=100.0,
            confidence_score=0.9,
            reliability_score=90.0,
            retry_attempts=0,
            is_safe_to_serve=True,
            created_at=datetime.now(UTC)
        )

        # Workspace B Data
        record_b1 = QueryAnalyticsRecord(
            tenant_id=tenant_b,
            correlation_id=str(uuid.uuid4()),
            query_text="unique_lexeme_beta",
            outcome="SUCCESS",
            total_duration_ms=100.0,
            confidence_score=0.9,
            reliability_score=90.0,
            retry_attempts=0,
            is_safe_to_serve=True,
            created_at=datetime.now(UTC)
        )
        record_b2 = QueryAnalyticsRecord(
            tenant_id=tenant_b,
            correlation_id=str(uuid.uuid4()),
            query_text="unique_lexeme_beta",
            outcome="ABORTED_HALLUCINATION", # Unanswered
            total_duration_ms=100.0,
            confidence_score=0.9,
            reliability_score=90.0,
            retry_attempts=0,
            is_safe_to_serve=True,
            created_at=datetime.now(UTC)
        )

        db.add_all([record_a1, record_a2, record_a3, record_b1, record_b2])
        await db.commit()

        yield tenant_a, tenant_b

def get_mock_user(workspace: str, role: Role):
    return UserContext(
        id=uuid.uuid4(),
        email="test@raguard.ai",
        role=role,
        is_active=True,
        is_verified=True,
        supabase_id="mock-supabase-id",
        session_id=uuid.uuid4(),
        workspace_name=workspace
    )

@pytest.mark.asyncio
async def test_real_cross_tenant_popular_topics(client, setup_data):
    tenant_a, tenant_b = setup_data

    # Test Tenant A
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(tenant_a, Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(tenant_a, Role.VIEWER)

    res_a = client.get("/api/v1/analytics/popular-topics")
    assert res_a.status_code == 200
    data_a = res_a.json()["data"]

    topics_a = [t["topic"] for t in data_a]
    assert "alpha" in topics_a
    assert "beta" not in topics_a

    # Test Tenant B
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(tenant_b, Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(tenant_b, Role.VIEWER)

    res_b = client.get("/api/v1/analytics/popular-topics")
    assert res_b.status_code == 200
    data_b = res_b.json()["data"]

    topics_b = [t["topic"] for t in data_b]
    assert "beta" in topics_b
    assert "alpha" not in topics_b

@pytest.mark.asyncio
async def test_real_cross_tenant_unanswered_queries(client, setup_data):
    tenant_a, tenant_b = setup_data

    # Test Tenant A
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(tenant_a, Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(tenant_a, Role.VIEWER)

    res_a = client.get("/api/v1/analytics/unanswered-queries")
    assert res_a.status_code == 200
    data_a = res_a.json()["data"]

    queries_a = [t["query_text"] for t in data_a]
    assert "unique_lexeme_alpha" in queries_a # CLARIFICATION_REQUIRED
    assert "unrelated_term" in queries_a # ABORTED_LOW_CONFIDENCE
    assert "unique_lexeme_beta" not in queries_a

    # Test Tenant B
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(tenant_b, Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(tenant_b, Role.VIEWER)

    res_b = client.get("/api/v1/analytics/unanswered-queries")
    assert res_b.status_code == 200
    data_b = res_b.json()["data"]

    queries_b = [t["query_text"] for t in data_b]
    assert "unique_lexeme_beta" in queries_b # ABORTED_HALLUCINATION
    assert "unique_lexeme_alpha" not in queries_b
    assert "unrelated_term" not in queries_b

@pytest.mark.asyncio
async def test_authorization_matrix(client, setup_data):
    tenant_a, _ = setup_data

    # Unauthenticated
    app.dependency_overrides.pop(get_optional_user, None)
    app.dependency_overrides.pop(get_current_user, None)
    res = client.get("/api/v1/analytics/popular-topics")
    assert res.status_code in (401, 403)

    # Insufficient Role (MEMBER instead of VIEWER/ADMIN - wait, is member insufficient?)
    # Usually ADMIN/VIEWER is required for workspace overview
    # Let's assume MEMBER is insufficient as in earlier tests
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(tenant_a, Role.MEMBER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(tenant_a, Role.MEMBER)
    res = client.get("/api/v1/analytics/popular-topics")
    assert res.status_code == 403

    # Authorized (VIEWER)
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(tenant_a, Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(tenant_a, Role.VIEWER)
    res = client.get("/api/v1/analytics/popular-topics")
    assert res.status_code == 200

@pytest.mark.asyncio
async def test_popular_topics_correctness(client):
    async with TestingSessionLocal() as db:
        tenant_id = f"Workspace-C-{uuid.uuid4()}"

        # Contains stop words ("the", "is", "a"), should be filtered out
        # "running" should stem to "run"
        record = QueryAnalyticsRecord(
            tenant_id=tenant_id,
            correlation_id=str(uuid.uuid4()),
            query_text="the quick fox is running fast",
            outcome="SUCCESS",
            total_duration_ms=100.0,
            created_at=datetime.now(UTC)
        )
        db.add(record)
        await db.commit()

    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(tenant_id, Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(tenant_id, Role.VIEWER)

    res = client.get("/api/v1/analytics/popular-topics")
    assert res.status_code == 200
    data = res.json()["data"]

    topics = [t["topic"] for t in data]
    # 'run', 'quick', 'fox', 'fast' should be here. 'the', 'is' should not.
    assert "run" in topics
    assert "the" not in topics
    assert "is" not in topics

@pytest.mark.asyncio
async def test_unanswered_query_correctness(client):
    async with TestingSessionLocal() as db:
        tenant_id = f"Workspace-D-{uuid.uuid4()}"

        # This one should NOT appear (SUCCESS)
        record1 = QueryAnalyticsRecord(
            tenant_id=tenant_id,
            correlation_id=str(uuid.uuid4()),
            query_text="success_query",
            outcome="SUCCESS",
            total_duration_ms=100.0,
            created_at=datetime.now(UTC)
        )
        # This one should NOT appear (Random unrelated outcome not in unanswered list)
        record2 = QueryAnalyticsRecord(
            tenant_id=tenant_id,
            correlation_id=str(uuid.uuid4()),
            query_text="random_query",
            outcome="OTHER_RANDOM_OUTCOME",
            total_duration_ms=100.0,
            created_at=datetime.now(UTC)
        )
        # This one SHOULD appear
        record3 = QueryAnalyticsRecord(
            tenant_id=tenant_id,
            correlation_id=str(uuid.uuid4()),
            query_text="aborted_query",
            outcome="ABORTED_MAX_RETRIES",
            total_duration_ms=100.0,
            created_at=datetime.now(UTC)
        )
        db.add_all([record1, record2, record3])
        await db.commit()

    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(tenant_id, Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(tenant_id, Role.VIEWER)

    res = client.get("/api/v1/analytics/unanswered-queries")
    assert res.status_code == 200
    data = res.json()["data"]

    queries = [t["query_text"] for t in data]
    assert "aborted_query" in queries
    assert "success_query" not in queries
    assert "random_query" not in queries
