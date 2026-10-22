"""Rate Limit Dependency for FastAPI Routes.

Extracts client identity via TrustedProxyMiddleware (request.state.client_ip),
supports tenant and user dimensions, applies atomic sliding-window limiting,
attaches standard RFC headers, and enforces endpoint degradation policies.
"""

from typing import Callable
from fastapi import HTTPException, Request, Response, status
from backend.cache.rate_limit import RateLimiter, RateLimitExceeded


AUTH_ACTIONS = {
    "login",
    "register",
    "forgot-password",
    "reset-password",
    "password-reset-request",
    "password-otp-request",
    "password-reset-verify",
    "password-otp-verify",
    "password-reset-complete",
    "change-password",
    "change-password-complete",
}


def RateLimit(
    action: str,
    limit: int,
    window: int,
    domain: str = "api",
    key_type: str = "multi_tier",  # "multi_tier", "composite", "ip", "tenant", "user"
    degradation_policy: str | None = None,
    ip_limit: int | None = None,
    tenant_limit: int | None = None,
    user_limit: int | None = None,
) -> Callable:
    """Dependency factory for multi-tier rate limiting endpoints.

    Enforces independent tiers:
    - IP Tier: bounds requests per client IP (prevents DDoS / brute-force).
    - Tenant Tier: bounds requests across entire workspace/tenant.
    - User Tier: bounds requests per authenticated user (prevents IP rotation evasion).

    Identities are extracted strictly from authenticated server context (never client headers).

    Args:
        action: The specific action to rate limit (e.g. 'chat_stream', 'upload').
        limit: Default max requests in the sliding window.
        window: Time window in seconds.
        domain: System domain ('api', 'auth', 'chat', 'documents', 'retrieval').
        key_type: Rate limit tier scope ('multi_tier', 'composite', 'ip', 'tenant', 'user').
        degradation_policy: 'fail_open' or 'fail_closed' on Redis failure.
                            If None, defaults to fail_closed for auth and upload,
                            fail_open for streaming and search.
        ip_limit: Explicit limit for IP tier (defaults to limit).
        tenant_limit: Explicit limit for tenant tier (defaults to limit * 2).
        user_limit: Explicit limit for user tier (defaults to limit).
    """
    if degradation_policy is None:
        if domain == "auth" or action in AUTH_ACTIONS:
            resolved_degradation = "fail_closed"
        elif domain == "documents" or "upload" in action:
            # Documented risk decision: fail closed to protect worker and storage saturation
            resolved_degradation = "fail_closed"
        else:
            resolved_degradation = "fail_open"
    else:
        resolved_degradation = degradation_policy

    eff_ip_limit = ip_limit or limit
    eff_tenant_limit = tenant_limit or (limit * 2)
    eff_user_limit = user_limit or limit

    async def _rate_limit_dependency(request: Request, response: Response) -> None:
        # 1. Resolve true client IP from TrustedProxyMiddleware state
        client_ip = getattr(request.state, "client_ip", None)
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"

        # 2. Extract tenant and user identity STRICTLY from authenticated server context.
        # NEVER trust or inspect client-supplied headers (e.g. X-Tenant-ID).
        user_ctx = getattr(request.state, "user_context", None) or getattr(request.state, "user", None)
        tenant_id = None
        user_id = None

        if user_ctx:
            tenant_val = getattr(user_ctx, "tenant_id", None) or getattr(user_ctx, "workspace_id", None)
            if tenant_val:
                tenant_id = str(tenant_val)
            user_val = getattr(user_ctx, "id", None) or getattr(user_ctx, "user_id", None)
            if user_val:
                user_id = str(user_val)

        # Also support server dependencies that attach tenant_id or user_id directly to request.state
        if not tenant_id and hasattr(request.state, "tenant_id") and request.state.tenant_id:
            tenant_id = str(request.state.tenant_id)
        if not user_id and hasattr(request.state, "user_id") and request.state.user_id:
            user_id = str(request.state.user_id)

        # 3. Build tiers to enforce based on requested key dimension
        tiers_to_check: list[tuple[str, str, str, int]] = []

        if key_type == "ip":
            tiers_to_check.append(("global", f"{action}:ip", f"ip:{client_ip}", eff_ip_limit))
        elif key_type == "tenant" and tenant_id:
            tiers_to_check.append((tenant_id, f"{action}:tenant", "tenant", eff_tenant_limit))
        elif key_type == "user" and user_id:
            tenant_scope = tenant_id if tenant_id else "global"
            tiers_to_check.append((tenant_scope, f"{action}:user", f"user:{user_id}", eff_user_limit))
        else:
            # Default multi-tier / composite: enforce all applicable tiers independently
            # Tier 1: IP tier (always enforced)
            tiers_to_check.append(("global", f"{action}:ip", f"ip:{client_ip}", eff_ip_limit))

            # Tier 2: Tenant tier (enforced when authenticated tenant context exists)
            if tenant_id:
                tiers_to_check.append((tenant_id, f"{action}:tenant", "tenant", eff_tenant_limit))

            # Tier 3: User tier (enforced when authenticated user context exists)
            if user_id:
                tenant_scope = tenant_id if tenant_id else "global"
                tiers_to_check.append((tenant_scope, f"{action}:user", f"user:{user_id}", eff_user_limit))

        # 4. Check each tier against Redis atomic sliding window
        min_remaining = limit
        max_reset = window

        try:
            for t_tenant, t_action, t_entity_id, t_limit in tiers_to_check:
                result = await RateLimiter.check_limit(
                    tenant=t_tenant,
                    domain=domain,
                    action=t_action,
                    entity_id=t_entity_id,
                    limit=t_limit,
                    window_seconds=window,
                    degradation_policy=resolved_degradation,
                )
                rem = result.get("remaining", t_limit)
                if rem < min_remaining:
                    min_remaining = rem
                rst = result.get("reset_seconds", window)
                if rst > max_reset:
                    max_reset = rst

                if result.get("degraded"):
                    # Redis outage encountered; short-circuit remaining tiers for this request
                    # to prevent duplicate failure telemetry and redundant connection timeouts.
                    break

            # 5. Attach RFC 6585 and X-RateLimit headers to response
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(min_remaining)
            response.headers["X-RateLimit-Reset"] = str(max_reset)

        except RateLimitExceeded as exc:
            headers = {
                "Retry-After": str(exc.retry_after),
                "X-RateLimit-Limit": str(exc.limit),
                "X-RateLimit-Remaining": str(exc.remaining),
                "X-RateLimit-Reset": str(exc.reset_seconds),
            }
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Please retry in {exc.retry_after} seconds.",
                headers=headers,
            ) from exc

    return _rate_limit_dependency
