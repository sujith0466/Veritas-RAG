"""Fail-Closed Preflight Safeguards for Locust Load Testing Harness.

WP-3D: Load-Test Isolation & Safety Preflight.

Enforces strict preflight checks before any simulated-user traffic is generated:
1. Explicit operator target host opt-in (no silent defaults to localhost:8000).
2. Explicit operator confirmation of target URL.
3. Explicit operator confirmation of dedicated, disposable non-production backing stores.
4. Explicit operator confirmation of mock LLM provider intention.
5. Server-side environment verification (/health) strictly rejecting production or unknown environments.
6. Server-side mock provider attestation verification (refusing unverified client-side claims).
"""

from typing import Any
import httpx
import structlog

from tests.performance.load.config import LoadTestConfig

logger = structlog.get_logger(__name__)


class PreflightError(Exception):
    """Base exception for load testing preflight safety aborts."""


class MissingTargetOptInError(PreflightError):
    """Raised when target host is not explicitly specified (no silent defaults)."""


class MissingDisposableStoreConfirmationError(PreflightError):
    """Raised when operator has not explicitly confirmed disposable non-production stores."""


class MissingOperatorMockConfirmationError(PreflightError):
    """Raised when operator has not explicitly confirmed mock provider intention."""


class ServerEnvironmentRejectionError(PreflightError):
    """Raised when target server environment is production or unknown."""


class ServerProviderAttestationError(PreflightError):
    """Raised when target server cannot safely attest to MOCK_LLM_PROVIDER configuration."""


def validate_operator_opt_ins(config: LoadTestConfig) -> None:
    """Validate explicit operator opt-ins and confirmations before network traffic.

    Args:
        config: LoadTestConfig instance.

    Raises:
        MissingTargetOptInError: If target host is missing or unconfirmed.
        MissingDisposableStoreConfirmationError: If disposable store confirmation is missing.
        MissingOperatorMockConfirmationError: If mock provider confirmation is missing.
    """
    # 1. Target Host Opt-in
    if not config.host or not config.host.strip():
        raise MissingTargetOptInError(
            "CRITICAL SAFETY ABORT: Target host opt-in required. "
            "Set PERF_TARGET_HOST or pass explicit host. Silent default to localhost:8000 is strictly prohibited."
        )

    # 2. Target URL Explicit Confirmation
    if not config.confirm_target_url:
        raise MissingTargetOptInError(
            f"CRITICAL SAFETY ABORT: Operator must explicitly confirm intended target URL '{config.host}' "
            "via PERF_CONFIRM_TARGET_URL=true."
        )

    # 3. Disposable Backing Stores Confirmation
    if not config.confirm_disposable_stores:
        raise MissingDisposableStoreConfirmationError(
            "CRITICAL SAFETY ABORT: Operator must explicitly confirm dedicated, disposable, "
            "non-production database and backing stores via PERF_CONFIRM_DISPOSABLE_STORES=true."
        )

    # 4. Mock Provider Confirmation
    if not config.confirm_mock_provider:
        raise MissingOperatorMockConfirmationError(
            "CRITICAL SAFETY ABORT: Operator must explicitly confirm mock LLM provider intention "
            "via PERF_CONFIRM_MOCK_PROVIDER=true."
        )


def verify_server_environment(host: str, client: httpx.Client | None = None) -> str:
    """Verify target server environment via /health endpoint.

    Args:
        host: Base URL of target server (e.g. 'http://127.0.0.1:8000').
        client: Optional httpx.Client for testing/dependency injection.

    Returns:
        Verified non-production environment name (e.g. 'development', 'test').

    Raises:
        ServerEnvironmentRejectionError: If server is in production or unknown environment.
        PreflightError: If health probe fails or is unreachable.
    """
    clean_host = host.rstrip("/")
    health_url = f"{clean_host}/health"

    try:
        if client is not None:
            resp = client.get(health_url)
        else:
            with httpx.Client(timeout=5.0) as http_client:
                resp = http_client.get(health_url)
    except Exception as exc:
        raise PreflightError(
            f"CRITICAL SAFETY ABORT: Failed to reach target server health endpoint at '{health_url}': {exc}"
        ) from exc

    if resp.status_code != 200:
        raise PreflightError(
            f"CRITICAL SAFETY ABORT: Target server health endpoint '{health_url}' returned HTTP {resp.status_code}."
        )

    try:
        data = resp.json()
    except Exception as exc:
        raise PreflightError(
            f"CRITICAL SAFETY ABORT: Target server health response was not valid JSON: {exc}"
        ) from exc

    env = str(data.get("environment", "")).strip().lower()
    if not env:
        raise ServerEnvironmentRejectionError(
            "CRITICAL SAFETY ABORT: Target server did not report an 'environment' in /health response."
        )

    if env == "production":
        raise ServerEnvironmentRejectionError(
            "CRITICAL SAFETY ABORT: Target server reports environment 'production'. "
            "Load testing against production environments is strictly prohibited."
        )

    allowed_non_prod_envs = {"development", "test", "staging", "local"}
    if env not in allowed_non_prod_envs:
        raise ServerEnvironmentRejectionError(
            f"CRITICAL SAFETY ABORT: Target server reports unknown or uncertified environment '{env}'. "
            f"Permitted environments: {sorted(allowed_non_prod_envs)}."
        )

    logger.info("Target server environment verified", environment=env, host=host)
    return env


