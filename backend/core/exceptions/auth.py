"""Authentication and authorization exceptions."""

from http import HTTPStatus

from .base import ApplicationException


class AuthenticationException(ApplicationException):
    """401 — Request lacks valid authentication credentials."""

    error_code = "AUTH_001"
    default_message = "Authentication required"
    http_status = HTTPStatus.UNAUTHORIZED


class InvalidTokenException(ApplicationException):
    """401 — Token is malformed, has an invalid signature, or cannot be decoded."""

    error_code = "AUTH_002"
    default_message = "Invalid authentication token"
    http_status = HTTPStatus.UNAUTHORIZED


class ExpiredTokenException(ApplicationException):
    """401 — Token has expired and must be refreshed."""

    error_code = "AUTH_003"
    default_message = "Authentication token has expired"
    http_status = HTTPStatus.UNAUTHORIZED


class AuthorizationException(ApplicationException):
    """403 — User is authenticated but lacks the required permission."""

    error_code = "AUTH_004"
    default_message = "You do not have permission to perform this action"
    http_status = HTTPStatus.FORBIDDEN


class InsufficientRoleException(AuthorizationException):
    """403 — User's role does not include the required permission."""

    error_code = "AUTH_005"
    default_message = "Insufficient role for this operation"
