"""Extractor Capability Registry (`ExtractorCapabilityRegistry`).

Routes file streams to the highest-priority enabled extractor based on MIME type and file extension (`Refinement 5`).
"""

from backend.document.schemas.errors import (DocumentDomainException,
                                             DocumentErrorCode)

from .base import BaseExtractor, ExtractorCapability


class ExtractorCapabilityRegistry:
    """Central registry mapping document formats to specific extractor implementations."""

    def __init__(self) -> None:
        self._extractors: dict[str, BaseExtractor] = {}

    def register(self, extractor: BaseExtractor) -> None:
        """Register an extractor instance in the registry."""
        cap = extractor.capability
        self._extractors[cap.name] = extractor

    def unregister(self, name: str) -> None:
        """Remove an extractor by name."""
        self._extractors.pop(name, None)

    def get_extractor(self, mime_type: str, extension: str) -> BaseExtractor:
        """Find the highest-priority enabled extractor matching `mime_type` or `extension` (`EXTRACT_003`)."""
        clean_mime = mime_type.split(";", maxsplit=1)[0].strip().lower()
        clean_ext = extension.lower()

        candidates: list[BaseExtractor] = []
        for ext_instance in self._extractors.values():
            cap = ext_instance.capability
            if not cap.enabled:
                continue
            if (
                clean_mime in cap.supported_mimes
                or clean_ext in cap.supported_extensions
            ):
                candidates.append(ext_instance)

        if not candidates:
            raise DocumentDomainException(
                code=DocumentErrorCode.EXTRACT_003,
                message=f"No capable extractor registered for MIME '{clean_mime}' or extension '{clean_ext}'.",
                detail={"mime_type": clean_mime, "extension": clean_ext},
            )

        # Sort descending by priority (highest priority first)
        candidates.sort(key=lambda e: e.capability.priority, reverse=True)
        return candidates[0]

    def list_capabilities(self) -> list[ExtractorCapability]:
        """List capabilities of all registered extractors."""
        return [e.capability for e in self._extractors.values()]
