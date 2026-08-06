from backend.core.exceptions import LLMProviderException


class V1EngineUnavailableError(LLMProviderException):
    def __init__(self, message: str = "V1 Engine is unavailable."):
        super().__init__(message=message, status_code=503)


class V1TLSError(LLMProviderException):
    def __init__(self, message: str = "V1 Engine mTLS handshake failed."):
        super().__init__(message=message, status_code=503)


class V1AuthenticationError(LLMProviderException):
    def __init__(self, message: str = "V1 Engine authentication failed."):
        super().__init__(message=message, status_code=502)


class V1AuthorizationError(LLMProviderException):
    def __init__(self, message: str = "V1 Engine authorization failed."):
        super().__init__(message=message, status_code=502)


class V1TimeoutError(LLMProviderException):
    def __init__(self, message: str = "V1 Engine request timed out."):
        super().__init__(message=message, status_code=504)


class V1EngineVersionMismatchError(LLMProviderException):
    def __init__(self, message: str = "V1 Engine version mismatch."):
        super().__init__(message=message, status_code=503)


class V1EngineStreamAbortError(LLMProviderException):
    def __init__(self, message: str = "V1 Engine stream aborted mid-generation."):
        super().__init__(message=message, status_code=500)
