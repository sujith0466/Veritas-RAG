"""Landing page route for the backend."""

import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.core.config import get_settings

router = APIRouter()

# Setup templates directory
# The templates folder is located at backend/templates
base_dir = os.path.dirname(os.path.dirname(__file__))
templates_dir = os.path.join(base_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)

# Track when the app started for uptime
START_TIME = time.time()


def _format_uptime(seconds: int) -> str:
    """Format seconds into a human-readable uptime string."""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")

    return " ".join(parts)


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_landing_page(request: Request):
    settings = get_settings()

    uptime_seconds = int(time.time() - START_TIME)
    uptime_str = _format_uptime(uptime_seconds)

    commit_hash = os.environ.get("GIT_COMMIT", "development")

    frontend_url = os.environ.get("VITE_API_BASE_URL", "http://localhost:5173").replace(
        "8000", "5173"
    )

    return templates.TemplateResponse(
        request=request,
        name="landing/index.html",
        context={
            "version": settings.app.version,
            "environment": settings.app.environment,
            "uptime": uptime_str,
            "commit_hash": commit_hash,
            "frontend_url": frontend_url,
        },
    )
