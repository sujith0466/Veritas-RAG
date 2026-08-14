"""Rate Limit Dependency for FastAPI Routes."""

from typing import Callable
from fastapi import Request, HTTPException, status
from backend.cache.rate_limit import RateLimiter, RateLimitExceeded

def RateLimit(action: str, limit: int, window: int) -> Callable:
    """Dependency factory for rate limiting endpoints.
    
    Args:
        action: The specific action to rate limit.
        limit: Max requests in the window.
        window: Time window in seconds.
    """
    async def _rate_limit_dependency(request: Request) -> None:
        entity_id = request.client.host if request.client else "unknown"
        try:
            await RateLimiter.check_limit(
                tenant="system",
                domain="auth",
                action=action,
                entity_id=entity_id,
                limit=limit,
                window_seconds=window
            )
        except RateLimitExceeded:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later."
            )

    return _rate_limit_dependency
