"""Generic Retry Utility.

Provides a reusable asynchronous exponential backoff decorator for resilient
infrastructure connections (Redis, PostgreSQL, Qdrant, OpenRouter, etc.).
"""

import asyncio
import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar, cast

logger = logging.getLogger(__name__)

T = TypeVar("T")


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for async functions to retry on failure with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries in seconds.
        exceptions: Tuple of exception types to catch and retry on.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            retries = 0
            delay = base_delay

            while True:
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    retries += 1
                    if retries > max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}. Error: {exc}"
                        )
                        raise

                    logger.warning(
                        f"Attempt {retries}/{max_retries} failed for {func.__name__}. "
                        f"Retrying in {delay}s. Error: {exc}"
                    )
                    await asyncio.sleep(delay)
                    
                    # Exponential backoff
                    delay = min(delay * 2, max_delay)

        return wrapper

    return decorator
