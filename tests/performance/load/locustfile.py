"""Locust Headless Load Testing Harness for Veritas RAG.

WP-3D: TSK-3D-02 — Locust Load Testing Harness.

Implements Scenarios A, B, and C with full TTFT and stream-drop instrumentation:
- Scenario A: Authenticated user login and session refresh.
- Scenario B: Chat session SSE stream querying knowledge base with TTFT measurement.
- Scenario C: Document metadata and ingestion status polling.
"""

import json
import logging
import os
import time
from typing import Any
import uuid

import httpx
try:
    from locust import HttpUser, between, events, task
    from locust.runners import MasterRunner
except ImportError:
    # Graceful fallback when locust is not installed in the local environment (e.g. during unit tests)
    class HttpUser:  # type: ignore[no-redef]
        pass

    def between(min_wait: float = 1.0, max_wait: float = 3.0):  # type: ignore[misc]
        return lambda: min_wait

    def task(weight: int = 1):  # type: ignore[misc]
        return lambda func: func

    class _MockEventHook:
        def add_listener(self, func):
            return func

    class _MockEvents:
        test_start = _MockEventHook()
        request = _MockEventHook()
        test_stop = _MockEventHook()

    events = _MockEvents()  # type: ignore[assignment]
    MasterRunner = type("MasterRunner", (), {})  # type: ignore[misc,assignment]

from tests.performance.load.config import (
    LoadTestConfig,
    calculate_percentiles_nist_type7,
    evaluate_load_benchmark_results,
)
from tests.performance.load.preflight import run_preflight_checks

logger = logging.getLogger("veritas.loadtest")

# Global metric accumulators
_raw_rest_latencies: list[float] = []
_raw_ttft_latencies: list[float] = []
_total_sse_streams: int = 0
_dropped_sse_streams: int = 0
_http_5xx_count: int = 0
_total_requests: int = 0
_test_start_time: float = 0.0


@events.test_start.add_listener
def on_test_start(environment: Any, **kwargs: Any) -> None:
    """Execute preflight safety checks, initialize test start timestamp, and clear metric accumulators."""
    global _test_start_time, _raw_rest_latencies, _raw_ttft_latencies
    global _total_sse_streams, _dropped_sse_streams, _http_5xx_count, _total_requests

    cli_host = environment.host
    env_host = os.getenv("PERF_TARGET_HOST")
    target_host = cli_host or env_host
    config = LoadTestConfig(host=target_host)

    # Fail-closed safety preflight before generating any load traffic
    try:
        run_preflight_checks(config, cli_host=cli_host)
        if not environment.host and target_host:
            environment.host = target_host
    except Exception as exc:
        logger.critical("SAFETY PREFLIGHT FAILED: Halting Locust test runner immediately: %s", exc)
        if environment.runner:
            environment.runner.quit()
        raise

    _test_start_time = time.time()
    _raw_rest_latencies.clear()
    _raw_ttft_latencies.clear()
    _total_sse_streams = 0
    _dropped_sse_streams = 0
    _http_5xx_count = 0
    _total_requests = 0
    logger.info("Veritas RAG load test initialized. Target: %s", environment.host)


@events.request.add_listener
def on_request(
    request_type: str,
    name: str,
    response_time: float,
    response_length: int,
    exception: Any,
    context: dict[str, Any],
    **kwargs: Any,
) -> None:
    """Collect raw request metrics after discarding the 60s warm-up window."""
    global _raw_rest_latencies, _http_5xx_count, _total_requests

    config = LoadTestConfig()
    elapsed_since_start = time.time() - _test_start_time

    # Discard 60s warm-up window in accordance with Master Plan Section 7.1
    if elapsed_since_start < config.warmup_seconds:
        return

    _total_requests += 1

    if exception:
        exc_str = str(exception)
        if "500" in exc_str or "502" in exc_str or "503" in exc_str:
            _http_5xx_count += 1
    else:
        _raw_rest_latencies.append(response_time)


