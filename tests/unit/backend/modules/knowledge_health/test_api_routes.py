"""Unit tests for Knowledge Health & Lifecycle REST API endpoints (`/api/v1/knowledge-health/*`)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.permissions.rbac import Role
from backend.main import create_app
from backend.modules.knowledge_health.api.dependencies import get_health_orchestrator
from backend.modules.knowledge_health.schemas.health_dto import (
    HealthScanJobDTO,
    MigrationJobDTO,
    ParityAuditDTO,
    PurgeSummaryDTO,
    ScanStatus,
    ScanType,
)


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    orch = MagicMock()
    orch.run_health_scan = AsyncMock(
        return_value=HealthScanJobDTO(
            id=uuid4(),
            tenant_id="test_tenant",
            scan_type=ScanType.ORPHAN_SWEEP,
            status=ScanStatus.COMPLETED,
            orphans_found=5,
            orphans_purged=5,
            stale_chunks_found=0,
            parity_status="SYNCED",
            duration_ms=15.0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    orch.list_scan_jobs = AsyncMock(
        return_value=(
            [
                HealthScanJobDTO(
                    id=uuid4(),
                    tenant_id="test_tenant",
                    scan_type=ScanType.PARITY_AUDIT,
                    status=ScanStatus.COMPLETED,
                    orphans_found=0,
                    orphans_purged=0,
                    stale_chunks_found=0,
                    parity_status="SYNCED (10 == 10)",
                    duration_ms=5.0,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            ],
            1,
        )
    )
    orch.verify_parity = AsyncMock(
        return_value=ParityAuditDTO(
            tenant_id="test_tenant",
            pg_chunk_count=100,
            qdrant_point_count=100,
            is_synced=True,
            parity_status="SYNCED (100 == 100)",
            checked_at=datetime.now(UTC),
        )
    )
    orch.rotate_tenant_embedding_model = AsyncMock(
        return_value=MigrationJobDTO(
            job_id=uuid4(),
            tenant_id="test_tenant",
            target_provider="cohere",
            target_model="embed-english-v3.0",
            stale_chunks_enqueued=25,
            status="PROCESSING",
            started_at=datetime.now(UTC),
        )
    )
    orch.execute_two_phase_purge = AsyncMock(
        return_value=PurgeSummaryDTO(
            document_id=uuid4(),
            tenant_id="test_tenant",
            qdrant_points_deleted=10,
            pg_chunks_deleted=10,
            is_fully_purged=True,
            duration_ms=30.0,
        )
    )
    return orch


@pytest.fixture
def client(app: FastAPI, mock_orchestrator: MagicMock) -> TestClient:
    admin_user = UserContext(
        id=uuid4(),
        supabase_id="sub-admin",
        email="admin@raguard.ai",
        role=Role.ADMIN,
        is_active=True,
        tenant_id="test_tenant",
    )
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_health_orchestrator] = lambda: mock_orchestrator
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_trigger_health_scan_endpoint(client: TestClient, mock_orchestrator: MagicMock) -> None:
    """Test POST /api/v1/knowledge-health/scans initiates scan and returns 200."""
    response = client.post(
        "/api/v1/knowledge-health/scans",
        json={"scan_type": "ORPHAN_SWEEP"},
        headers={"X-Tenant-ID": "test_tenant"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["scan_type"] == "ORPHAN_SWEEP"
    assert data["data"]["orphans_purged"] == 5
    mock_orchestrator.run_health_scan.assert_called_once()


def test_list_health_scans_endpoint(client: TestClient, mock_orchestrator: MagicMock) -> None:
    """Test GET /api/v1/knowledge-health/scans returns paginated jobs."""
    response = client.get("/api/v1/knowledge-health/scans?page=1&size=20", headers={"X-Tenant-ID": "test_tenant"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]["items"]) == 1
    assert data["data"]["total"] == 1


def test_check_parity_endpoint(client: TestClient, mock_orchestrator: MagicMock) -> None:
    """Test GET /api/v1/knowledge-health/parity returns exact 1:1 count status."""
    response = client.get("/api/v1/knowledge-health/parity", headers={"X-Tenant-ID": "test_tenant"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["is_synced"] is True
    assert data["data"]["pg_chunk_count"] == 100


def test_rotate_model_endpoint(client: TestClient, mock_orchestrator: MagicMock) -> None:
    """Test POST /api/v1/knowledge-health/rotate-model initiates shadow migration job."""
    response = client.post(
        "/api/v1/knowledge-health/rotate-model",
        json={"new_provider": "cohere", "new_model": "embed-english-v3.0"},
        headers={"X-Tenant-ID": "test_tenant"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["target_provider"] == "cohere"
    assert data["data"]["stale_chunks_enqueued"] == 25


def test_purge_document_endpoint(client: TestClient, mock_orchestrator: MagicMock) -> None:
    """Test DELETE /api/v1/knowledge-health/purge/{id} executes two-phase purge."""
    doc_id = uuid4()
    response = client.delete(f"/api/v1/knowledge-health/purge/{doc_id}", headers={"X-Tenant-ID": "test_tenant"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["qdrant_points_deleted"] == 10
    assert data["data"]["is_fully_purged"] is True
