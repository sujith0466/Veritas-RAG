import os
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pathlib import Path
from backend.core.dependencies.auth import get_optional_user
from backend.core.auth.context import UserContext

router = APIRouter(prefix="/storage", tags=["storage"])

# This should match LocalStorageProvider's base_path
STORAGE_DIR = Path("data/storage")


@router.get("/{bucket}/{filename:path}")
async def get_file(
    bucket: str, 
    filename: str, 
    user: UserContext | None = Depends(get_optional_user)
):
    """Serve files uploaded to local storage."""
    
    # Authorization checks
    if bucket != "avatars":
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required for this bucket")
            
        # Tenant isolation for documents bucket
        if bucket == "documents":
            parts = filename.replace("\\", "/").split("/")
            if not parts or parts[0] != user.tenant_id:
                raise HTTPException(status_code=403, detail="Cross-tenant access forbidden")

    file_path = STORAGE_DIR / bucket / filename
    
    # Basic security check to prevent directory traversal
    try:
        if not file_path.resolve().is_relative_to(STORAGE_DIR.resolve()):
            raise HTTPException(status_code=403, detail="Forbidden")
    except ValueError:
         raise HTTPException(status_code=403, detail="Forbidden")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)