@events.test_stop.add_listener
def on_test_stop(environment: Any, **kwargs: Any) -> None:
    """Evaluate and log the final NIST Type 7 benchmark scorecard."""
    if isinstance(environment.runner, MasterRunner):
        return  # Only log summary on worker or local runner

    summary = evaluate_load_benchmark_results(
        rest_latencies_ms=_raw_rest_latencies,
        ttft_latencies_ms=_raw_ttft_latencies,
        total_streams=_total_sse_streams,
        dropped_streams=_dropped_sse_streams,
        http_5xx_count=_http_5xx_count,
        total_requests=_total_requests,
    )

    logger.info("=================================================================")
    logger.info("VERITAS RAG — WP-3D CAPACITY & LOAD BENCHMARK SCORECARD")
    logger.info("=================================================================")
    logger.info("Overall Verdict: %s", "PASSED" if summary["overall_pass"] else "FAILED")
    logger.info("Valid Post-Warmup Samples: %d (Min Required: 500)", summary["sample_count"])
    logger.info("REST Latencies (NIST Type 7): %s", summary["rest_percentiles"])
    logger.info("Chat TTFT (NIST Type 7): %s", summary["ttft_percentiles"])
    logger.info("Stream Drop Rate: %.2f%%", float(summary["stream_drop_rate"]) * 100.0)
    logger.info("HTTP 5xx Rate: %.2f%%", float(summary["http_5xx_rate"]) * 100.0)
    logger.info("=================================================================")


