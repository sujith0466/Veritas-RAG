from enum import StrEnum
from backend.core.exceptions.base import RAGuardException


class GenerationErrorCode(StrEnum):
    GENERATION_FAILED = "GEN_001"
    CITATION_EXTRACTION_FAILED = "GEN_002"
    GROUNDING_VIOLATION = "GEN_003"


class GenerationDomainException(RAGuardException):
    """Base exception for generation domain."""
    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)


class GenerationFailed(GenerationDomainException):
    def __init__(self, message: str = "Answer generation failed", detail: dict | None = None):
        super().__init__(message=message, error_code=GenerationErrorCode.GENERATION_FAILED, detail=detail)


class CitationExtractionFailed(GenerationDomainException):
    def __init__(self, message: str = "Citation extraction failed", detail: dict | None = None):
        super().__init__(message=message, error_code=GenerationErrorCode.CITATION_EXTRACTION_FAILED, detail=detail)


class GroundingViolation(GenerationDomainException):
    """Raised when an answer contains claims with zero citation backing."""
    def __init__(self, message: str = "Grounding violation: answer contains uncited claims", detail: dict | None = None):
        super().__init__(message=message, error_code=GenerationErrorCode.GROUNDING_VIOLATION, detail=detail)
