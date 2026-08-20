"""Comprehensive Unit and Integration Test Suite for Prometheus Metrics & Grafana Reconciliation (F14.4)."""

import json
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.observability.monitoring.routes import router as metrics_router
from backend.observability.metrics.prometheus import (
    CELERY_TASK_DURATION_SECONDS,
    CELERY_TASKS_TOTAL,
    ERRORS_TOTAL,
    HALLUCINATION_DETECTIONS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_ACTIVE,
    HTTP_REQUESTS_TOTAL,
    PIPELINE_STAGE_DURATION_SECONDS,
    POST_GEN_RELIABILITY_SCORE,
    PRE_GEN_CONFIDENCE_SCORE,
    QDRANT_ERRORS_TOTAL,
    QDRANT_SEARCH_DURATION_SECONDS,
    QDRANT_SEARCHES_TOTAL,
    QDRANT_UPSERT_DURATION_SECONDS,
    QDRANT_UPSERTS_TOTAL,
    QUERIES_PROCESSED_TOTAL,
    REDIS_HITS_TOTAL,
    REDIS_MISSES_TOTAL,
    REDIS_RECONNECTS_TOTAL,
    REDIS_RETRIES_TOTAL,
    REFLECTION_FAILURES_TOTAL,
    SELF_CORRECTION_RETRIES_TOTAL,
    SSE_ACTIVE_STREAMS,
    STORAGE_BYTES_DOWNLOADED_TOTAL,
    STORAGE_BYTES_UPLOADED_TOTAL,
    STORAGE_DELETES_TOTAL,
    STORAGE_DOWNLOAD_DURATION_SECONDS,
    STORAGE_DOWNLOADS_TOTAL,
    STORAGE_FAILURES_TOTAL,
    STORAGE_UPLOAD_DURATION_SECONDS,
    STORAGE_UPLOADS_TOTAL,
    TOKENS_CONSUMED_TOTAL,
    get_metrics_content_type,
    get_metrics_output,
    record_celery_task,
    record_confidence_metric,
    record_error_metric,
    record_http_request,
    record_qdrant_error,
    record_qdrant_search,
    record_qdrant_upsert,
    record_query_metric,
    record_redis_hit,
    record_redis_miss,
    record_redis_reconnect,
    record_redis_retry,
    record_reflection_metric,
    record_reliability_metric,
    record_retry_metric,
    record_stage_duration,
    record_storage_delete,
    record_storage_download,
    record_storage_failure,
    record_storage_upload,
    record_tokens_consumed,
)