class VeritasUser(HttpUser):
    """Simulates an enterprise knowledge worker interacting with Veritas RAG.

    Scenario Mutating vs Read-Only Classification:
    - Auth & Startup:
      * POST /api/v1/auth/login: Mutates login audit logs and session tracking.
      * GET /api/v1/workspaces: Verified READ-ONLY.
    - Scenario A:
      * POST /api/v1/auth/refresh: Mutates token state and rotation tables.
      * GET /api/v1/users/me: Verified READ-ONLY.
    - Scenario B:
      * POST /api/v1/chat/sessions: MUTATING — inserts chat_sessions record.
      * POST /api/v1/chat/sessions/{id}/stream: MUTATING — inserts chat_messages records.
    - Scenario C:
      * GET /api/v1/documents: Verified READ-ONLY — executes SELECT query only,
        with zero file uploads, zero MinIO writes, and zero Celery task dispatches.
    """

    wait_time = between(1.0, 3.0)

    def on_start(self) -> None:
        """Authenticate user and obtain JWT tokens before executing load tasks."""
        self.config = LoadTestConfig()
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.workspace_id: str | None = None
        self.session_id: str | None = None
        self.fixture_session_ids: list[str] = []

        self._authenticate()

    def on_stop(self) -> None:
        """Safely clean up only test-created fixture sessions upon virtual user teardown."""
        if not self.config.enable_fixture_cleanup or not self.access_token:
            return

        for sid in list(self.fixture_session_ids):
            try:
                self.client.delete(
                    f"/api/v1/chat/sessions/{sid}",
                    name="DELETE /api/v1/chat/sessions/{id} (cleanup)",
                )
            except Exception as exc:
                logger.warning("Failed to clean up test fixture session %s: %s", sid, exc)
        self.fixture_session_ids.clear()

    def _authenticate(self) -> None:
        """Execute login request and configure Authorization header."""
        payload = {
            "email": self.config.qa_email,
            "password": self.config.qa_password,
        }
        with self.client.post(
            "/api/v1/auth/login",
            json=payload,
            name="POST /api/v1/auth/login",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json().get("data", {})
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                if self.access_token:
                    self.client.headers["Authorization"] = f"Bearer {self.access_token}"
                response.success()
            else:
                response.failure(f"Authentication failed with status {response.status_code}")

        # Fetch current workspace
        if self.access_token:
            with self.client.get(
                "/api/v1/workspaces",
                name="GET /api/v1/workspaces",
                catch_response=True,
            ) as ws_response:
                if ws_response.status_code == 200:
                    ws_data = ws_response.json().get("data", [])
                    if ws_data and isinstance(ws_data, list):
                        self.workspace_id = ws_data[0].get("id")
                    ws_response.success()
                else:
                    ws_response.failure(f"Fetch workspaces failed: {ws_response.status_code}")

    @task(3)
    def scenario_a_auth_and_session(self) -> None:
        """Scenario A: Authenticated user session refresh and profile lookup."""
        if not self.refresh_token:
            return

        # 1. Refresh Token
        with self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": self.refresh_token},
            name="POST /api/v1/auth/refresh",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                data = response.json().get("data", {})
                new_token = data.get("access_token")
                if new_token:
                    self.access_token = new_token
                    self.client.headers["Authorization"] = f"Bearer {self.access_token}"
                response.success()
            else:
                response.failure(f"Token refresh failed: {response.status_code}")

        # 2. Get User Profile
        self.client.get(
            "/api/v1/users/me",
            name="GET /api/v1/users/me",
        )

    @task(5)
    def scenario_b_chat_stream_query(self) -> None:
        """Scenario B: Authenticated chat session creation and SSE streaming query."""
        global _total_sse_streams, _dropped_sse_streams, _raw_ttft_latencies

        if not self.access_token:
            return

        # 1. Create session if not already existing
        if not self.session_id:
            fixture_title = f"PERF_FIXTURE_{uuid.uuid4().hex[:8]}"
            payload = {"title": fixture_title}
            with self.client.post(
                "/api/v1/chat/sessions",
                json=payload,
                name="POST /api/v1/chat/sessions",
                catch_response=True,
            ) as session_resp:
                if session_resp.status_code in (200, 201):
                    self.session_id = session_resp.json().get("data", {}).get("id")
                    if self.session_id:
                        self.fixture_session_ids.append(self.session_id)
                    session_resp.success()
                else:
                    session_resp.failure("Failed to create chat session")
                    return

        # 2. Execute SSE Streaming Request
        _total_sse_streams += 1
        stream_start = time.perf_counter()
        first_chunk_received = False
        stream_dropped = False

        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }
        stream_payload = {
            "query": "What are the compliance and resilience requirements for Veritas RAG?",
            "workspace_id": self.workspace_id,
        }

        try:
            with self.client.post(
                f"/api/v1/chat/sessions/{self.session_id}/stream",
                json=stream_payload,
                headers=headers,
                stream=True,
                name="POST /api/v1/chat/sessions/{id}/stream",
                catch_response=True,
            ) as stream_resp:
                if stream_resp.status_code == 200:
                    for chunk in stream_resp.iter_lines():
                        if not chunk:
                            continue
                        if not first_chunk_received:
                            first_chunk_received = True
                            ttft = (time.perf_counter() - stream_start) * 1000.0  # ms
                            elapsed_since_start = time.time() - _test_start_time
                            if elapsed_since_start >= self.config.warmup_seconds:
                                _raw_ttft_latencies.append(ttft)
                    stream_resp.success()
                elif stream_resp.status_code == 503:
                    # Concurrency limiter shed Request 51
                    stream_resp.success()
                else:
                    stream_dropped = True
                    _dropped_sse_streams += 1
                    stream_resp.failure(f"Streaming failed with status {stream_resp.status_code}")
        except Exception as exc:
            stream_dropped = True
            _dropped_sse_streams += 1
            logger.error("SSE stream connection aborted unexpectedly: %s", exc)

    @task(2)
    def scenario_c_document_ingestion_polling(self) -> None:
        """Scenario C: Document list and ingestion status polling."""
        if not self.access_token:
            return

        with self.client.get(
            "/api/v1/documents",
            name="GET /api/v1/documents",
            catch_response=True,
        ) as doc_resp:
            if doc_resp.status_code == 200:
                doc_resp.success()
            else:
                doc_resp.failure(f"List documents failed: {doc_resp.status_code}")


class CleanupError(Exception):
    """Raised when benchmark fixture cleanup fails or cannot be executed safely."""


