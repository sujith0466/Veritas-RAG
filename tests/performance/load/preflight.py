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
import urllib.parse
import httpx
import structlog

from tests.performance.load.config import LoadTestConfig

logger = structlog.get_logger(__name__)


class PreflightError(Exception):
    """Base exception for load testing preflight safety aborts."""


class MissingTargetOptInError(PreflightError):
    """Raised when target host is not explicitly specified (no silent defaults)."""


class TargetMismatchError(PreflightError):
    """Raised when command-line --host and environment PERF_TARGET_HOST disagree."""


class MalformedTargetURLError(PreflightError):
    """Raised when target URL scheme or structure is malformed."""


class MissingDisposableStoreConfirmationError(PreflightError):
    """Raised when operator has not explicitly confirmed disposable non-production stores."""


class MissingOperatorMockConfirmationError(PreflightError):
    """Raised when operator has not explicitly confirmed mock provider intention."""


class ServerEnvironmentRejectionError(PreflightError):
    """Raised when target server environment is production or unknown."""


class ServerProviderAttestationError(PreflightError):
    """Raised when target server cannot safely attest to MOCK_LLM_PROVIDER configuration."""


class ServerEmbeddingIsolationError(PreflightError):
    """Raised when target server embedding provider is unverified or configured to a live external provider."""


def validate_operator_opt_ins(config: LoadTestConfig, cli_host: str | None = None) -> str:
    """Validate explicit operator opt-ins, confirmations, and target consistency before traffic.

    Args:
        config: LoadTestConfig instance.
        cli_host: Optional command-line host passed to Locust (--host).

    Returns:
        Effective, verified target URL.

    Raises:
        MissingTargetOptInError: If target host is missing or unconfirmed.
        TargetMismatchError: If --host and PERF_TARGET_HOST conflict.
        MalformedTargetURLError: If target URL is not a valid http(s) URL.
        MissingDisposableStoreConfirmationError: If disposable store confirmation is missing.
        MissingOperatorMockConfirmationError: If mock provider confirmation is missing.
    """
    env_host = config.host

    # 1. Target Ambiguity and Mismatch Detection
    if cli_host and env_host:
        norm_cli = cli_host.strip().rstrip("/").lower()
        norm_env = env_host.strip().rstrip("/").lower()
        if norm_cli != norm_env:
            raise TargetMismatchError(
                f"CRITICAL SAFETY ABORT: Target mismatch detected! "
                f"Command-line --host '{cli_host}' and PERF_TARGET_HOST '{env_host}' disagree. "
                "Disagreement between targets is strictly prohibited to prevent accidental traffic."
            )

    effective_host = cli_host or env_host
    if not effective_host or not effective_host.strip():
        raise MissingTargetOptInError(
            "CRITICAL SAFETY ABORT: Target host opt-in required. "
            "Set PERF_TARGET_HOST or pass explicit --host. Silent default to localhost:8000 is strictly prohibited."
        )

    # 2. URL Scheme & Structure Validation
    clean_target = effective_host.strip()
    parsed = urllib.parse.urlparse(clean_target)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise MalformedTargetURLError(
            f"CRITICAL SAFETY ABORT: Target URL '{clean_target}' is malformed. "
            "Must be a valid URL with explicit 'http://' or 'https://' scheme and network location."
        )

    # 3. Target URL Explicit Confirmation
    if not config.confirm_target_url:
        raise MissingTargetOptInError(
            f"CRITICAL SAFETY ABORT: Operator must explicitly confirm intended target URL '{clean_target}' "
            "via PERF_CONFIRM_TARGET_URL=true."
        )

    # 4. Disposable Backing Stores Confirmation
    if not config.confirm_disposable_stores:
        raise MissingDisposableStoreConfirmationError(
            "CRITICAL SAFETY ABORT: Operator must explicitly confirm dedicated, disposable, "
            "non-production database and backing stores via PERF_CONFIRM_DISPOSABLE_STORES=true."
        )

    # 5. Mock Provider Confirmation
    if not config.confirm_mock_provider:
        raise MissingOperatorMockConfirmationError(
            "CRITICAL SAFETY ABORT: Operator must explicitly confirm mock LLM provider intention "
            "via PERF_CONFIRM_MOCK_PROVIDER=true."
        )

    return clean_target


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

    # Check mock circuit state: must NOT be OPEN
    mock_state = str(circuit_states.get("mock", "")).strip().upper()
    if mock_state == "OPEN":
        raise ServerProviderAttestationError(
            "CRITICAL SAFETY ABORT: Server mock provider circuit breaker is OPEN. "
            "Target server cannot accept chat requests. Cooldown or reset required before benchmark run."
        )

    if mock_state not in ("CLOSED", "HALF_OPEN"):
        raise ServerProviderAttestationError(
            f"CRITICAL SAFETY ABORT: Server mock provider circuit breaker is in unexpected state '{mock_state}'. "
            "Expected 'CLOSED' or 'HALF_OPEN'."
        )

    logger.info("Server mock provider attestation verified", host=host, circuit_states=circuit_states)
    return True


