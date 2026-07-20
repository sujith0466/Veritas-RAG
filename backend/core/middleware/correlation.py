"""Correlation ID middleware.

Injects a unique X-Correlation-ID into every request for distributed tracing.

Behaviour:
- If the client sends an X-Correlation-ID header, propagate it unchanged.
- Otherwise, generate a new UUID v4 and use that.
- The ID is stored on request.state.correlation_id for use by other layers.
- The X-Correlation-ID header is echoed back in the response.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

CORRELATION_ID_HEADER = "X-Correlation-ID"


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Inject and propagate a correlation ID on every request."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = (
            request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        )
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
