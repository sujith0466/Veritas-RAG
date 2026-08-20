"""Prometheus metrics scraping route.

Provides the production-ready Prometheus metrics scraping endpoint serving
counters, histograms, and gauges in standard Prometheus text format (`CONTENT_TYPE_LATEST`).
"""

from fastapi import APIRouter, Response

from backend.observability.metrics import get_metrics_content_type, get_metrics_output

router = APIRouter(tags=["Monitoring & Metrics"])


@router.get(
    "/metrics",
    summary="Prometheus Metrics Scraper",
    description="Expose production Prometheus text format metrics across all RAGuard AI modules.",
    response_class=Response,
)
@router.get(
    "/api/v1/metrics",
    summary="Prometheus Metrics Scraper (API v1 Alias)",
    description="Expose production Prometheus text format metrics at canonical /api/v1/metrics path.",
    response_class=Response,
)
async def get_prometheus_metrics() -> Response:
    """Return latest system and AI pipeline metrics in Prometheus format."""
    output = get_metrics_output()
    content_type = get_metrics_content_type()
    return Response(content=output, media_type=content_type)
