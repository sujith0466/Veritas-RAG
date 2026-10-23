"""Unit tests for Load Testing Preflight Isolation & Safeguards.

WP-3D: Load-Test Isolation & Safety Preflight.

Verifies:
1. Missing target opt-in aborts before traffic.
2. Missing or unverified mock-provider attestation aborts.
3. Production or unknown environment aborts.
4. Missing disposable-store confirmation aborts.
5. Fully valid preflight permits harness initialization without starting a load test.
"""

from unittest.mock import MagicMock
import pytest

from tests.performance.load.config import LoadTestConfig
from tests.performance.load.preflight import (
    MalformedTargetURLError,
    MissingDisposableStoreConfirmationError,
    MissingOperatorMockConfirmationError,
    MissingTargetOptInError,
    PreflightError,
    ServerEmbeddingIsolationError,
    ServerEnvironmentRejectionError,
    ServerProviderAttestationError,
    TargetMismatchError,
    run_preflight_checks,
    validate_operator_opt_ins,
    verify_server_embedding_isolation,
    verify_server_environment,
    verify_server_mock_provider_attestation,
)


def test_missing_target_opt_in_aborts():
    """Verify missing target host aborts before traffic (no silent default)."""
    cfg = LoadTestConfig(
        host=None,
        confirm_target_url=False,
        confirm_disposable_stores=True,
        confirm_mock_provider=True,
    )
    with pytest.raises(MissingTargetOptInError, match="Target host opt-in required"):
        validate_operator_opt_ins(cfg)


def test_unconfirmed_target_url_aborts():
    """Verify target URL without explicit confirmation aborts."""
    cfg = LoadTestConfig(
        host="http://localhost:8000",
        confirm_target_url=False,
        confirm_disposable_stores=True,
        confirm_mock_provider=True,
    )
    with pytest.raises(MissingTargetOptInError, match="must explicitly confirm intended target URL"):
        validate_operator_opt_ins(cfg)


def test_missing_disposable_store_confirmation_aborts():
    """Verify missing disposable backing store confirmation aborts."""
    cfg = LoadTestConfig(
        host="http://127.0.0.1:8000",
        confirm_target_url=True,
        confirm_disposable_stores=False,
        confirm_mock_provider=True,
    )
    with pytest.raises(
        MissingDisposableStoreConfirmationError,
        match="must explicitly confirm dedicated, disposable, non-production database",
    ):
        validate_operator_opt_ins(cfg)


def test_missing_operator_mock_confirmation_aborts():
    """Verify missing operator mock LLM provider confirmation aborts."""
    cfg = LoadTestConfig(
        host="http://127.0.0.1:8000",
        confirm_target_url=True,
        confirm_disposable_stores=True,
        confirm_mock_provider=False,
    )
    with pytest.raises(
        MissingOperatorMockConfirmationError,
        match="must explicitly confirm mock LLM provider intention",
    ):
        validate_operator_opt_ins(cfg)


def test_server_environment_rejection_production():
    """Verify target server reporting production environment immediately aborts."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "version": "1.0.0",
        "environment": "production",
    }
    mock_client.get.return_value = mock_response

    with pytest.raises(ServerEnvironmentRejectionError, match="strictly prohibited"):
        verify_server_environment("http://target-api:8000", client=mock_client)


def test_server_environment_rejection_unknown():
    """Verify target server reporting unknown environment aborts."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "version": "1.0.0",
        "environment": "corp-finance-dmz",
    }
    mock_client.get.return_value = mock_response

    with pytest.raises(ServerEnvironmentRejectionError, match="unknown or uncertified environment"):
        verify_server_environment("http://target-api:8000", client=mock_client)


def test_server_environment_acceptance_development():
    """Verify development environment is accepted."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "version": "1.0.0",
        "environment": "development",
    }
    mock_client.get.return_value = mock_response

    env = verify_server_environment("http://target-api:8000", client=mock_client)
    assert env == "development"


def test_missing_mock_provider_attestation_without_admin_token_aborts():
    """Verify that unverified client-side claims without server attestation credentials abort."""
    with pytest.raises(
        ServerProviderAttestationError,
        match="cannot safely attest to MOCK_LLM_PROVIDER configuration through an existing trusted mechanism",
    ):
        verify_server_mock_provider_attestation(
            host="http://target-api:8000",
            admin_token=None,
        )


def test_mock_provider_attestation_fails_when_live_fallback_present():
    """Verify attestation aborts if server indicates active live fallback routes alongside mock."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "version": "1.0.0",
        "dependencies": [
            {
                "name": "llm_provider",
                "status": "healthy",
                "info": {
                    "provider_status": "healthy",
                    "circuit_states": {
                        "mock": "closed",
                        "openrouter": "closed",  # Active fallback violates strict mock isolation
                    },
                },
            }
        ],
    }
    mock_client.get.return_value = mock_response

    with pytest.raises(ServerProviderAttestationError, match="indicate active fallback routes"):
        verify_server_mock_provider_attestation(
            host="http://target-api:8000",
            admin_token="valid-admin-token",
            client=mock_client,
        )


def test_mock_provider_attestation_fails_when_mock_not_active():
    """Verify attestation aborts if server reports standard live providers without mock."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "version": "1.0.0",
        "dependencies": [
            {
                "name": "llm_provider",
                "status": "healthy",
                "info": {
                    "provider_status": "healthy",
                    "circuit_states": {
                        "openrouter": "closed",
                        "gemini": "closed",
                    },
                },
            }
        ],
    }
    mock_client.get.return_value = mock_response

    with pytest.raises(ServerProviderAttestationError, match="do not contain 'mock'"):
        verify_server_mock_provider_attestation(
            host="http://target-api:8000",
            admin_token="valid-admin-token",
            client=mock_client,
        )


def test_mock_provider_attestation_success():
    """Verify attestation succeeds when server confirms exclusive mock provider isolation."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "healthy",
        "version": "1.0.0",
        "dependencies": [
            {
                "name": "llm_provider",
                "status": "healthy",
                "info": {
                    "provider_status": "healthy",
                    "circuit_states": {
                        "mock": "closed",
                    },
                },
            }
        ],
    }
    mock_client.get.return_value = mock_response

    assert (
        verify_server_mock_provider_attestation(
            host="http://target-api:8000",
            admin_token="valid-admin-token",
            client=mock_client,
        )
        is True
    )


