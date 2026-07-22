from enum import StrEnum

from backend.core.exceptions.base import RAGuardException


class EvaluationErrorCode(StrEnum):
    DATASET_NOT_FOUND = "EVAL_001"
    EVALUATION_FAILED = "EVAL_002"


class EvaluationDomainException(RAGuardException):
    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)
