"""Authentication helpers and context middleware.

Provides utilities for extracting bearer credentials from HTTP requests
and managing request-scoped context.
"""

from fastapi import Request


def extract_bearer_token(request: Request) -> str | None:
    """Extract and clean Bearer token from the HTTP Authorization header.

    Args:
        request: The incoming FastAPI HTTP request.

    Returns:
        The raw token string if present and properly formatted, else None.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    parts = auth_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]
