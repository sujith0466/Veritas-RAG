from typing import Any

from pydantic import BaseModel


class AppBundleDTO(BaseModel):
    bundle_id: str
    name: str
    version: str
    description: str
    author: str
    payload: dict[str, Any]
    signature_hash: str


class BundleInstallRequestDTO(BaseModel):
    tenant_id: str
    bundle_id: str
    version: str


class BundleInstallStatusDTO(BaseModel):
    status: str
    message: str
    applied_components: list[str]
