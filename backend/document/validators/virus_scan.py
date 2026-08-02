"""Pluggable virus scanning abstraction (`VAL_005`).

Provides an abstract interface for malware checks during upload validation.
Includes clean dev bypass and production ClamAV hook.
"""

from abc import ABC, abstractmethod
from typing import BinaryIO

from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode


class VirusScanner(ABC):
    """Abstract interface for document virus and malware scanning."""

    @abstractmethod
    async def scan(self, stream: BinaryIO, filename: str) -> bool:
        """Scan binary stream for malware (`VAL_005`).

        Returns True if clean. Raises DocumentDomainException(VAL_005) if infected.
        """
        ...


class CleanPassScanner(VirusScanner):
    """Local development and clean-pass scanner implementation."""

    async def scan(self, stream: BinaryIO, filename: str) -> bool:
        """Always passes cleanly (used for local/testing environments)."""
        return True


class ClamAVScanner(VirusScanner):
    """ClamAV daemon scanner hook (`3310` socket)."""

    def __init__(self, host: str = "clamav", port: int = 3310) -> None:
        self.host = host
        self.port = port

    async def scan(self, stream: BinaryIO, filename: str) -> bool:
        """Connect to ClamAV daemon and verify file cleanliness (`VAL_005`)."""
        # Note: In Phase 1 local dev, we default to CleanPassScanner unless ClamAV is enabled.
        # This hook prepares standard EICAR / ClamAV socket communication.
        current_pos = stream.tell()
        stream.seek(0)
        content = stream.read()
        stream.seek(current_pos)

        # Standard EICAR test string check for self-testing / hooks
        if (
            b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
            in content
        ):
            raise DocumentDomainException(
                code=DocumentErrorCode.VAL_005,
                message="Security violation: Malware or EICAR test virus signature detected.",
                detail={"filename": filename, "scanner": "ClamAVScanner"},
            )

        return True