def test_fully_valid_preflight_permits_harness_initialization_without_load():
    """Verify that a fully valid preflight succeeds and returns attestation data without running load."""
    cfg = LoadTestConfig(
        host="http://target-api:8000",
        confirm_target_url=True,
        confirm_disposable_stores=True,
        confirm_mock_provider=True,
        admin_token="valid-admin-token",
    )

    mock_client = MagicMock()

    # Health probe
    health_resp = MagicMock()
    health_resp.status_code = 200
    health_resp.json.return_value = {
        "status": "healthy",
        "version": "1.0.0",
        "environment": "development",
    }

    # Detailed health probe
    detailed_resp = MagicMock()
    detailed_resp.status_code = 200
    detailed_resp.json.return_value = {
        "status": "healthy",
        "version": "1.0.0",
        "dependencies": [
            {
                "name": "llm_provider",
                "status": "healthy",
                "info": {
                    "provider_status": "healthy",
                    "circuit_states": {
                        "mock": "closed",
                    },
                },
            }
        ],
    }

    def client_get_dispatcher(url, **kwargs):
        if url.endswith("/health"):
            return health_resp
        elif url.endswith("/detailed"):
            return detailed_resp
        return MagicMock(status_code=404)

    mock_client.get.side_effect = client_get_dispatcher

    result = run_preflight_checks(cfg, client=mock_client)

    assert result["preflight_passed"] is True
    assert result["target_host"] == "http://target-api:8000"
    assert result["environment"] == "development"
    assert result["mock_attested"] is True


def test_target_mismatch_between_cli_and_env_aborts():
    """Verify that disagreement between Locust --host and PERF_TARGET_HOST fails closed."""
    cfg = LoadTestConfig(
        host="http://localhost:8001",
        confirm_target_url=True,
        confirm_disposable_stores=True,
        confirm_mock_provider=True,
    )
    with pytest.raises(TargetMismatchError, match="Target mismatch detected"):
        validate_operator_opt_ins(cfg, cli_host="http://localhost:8000")


def test_matching_cli_and_env_targets_succeed():
    """Verify that matching --host and PERF_TARGET_HOST pass validation."""
    cfg = LoadTestConfig(
        host="http://localhost:8001/",
        confirm_target_url=True,
        confirm_disposable_stores=True,
        confirm_mock_provider=True,
    )
    effective = validate_operator_opt_ins(cfg, cli_host="http://localhost:8001")
    assert effective == "http://localhost:8001"


def test_malformed_target_url_aborts():
    """Verify that a malformed target URL lacking http/https scheme aborts."""
    cfg = LoadTestConfig(
        host="not-a-valid-url",
        confirm_target_url=True,
        confirm_disposable_stores=True,
        confirm_mock_provider=True,
    )
    with pytest.raises(MalformedTargetURLError, match="malformed"):
        validate_operator_opt_ins(cfg)


def test_mock_provider_circuit_open_aborts():
    """Verify that OPEN circuit breaker for mock provider causes preflight abort."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "unhealthy",
        "dependencies": [
            {
                "name": "llm_provider",
                "info": {
                    "circuit_states": {
                        "mock": "OPEN",
                    },
                },
            }
        ],
    }
    mock_client.get.return_value = mock_resp

    with pytest.raises(ServerProviderAttestationError, match="circuit breaker is OPEN"):
        verify_server_mock_provider_attestation(
            "http://target-api:8000",
            admin_token="valid-admin-token",
            client=mock_client,
        )


def test_mock_provider_circuit_half_open_accepted():
    """Verify that HALF_OPEN canary trial state for mock provider is accepted."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "healthy",
        "dependencies": [
            {
                "name": "llm_provider",
                "info": {
                    "circuit_states": {
                        "mock": "HALF_OPEN",
                    },
                },
            }
        ],
    }
    mock_client.get.return_value = mock_resp

    res = verify_server_mock_provider_attestation(
        "http://target-api:8000",
        admin_token="valid-admin-token",
        client=mock_client,
    )
    assert res is True


def test_server_embedding_isolation_external_provider_aborts():
    """Verify that live external embedding provider (OpenAI/Cohere) aborts without override."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "degraded",
        "dependencies": [
            {
                "name": "embedding_provider",
                "info": {
                    "default_provider": "openai",
                    "is_isolated": False,
                },
            }
        ],
    }
    mock_client.get.return_value = mock_resp

    with pytest.raises(ServerEmbeddingIsolationError, match="live external embedding provider"):
        verify_server_embedding_isolation(
            "http://target-api:8000",
            admin_token="valid-admin-token",
            client=mock_client,
            allow_unverified=False,
        )


def test_server_embedding_isolation_local_provider_passes():
    """Verify that local/mock embedding provider passes preflight verification."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "healthy",
        "dependencies": [
            {
                "name": "embedding_provider",
                "info": {
                    "default_provider": "local",
                    "is_isolated": True,
                },
            }
        ],
    }
    mock_client.get.return_value = mock_resp

    res = verify_server_embedding_isolation(
        "http://target-api:8000",
        admin_token="valid-admin-token",
        client=mock_client,
        allow_unverified=False,
    )
    assert res is True
