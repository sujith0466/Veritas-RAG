from fastapi import APIRouter

from backend.modules.marketplace.schemas.marketplace_dto import (
    AppBundleDTO, BundleInstallRequestDTO, BundleInstallStatusDTO)

router = APIRouter(prefix="/marketplace/v1", tags=["Marketplace"])


@router.get("/bundles", response_model=list[AppBundleDTO])
async def list_bundles():
    return [
        AppBundleDTO(
            bundle_id="finance-compliance-pack",
            name="Financial Services Baseline",
            version="1.0.0",
            description="Strict PII redaction and aggressive confidence thresholds.",
            author="raguard-coe",
            payload={},
            signature_hash="sha256-mock-hash",
        )
    ]


@router.post("/install", response_model=BundleInstallStatusDTO)
async def install_bundle(req: BundleInstallRequestDTO):
    return BundleInstallStatusDTO(
        status="SUCCESS",
        message=f"Bundle {req.bundle_id} installed successfully",
        applied_components=["security_policies", "governor_thresholds"],
    )