def run_targeted_cleanup(
    host: str | None = None,
    qa_email: str | None = None,
    qa_password: str | None = None,
    run_id: str | None = None,
    session_ids: list[str] | tuple[str, ...] | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Safely delete only test-created benchmark sessions for the authenticated QA user.

    Strict ownership and safety isolation:
    1. Authenticates as the configured QA user (qa@raguard.ai).
    2. Deletions execute exclusively via authenticated DELETE /api/v1/chat/sessions/{id}.
       The backend repository enforces tenant and user ownership matching the JWT token.
    3. If explicit session_ids are provided:
       Deletes only those specific session IDs.
    4. If session_ids is None:
       Fetches GET /api/v1/chat/sessions (which returns only sessions owned by the QA user).
       Filters sessions whose title matches 'PERF_FIXTURE_' (and run_id if specified).
    5. Never touches sessions of other users or tenants.
    6. Fail-closed: raises CleanupError if authentication fails or target cannot be reached.
    """
    config = LoadTestConfig(host=host) if host else LoadTestConfig()
    target_host = host or config.host
    if not target_host:
        raise CleanupError("Target host must be specified for targeted cleanup.")

    email = qa_email or config.qa_email
    password = qa_password or config.qa_password
    clean_host = target_host.rstrip("/")

    logger.info("Executing targeted benchmark fixture cleanup for %s (email: %s)", clean_host, email)

    should_close_client = False
    if client is None:
        client = httpx.Client(timeout=10.0)
        should_close_client = True

    deleted_sessions: list[str] = []
    failed_sessions: list[str] = []

    try:
        # 1. Authenticate as QA User
        login_url = f"{clean_host}/api/v1/auth/login"
        try:
            login_resp = client.post(login_url, json={"email": email, "password": password})
        except Exception as exc:
            raise CleanupError(f"Target host unreachable during cleanup: {exc}") from exc

        if login_resp.status_code != 200:
            raise CleanupError(f"Authentication failed during cleanup: HTTP {login_resp.status_code}")

        token_data = login_resp.json().get("data", {})
        access_token = token_data.get("access_token")
        if not access_token:
            raise CleanupError("No access token returned during cleanup authentication.")

        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # 2. Determine target session IDs
        target_ids: list[str] = []
        if session_ids:
            target_ids = list(session_ids)
        else:
            # Fetch QA user's sessions
            list_url = f"{clean_host}/api/v1/chat/sessions"
            try:
                list_resp = client.get(list_url, headers=auth_headers)
            except Exception as exc:
                raise CleanupError(f"Failed to query chat sessions during cleanup: {exc}") from exc

            if list_resp.status_code != 200:
                raise CleanupError(f"Failed to list chat sessions during cleanup: HTTP {list_resp.status_code}")

            raw_sessions = list_resp.json().get("data", [])
            expected_prefix = f"PERF_FIXTURE_{run_id}" if run_id else "PERF_FIXTURE_"
            for s in raw_sessions:
                if isinstance(s, dict):
                    title = str(s.get("title", ""))
                    sid = s.get("id")
                    if title.startswith(expected_prefix) and sid:
                        target_ids.append(sid)

        # 3. Safely delete matching sessions
        for sid in target_ids:
            del_url = f"{clean_host}/api/v1/chat/sessions/{sid}"
            try:
                del_resp = client.delete(del_url, headers=auth_headers)
                if del_resp.status_code in (200, 204):
                    deleted_sessions.append(sid)
                else:
                    failed_sessions.append(sid)
                    logger.warning("Failed to delete fixture session %s: HTTP %s", sid, del_resp.status_code)
            except Exception as exc:
                failed_sessions.append(sid)
                logger.warning("Exception deleting fixture session %s: %s", sid, exc)

        logger.info(
            "Targeted fixture cleanup completed: deleted=%d, failed=%d",
            len(deleted_sessions),
            len(failed_sessions),
        )
        return {
            "status": "COMPLETED",
            "deleted_count": len(deleted_sessions),
            "deleted_sessions": deleted_sessions,
            "failed_count": len(failed_sessions),
            "failed_sessions": failed_sessions,
        }
    finally:
        if should_close_client:
            client.close()
