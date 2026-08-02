"""Unit tests for Document Domain Exception Hierarchy & Taxonomy (`ADR-005`, `Refinement 7`)."""


from backend.document.schemas.errors import (
    DocumentDomainException,
    DocumentErrorCode,
    ErrorSeverity,
    get_error_severity,
)


class TestDocumentErrors:
    """Test suite verifying document exception attributes and HTTP mappings."""

    def test_base_document_domain_exception(self):
        """Verify inheritance from RAGuardException and defaults."""
        exc = DocumentDomainException(
            code=DocumentErrorCode.SYS_001,
            message="General document error",
        )
        assert str(exc) == "General document error"
        assert exc.error_code == "SYS_001"
        assert exc.http_status == 500
        assert exc.severity == ErrorSeverity.RECOVERABLE

    def test_validation_error_attributes(self):
        """Verify validation errors map to HTTP 400 and FATAL severity."""
        exc = DocumentDomainException(
            code=DocumentErrorCode.VAL_002,
            message="Disallowed MIME type",
        )
        assert exc.error_code == "VAL_002"
        assert exc.http_status == 400
        assert exc.severity == ErrorSeverity.FATAL

    def test_not_found_error_attributes(self):
        """Verify STORE_002 maps to HTTP 404."""
        exc = DocumentDomainException(
            code=DocumentErrorCode.STORE_002,
            message="Document object not found",
        )
        assert exc.error_code == "STORE_002"
        assert exc.http_status == 404
        assert exc.severity == ErrorSeverity.RECOVERABLE

    def test_contract_violation_error_attributes(self):
        """Verify CONTRACT_001 code mapping (`Refinement 6`)."""
        exc = DocumentDomainException(
            code=DocumentErrorCode.CONTRACT_001,
            message="Missing normalized text artifact",
        )
        assert exc.error_code == "CONTRACT_001"
        assert exc.http_status == 500
        assert exc.severity == ErrorSeverity.RECOVERABLE

    def test_error_severity_helper(self):
        """Verify get_error_severity mapping for both FATAL and RECOVERABLE codes."""
        assert get_error_severity(DocumentErrorCode.VAL_005) == ErrorSeverity.FATAL
        assert get_error_severity(DocumentErrorCode.EXTRACT_001) == ErrorSeverity.FATAL
        assert get_error_severity(DocumentErrorCode.OCR_001) == ErrorSeverity.RECOVERABLE
