"""Unit tests for Stage 6 Targeted Benchmark Fixture Cleanup.

WP-3D: Stage 6 Targeted Cleanup Verification.

Verifies:
1. Targeted cleanup requires explicit host and fails closed on connection/auth errors.
2. Targeted cleanup deletes ONLY sessions prefixed with PERF_FIXTURE_ owned by QA user.
3. Sessions belonging to other users or lacking the fixture prefix are never touched.
4. Run ID filtering restricts deletion to sessions created in a specific test run.
5. Explicit session ID list deletion operates safely.
"""

from unittest.mock import MagicMock
import pytest

from tests.performance.load.locustfile import CleanupError, run_targeted_cleanup


def test_cleanup_missing_host_aborts():
    """Verify that cleanup without an explicit target host aborts."""
    with pytest.raises(CleanupError, match="Target host must be specified"):
        run_targeted_cleanup(host=None)


def test_cleanup_unreachable_host_aborts():
    """Verify that network errors to target host fail closed."""
    mock_client = MagicMock()
    mock_client.post.side_effect = Exception("Connection refused")

    with pytest.raises(CleanupError, match="Target host unreachable"):
        run_targeted_cleanup(host="http://localhost:8001", client=mock_client)


def test_cleanup_auth_failure_aborts():
    """Verify that invalid QA credentials or 401 response aborts cleanup."""
    mock_client = MagicMock()
    login_resp = MagicMock()
    login_resp.status_code = 401
    mock_client.post.return_value = login_resp

    with pytest.raises(CleanupError, match="Authentication failed during cleanup"):
        run_targeted_cleanup(host="http://localhost:8001", client=mock_client)


def test_cleanup_deletes_only_perf_fixture_sessions():
    """Verify that cleanup strictly deletes sessions prefixed with PERF_FIXTURE_."""
    mock_client = MagicMock()

    # Login response
    login_resp = MagicMock()
    login_resp.status_code = 200
    login_resp.json.return_value = {"data": {"access_token": "qa-jwt-token"}}

    # List sessions response
    list_resp = MagicMock()
    list_resp.status_code = 200
    list_resp.json.return_value = {
        "data": [
            {"id": "sess-perf-1", "title": "PERF_FIXTURE_abc123"},
            {"id": "sess-user-prod", "title": "Customer Executive Onboarding Chat"},
            {"id": "sess-perf-2", "title": "PERF_FIXTURE_def456"},
            {"id": "sess-other-chat", "title": "General Inquiries"},
        ]
    }

    # Delete response
    del_resp = MagicMock()
    del_resp.status_code = 204

    def client_post_dispatcher(url, **kwargs):
        if url.endswith("/login"):
            return login_resp
        return MagicMock(status_code=404)

    def client_get_dispatcher(url, **kwargs):
        if url.endswith("/chat/sessions"):
            return list_resp
        return MagicMock(status_code=404)

    def client_del_dispatcher(url, **kwargs):
        return del_resp

    mock_client.post.side_effect = client_post_dispatcher
    mock_client.get.side_effect = client_get_dispatcher
    mock_client.delete.side_effect = client_del_dispatcher

    res = run_targeted_cleanup(host="http://localhost:8001", client=mock_client)

    assert res["status"] == "COMPLETED"
    assert res["deleted_count"] == 2
    assert "sess-perf-1" in res["deleted_sessions"]
    assert "sess-perf-2" in res["deleted_sessions"]
    assert "sess-user-prod" not in res["deleted_sessions"]
    assert "sess-other-chat" not in res["deleted_sessions"]

    # Verify DELETE was called only for the two fixture IDs
    deleted_urls = [call.args[0] for call in mock_client.delete.call_args_list]
    assert "http://localhost:8001/api/v1/chat/sessions/sess-perf-1" in deleted_urls
    assert "http://localhost:8001/api/v1/chat/sessions/sess-perf-2" in deleted_urls
    assert "http://localhost:8001/api/v1/chat/sessions/sess-user-prod" not in deleted_urls
    assert len(deleted_urls) == 2


def test_cleanup_run_id_isolation():
    """Verify that specifying run_id isolates deletions to only that specific run."""
    mock_client = MagicMock()

    login_resp = MagicMock()
    login_resp.status_code = 200
    login_resp.json.return_value = {"data": {"access_token": "qa-jwt-token"}}

    list_resp = MagicMock()
    list_resp.status_code = 200
    list_resp.json.return_value = {
        "data": [
            {"id": "sess-run-101", "title": "PERF_FIXTURE_run101_user1"},
            {"id": "sess-run-102", "title": "PERF_FIXTURE_run102_user1"},
        ]
    }

    del_resp = MagicMock()
    del_resp.status_code = 204

    mock_client.post.return_value = login_resp
    mock_client.get.return_value = list_resp
    mock_client.delete.return_value = del_resp

    res = run_targeted_cleanup(
        host="http://localhost:8001",
        run_id="run101",
        client=mock_client,
    )

    assert res["deleted_count"] == 1
    assert "sess-run-101" in res["deleted_sessions"]
    assert "sess-run-102" not in res["deleted_sessions"]


def test_cleanup_explicit_session_ids():
    """Verify cleanup when explicit list of session IDs is passed."""
    mock_client = MagicMock()

    login_resp = MagicMock()
    login_resp.status_code = 200
    login_resp.json.return_value = {"data": {"access_token": "qa-jwt-token"}}

    del_resp = MagicMock()
    del_resp.status_code = 204

    mock_client.post.return_value = login_resp
    mock_client.delete.return_value = del_resp

    res = run_targeted_cleanup(
        host="http://localhost:8001",
        session_ids=["sess-custom-1", "sess-custom-2"],
        client=mock_client,
    )

    assert res["deleted_count"] == 2
    assert "sess-custom-1" in res["deleted_sessions"]
    assert "sess-custom-2" in res["deleted_sessions"]
    # GET list_sessions should not be called when explicit IDs provided
    mock_client.get.assert_not_called()
