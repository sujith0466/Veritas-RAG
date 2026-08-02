import hashlib

from backend.modules.dashboard.schemas.dashboard_dto import (
    AuditExportBundleDTO,
    AuditExportRequestDTO,
)


class AuditExportService:
    async def generate_export(
        self, request: AuditExportRequestDTO
    ) -> AuditExportBundleDTO:
        """
        Mocks the generation of a regulatory compliance export bundle.
        In production, this queries all logs and generates a CSV/JSON bundle in S3.
        """
        dummy_content = (
            f"tenant_id={request.tenant_id},window={request.window},records=500"
        )
        checksum = hashlib.sha256(dummy_content.encode("utf-8")).hexdigest()

        return AuditExportBundleDTO(
            download_url=f"https://storage.raguard.ai/exports/{request.tenant_id}/bundle.zip",
            checksum_sha256=checksum,
            record_count=500,
        )