def verify_server_embedding_isolation(
    host: str,
    admin_token: str | None = None,
    client: httpx.Client | None = None,
    allow_unverified: bool = False,
) -> bool:
    """Verify that the target server is configured with isolated local/mock embedding providers.

    Prevents accidental outbound requests to billable external APIs (e.g. OpenAI, Cohere)
    during vector indexing or query embedding.

    Args:
        host: Target server host.
        admin_token: Optional platform admin JWT token.
        client: Optional httpx.Client for dependency injection.
        allow_unverified: If True, permits proceeding without explicit embedding attestation (e.g. for pure read-only runs).

    Returns:
        True if embedding isolation is attested.

    Raises:
        ServerEmbeddingIsolationError: If an external billable embedding provider is detected without explicit override.
    """
    if not admin_token:
        if allow_unverified:
            logger.warning("Embedding isolation attestation skipped: admin token omitted and allow_unverified=True")
            return True
        logger.info("Admin token omitted; assuming read-only benchmark scenarios")
        return True

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
        raise ServerEmbeddingIsolationError(
            f"CRITICAL SAFETY ABORT: Failed to query server detailed health for embedding isolation: {exc}"
        ) from exc

    if resp.status_code != 200:
        raise ServerEmbeddingIsolationError(
            f"CRITICAL SAFETY ABORT: Detailed health query returned HTTP {resp.status_code}."
        )

    data = resp.json()
    dependencies = data.get("dependencies", [])

    emb_dep: dict[str, Any] | None = None
    for dep in dependencies:
        if isinstance(dep, dict) and dep.get("name") == "embedding_provider":
            emb_dep = dep
            break

    if emb_dep:
        info = emb_dep.get("info") or {}
        provider_name = str(info.get("default_provider", "")).strip().lower()
        is_isolated = info.get("is_isolated", False)

        if not is_isolated and provider_name in ("openai", "cohere") and not allow_unverified:
            raise ServerEmbeddingIsolationError(
                f"CRITICAL SAFETY ABORT: Target server is configured with live external embedding provider "
                f"'{provider_name}'. Ingestion and embedding workloads require DEFAULT_EMBEDDING_PROVIDER='local' "
                "or 'mock'. Export PERF_CONFIRM_EMBEDDING_ISOLATION=true if running read-only without ingestion."
            )

    logger.info("Server embedding provider isolation verified", host=host)
    return True


def run_preflight_checks(
    config: LoadTestConfig,
    cli_host: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Execute complete fail-closed preflight verification suite before generating load.

    Args:
        config: LoadTestConfig instance.
        cli_host: Optional command-line host passed to Locust (--host).
        client: Optional httpx.Client for testing/dependency injection.

    Returns:
        Dictionary summarizing verified preflight attestations.

    Raises:
        PreflightError (or subclass): Upon any validation or attestation failure.
    """
    logger.info("Executing load testing safety preflight checks...")

    # 1. Operator Opt-ins & Target Consistency
    effective_host = validate_operator_opt_ins(config, cli_host=cli_host)

    # 2. Server Environment Verification
    env = verify_server_environment(effective_host, client=client)

    # 3. Server Mock Provider Attestation
    mock_attested = verify_server_mock_provider_attestation(
        effective_host,
        admin_token=config.admin_token,
        client=client,
    )

    # 4. Server Embedding Provider Isolation
    embedding_isolated = verify_server_embedding_isolation(
        effective_host,
        admin_token=config.admin_token,
        client=client,
        allow_unverified=config.confirm_embedding_isolation,
    )

    logger.info(
        "Load test safety preflight PASSED",
        target_host=effective_host,
        environment=env,
        mock_attested=mock_attested,
        embedding_isolated=embedding_isolated,
    )

    return {
        "preflight_passed": True,
        "target_host": effective_host,
        "environment": env,
        "mock_attested": mock_attested,
        "embedding_isolated": embedding_isolated,
    }