def verify_server_mock_provider_attestation(
    host: str,
    admin_token: str | None = None,
    client: httpx.Client | None = None,
) -> bool:
    """Verify server-side mock provider attestation.

    Adheres strictly to safety rule:
    'Do not treat a client-side configuration flag as proof of the server's actual provider configuration.
    If the server cannot safely attest to the required test configuration through an existing trusted
    mechanism, abort and report the missing verification. Do not expose secrets to achieve verification.'

    Args:
        host: Target server host.
        admin_token: Optional platform admin JWT token to query detailed health.
        client: Optional httpx.Client for testing/dependency injection.

    Returns:
        True if server attestation confirms exclusive mock provider configuration.

    Raises:
        ServerProviderAttestationError: If server cannot attest or does not attest to mock provider.
    """
    if not admin_token:
        # Without a trusted attestation mechanism (like admin-authenticated detailed health),
        # client-side flags cannot be trusted as proof of server provider isolation.
        raise ServerProviderAttestationError(
            f"CRITICAL SAFETY ABORT: Target server at '{host}' cannot safely attest to MOCK_LLM_PROVIDER "
            "configuration through an existing trusted mechanism without platform admin credentials. "
            "Client-side configuration flags cannot serve as proof of server provider configuration. "
            "Provide PERF_ADMIN_TOKEN to enable trusted server-side attestation."
        )

    clean_host = host.rstrip("/")
    detailed_health_url = f"{clean_host}/api/v1/health/detailed"
    headers = {"Authorization": f"Bearer {admin_token}"}

    try:
        if client is not None:
            resp = client.get(detailed_health_url, headers=headers)
        else:
            with httpx.Client(timeout=5.0) as http_client:
                resp = http_client.get(detailed_health_url, headers=headers)
    except Exception as exc:
        raise ServerProviderAttestationError(
            f"CRITICAL SAFETY ABORT: Failed to query server detailed health at '{detailed_health_url}': {exc}"
        ) from exc

    if resp.status_code != 200:
        raise ServerProviderAttestationError(
            f"CRITICAL SAFETY ABORT: Server detailed health attestation query failed with HTTP {resp.status_code}."
        )

    data = resp.json()
    dependencies = data.get("dependencies", [])

    llm_dep: dict[str, Any] | None = None
    for dep in dependencies:
        if isinstance(dep, dict) and dep.get("name") == "llm_provider":
            llm_dep = dep
            break

    if not llm_dep:
        raise ServerProviderAttestationError(
            "CRITICAL SAFETY ABORT: Server detailed health did not report 'llm_provider' dependency."
        )

    info = llm_dep.get("info") or {}
    circuit_states = info.get("circuit_states", {})

    # Mock provider isolation check: circuit_states must contain 'mock' and must NOT contain live providers
    if "mock" not in circuit_states:
        raise ServerProviderAttestationError(
            f"CRITICAL SAFETY ABORT: Server provider states ({circuit_states}) do not contain 'mock'. "
            "Mock provider is not active on the target server."
        )

    if len(circuit_states) > 1:
        raise ServerProviderAttestationError(
            f"CRITICAL SAFETY ABORT: Server provider states ({circuit_states}) indicate active fallback routes. "
            "Strict mock provider isolation requires priority list locked exclusively to ['mock']."
        )

    logger.info("Server mock provider attestation verified", host=host, circuit_states=circuit_states)
    return True


def run_preflight_checks(config: LoadTestConfig, client: httpx.Client | None = None) -> dict[str, Any]:
    """Execute complete fail-closed preflight verification suite before generating load.

    Returns:
        Dictionary summarizing verified preflight attestations.

    Raises:
        PreflightError (or subclass): Upon any validation or attestation failure.
    """
    logger.info("Executing load testing safety preflight checks...")

    # 1. Operator Opt-ins
    validate_operator_opt_ins(config)
    assert config.host is not None  # Guaranteed by validate_operator_opt_ins

    # 2. Server Environment Verification
    env = verify_server_environment(config.host, client=client)

    # 3. Server Mock Provider Attestation
    mock_attested = verify_server_mock_provider_attestation(
        config.host,
        admin_token=config.admin_token,
        client=client,
    )

    logger.info(
        "Load test safety preflight PASSED",
        target_host=config.host,
        environment=env,
        mock_attested=mock_attested,
    )

    return {
        "preflight_passed": True,
        "target_host": config.host,
        "environment": env,
        "mock_attested": mock_attested,
    }
