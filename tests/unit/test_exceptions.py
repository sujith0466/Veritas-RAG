"""Unit tests for the RAGuard exception hierarchy and FastAPI exception handlers."""

from http import HTTPStatus

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
import pytest
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.core.exceptions import (
    ApplicationException,
    AuthenticationException,
    AuthorizationException,
    BusinessRuleException,
    CacheConnectionException,
    CacheException,
    ConfidenceThresholdException,
    ConflictException,
    DatabaseConnectionException,
    DatabaseException,
    ExpiredTokenException,
    ExternalServiceException,
    InfrastructureException,
    IngestionException,
    InsufficientRoleException,
    InvalidTokenException,
    LLMProviderException,
    NotFoundException,
    RAGuardException,
    RateLimitException,
    RetrievalException,
    RetryBudgetExhaustedException,
    ValidationException,
    VectorDBConnectionException,
    VectorDBException,
    get_exception_handlers,
)
from backend.core.exceptions.handlers import (
    http_exception_handler,
    raguard_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)


@pytest.mark.unit
class TestExceptionHierarchy:
    def test_base_raguard_exception_defaults(self) -> None:
        exc = RAGuardException()
        assert exc.message == "An unexpected error occurred"
        assert exc.error_code == "INTERNAL_000"
        assert exc.http_status == HTTPStatus.INTERNAL_SERVER_ERROR
        assert exc.detail == {}
        assert str(exc) == exc.message

    def test_base_raguard_exception_custom_values(self) -> None:
        exc = RAGuardException(
            message="Custom error",
            detail={"foo": "bar"},
            error_code="CUSTOM_999",
        )
        assert exc.message == "Custom error"
        assert exc.error_code == "CUSTOM_999"
        assert exc.detail == {"foo": "bar"}

    def test_application_vs_infrastructure_http_status(self) -> None:
        app_exc = ApplicationException("Client error")
        assert app_exc.http_status == HTTPStatus.BAD_REQUEST

        infra_exc = InfrastructureException("Server error")
        assert infra_exc.http_status == HTTPStatus.SERVICE_UNAVAILABLE

    @pytest.mark.parametrize(
        "exc_class, expected_code, expected_status",
        [
            (AuthenticationException, "AUTH_001", HTTPStatus.UNAUTHORIZED),
            (InvalidTokenException, "AUTH_002", HTTPStatus.UNAUTHORIZED),
            (ExpiredTokenException, "AUTH_003", HTTPStatus.UNAUTHORIZED),
            (AuthorizationException, "AUTH_004", HTTPStatus.FORBIDDEN),
            (InsufficientRoleException, "AUTH_005", HTTPStatus.FORBIDDEN),
            (ValidationException, "VAL_001", HTTPStatus.BAD_REQUEST),
            (NotFoundException, "NOT_FOUND_001", HTTPStatus.NOT_FOUND),
            (ConflictException, "CONFLICT_001", HTTPStatus.CONFLICT),
            (RateLimitException, "RATE_001", HTTPStatus.TOO_MANY_REQUESTS),
            (BusinessRuleException, "BIZ_001", HTTPStatus.UNPROCESSABLE_ENTITY),
            (RetrievalException, "RET_001", HTTPStatus.INTERNAL_SERVER_ERROR),
            (RetryBudgetExhaustedException, "SC_001", HTTPStatus.UNPROCESSABLE_ENTITY),
            (ConfidenceThresholdException, "SC_002", HTTPStatus.UNPROCESSABLE_ENTITY),
            (IngestionException, "ING_001", HTTPStatus.BAD_REQUEST),
            (DatabaseException, "DB_001", HTTPStatus.SERVICE_UNAVAILABLE),
            (DatabaseConnectionException, "DB_002", HTTPStatus.SERVICE_UNAVAILABLE),
            (CacheException, "CACHE_001", HTTPStatus.SERVICE_UNAVAILABLE),
            (CacheConnectionException, "CACHE_002", HTTPStatus.SERVICE_UNAVAILABLE),
            (VectorDBException, "VDB_001", HTTPStatus.SERVICE_UNAVAILABLE),
            (VectorDBConnectionException, "VDB_002", HTTPStatus.SERVICE_UNAVAILABLE),
            (ExternalServiceException, "EXT_001", HTTPStatus.BAD_GATEWAY),
            (LLMProviderException, "EXT_002", HTTPStatus.BAD_GATEWAY),
        ],
    )
    def test_subclasses_attributes(
        self, exc_class: type[RAGuardException], expected_code: str, expected_status: HTTPStatus
    ) -> None:
        exc = exc_class()
        assert exc.error_code == expected_code
        assert exc.http_status == expected_status
        assert isinstance(exc, RAGuardException)


@pytest.mark.unit
class TestExceptionHandlers:
    @pytest.fixture
    def mock_request(self) -> Request:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/test",
            "headers": [(b"host", b"testserver")],
        }
        req = Request(scope)
        req.state.correlation_id = "test-correlation-123"
        return req

    @pytest.mark.asyncio
    async def test_raguard_exception_handler(self, mock_request: Request) -> None:
        exc = NotFoundException(message="User not found", detail={"user_id": "42"})
        response = await raguard_exception_handler(mock_request, exc)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.headers["X-Correlation-ID"] == "test-correlation-123"

        import json
        body = json.loads(bytes(response.body).decode("utf-8"))
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND_001"
        assert body["error"]["message"] == "User not found"
        assert body["error"]["detail"] == {"user_id": "42"}
        assert body["error"]["request_id"] == "test-correlation-123"

    @pytest.mark.asyncio
    async def test_validation_exception_handler(self, mock_request: Request) -> None:
        # Construct a RequestValidationError
        exc = RequestValidationError([
            {
                "type": "missing",
                "loc": ("body", "username"),
                "msg": "Field required",
                "input": {},
            }
        ])
        response = await validation_exception_handler(mock_request, exc)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        import json
        body = json.loads(bytes(response.body).decode("utf-8"))
        assert body["success"] is False
        assert body["error"]["code"] == "VAL_002"
        assert body["error"]["message"] == "Request body validation failed"
        assert body["error"]["detail"]["errors"] == [
            {"field": "body.username", "message": "Field required", "type": "missing"}
        ]

    @pytest.mark.asyncio
    async def test_http_exception_handler(self, mock_request: Request) -> None:
        exc = StarletteHTTPException(status_code=403, detail="Not allowed")
        response = await http_exception_handler(mock_request, exc)
        assert response.status_code == 403

        import json
        body = json.loads(bytes(response.body).decode("utf-8"))
        assert body["success"] is False
        assert body["error"]["code"] == "AUTH_004"
        assert body["error"]["message"] == "Not allowed"

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler(self, mock_request: Request) -> None:
        exc = RuntimeError("Boom")
        response = await unhandled_exception_handler(mock_request, exc)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        import json
        body = json.loads(bytes(response.body).decode("utf-8"))
        assert body["success"] is False
        assert body["error"]["code"] == "INTERNAL_000"
        assert body["error"]["message"] == "An internal server error occurred"
        assert body["error"]["detail"] == {"correlation_id": "test-correlation-123"}

    def test_get_exception_handlers(self) -> None:
        handlers = get_exception_handlers()
        assert len(handlers) == 4
        exc_types = [h[0] for h in handlers]
        assert RAGuardException in exc_types
        assert RequestValidationError in exc_types
        assert StarletteHTTPException in exc_types
        assert Exception in exc_types
