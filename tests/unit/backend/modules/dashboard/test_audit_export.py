import pytest

from backend.modules.dashboard.schemas.dashboard_dto import AuditExportRequestDTO
from backend.modules.dashboard.services.audit_export import AuditExportService


@pytest.mark.asyncio
async def test_audit_export():
    svc = AuditExportService()
    req = AuditExportRequestDTO(tenant_id="t1", window="24h")
    bundle = await svc.generate_export(req)

    assert bundle.record_count == 500
    assert bundle.download_url == "https://storage.raguard.ai/exports/t1/bundle.zip"
    assert len(bundle.checksum_sha256) == 64