class TestPrometheusMetricsDefinitions:
    """Test suite for metric definitions and recording functions."""

    def test_http_metrics_recording(self) -> None:
        record_http_request("GET", "/api/v1/test", 200, 0.045)
        raw = get_metrics_output().decode("utf-8")
        assert "raguard_http_requests_total" in raw
        assert 'method="GET"' in raw
        assert 'endpoint="/api/v1/test"' in raw
        assert 'status_code="200"' in raw
        assert "raguard_http_request_duration_seconds_bucket" in raw

    def test_pipeline_query_metric_cardinality(self) -> None:
        record_query_metric("tenant-123", "success", 0.35)
        raw = get_metrics_output().decode("utf-8")
        assert "raguard_queries_processed_total" in raw
        assert 'outcome="success"' in raw
        # Ensure unbounded tenant_id is NOT in Prometheus label list
        assert 'tenant_id="tenant-123"' not in raw

    def test_subsystem_redis_metrics(self) -> None:
        record_redis_hit()
        record_redis_miss()
        record_redis_retry()
        record_redis_reconnect()
        raw = get_metrics_output().decode("utf-8")
        assert "raguard_redis_hits_total" in raw
        assert "raguard_redis_misses_total" in raw
        assert "raguard_redis_retries_total" in raw
        assert "raguard_redis_reconnects_total" in raw

    def test_subsystem_qdrant_metrics(self) -> None:
        record_qdrant_search(0.012)
        record_qdrant_upsert(0.045)
        record_qdrant_error("search")
        raw = get_metrics_output().decode("utf-8")
        assert "raguard_qdrant_searches_total" in raw
        assert "raguard_qdrant_search_duration_seconds" in raw
        assert "raguard_qdrant_upserts_total" in raw
        assert "raguard_qdrant_upsert_duration_seconds" in raw
        assert "raguard_qdrant_errors_total" in raw

    def test_subsystem_storage_metrics(self) -> None:
        record_storage_upload(1024, 0.025)
        record_storage_download(2048, 0.015)
        record_storage_delete()
        record_storage_failure("upload")
        raw = get_metrics_output().decode("utf-8")
        assert "raguard_storage_uploads_total" in raw
        assert "raguard_storage_bytes_uploaded_total" in raw
        assert "raguard_storage_downloads_total" in raw
        assert "raguard_storage_bytes_downloaded_total" in raw
        assert "raguard_storage_deletes_total" in raw
        assert "raguard_storage_failures_total" in raw

    def test_token_accounting_metric(self) -> None:
        record_tokens_consumed("gemini-1.5-pro", "prompt", 350)
        record_tokens_consumed("gemini-1.5-pro", "completion", 120)
        raw = get_metrics_output().decode("utf-8")
        assert "raguard_tokens_consumed_total" in raw
        assert 'model="gemini-1.5-pro"' in raw
        assert 'type="prompt"' in raw

    def test_celery_task_metric(self) -> None:
        record_celery_task("ingestion.process_document", "success", 1.25)
        raw = get_metrics_output().decode("utf-8")
        assert "raguard_celery_tasks_total" in raw
        assert 'task_name="ingestion.process_document"' in raw
        assert 'status="success"' in raw
        assert "raguard_celery_task_duration_seconds" in raw


class TestPrometheusScrapeEndpoints:
    """Test suite for HTTP scrape endpoints."""

    @pytest.fixture
    def test_app(self) -> FastAPI:
        test_app = FastAPI()
        test_app.include_router(metrics_router)
        return test_app

    def test_metrics_endpoint_standard_path(self, test_app: FastAPI) -> None:
        client = TestClient(test_app)
        res = client.get("/metrics")
        assert res.status_code == 200
        assert "text/plain" in res.headers["content-type"]
        assert "raguard_http_requests_total" in res.text

    def test_metrics_endpoint_api_v1_alias(self, test_app: FastAPI) -> None:
        client = TestClient(test_app)
        res = client.get("/api/v1/metrics")
        assert res.status_code == 200
        assert "text/plain" in res.headers["content-type"]
        assert "raguard_http_requests_total" in res.text


class TestGrafanaDashboardPromQLReconciliation:
    """Test suite ensuring all PromQL queries in Grafana dashboard reference real metrics."""

    def test_all_dashboard_promql_metrics_exist_in_prometheus_registry(self) -> None:
        dashboard_path = Path("infrastructure/monitoring/grafana/dashboards/raguard_enterprise_dashboard.json")
        assert dashboard_path.exists()

        with open(dashboard_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        panels = data.get("panels", [])
        assert len(panels) >= 10

        # Collect all metric names from PromQL expressions
        metric_pattern = re.compile(r"\b(raguard_[a-zA-Z0-9_]+)\b")
        dashboard_metrics = set()

        for panel in panels:
            targets = panel.get("targets", [])
            for target in targets:
                expr = target.get("expr", "")
                matches = metric_pattern.findall(expr)
                for m in matches:
                    # Strip standard histogram suffixes for base verification if needed
                    base_m = m[:-7] if m.endswith("_bucket") else m
                    dashboard_metrics.add(base_m)

        raw_metrics = get_metrics_output().decode("utf-8")

        # Verify each metric mentioned in the dashboard is in the Prometheus output
        for m in dashboard_metrics:
            assert m in raw_metrics, f"Dashboard metric '{m}' is not exported by Prometheus registry!"
