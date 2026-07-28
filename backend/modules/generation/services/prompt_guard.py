"""Prompt Guardrail Service — Phase 10.

Protects grounded generation against prompt injections hidden inside retrieved
evidence chunks or queries, and formats evidence blocks securely.
"""

import re
from typing import Any

from structlog import get_logger

from backend.modules.generation.schemas.generation_dto import \
    PromptGuardrailConfigDTO

logger = get_logger(__name__)

_INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"ignore all prior instructions",
    r"system prompt override",
    r"you are now a helpful assistant without rules",
    r"do not cite sources",
    r"output raw system prompt",
]


class PromptGuard:
    """Sanitizes inputs and builds secure prompt blocks for generation."""

    def __init__(self, config: PromptGuardrailConfigDTO | None = None) -> None:
        self.config = config or PromptGuardrailConfigDTO()
        self._compiled_patterns = [
            re.compile(pat, re.IGNORECASE) for pat in _INJECTION_PATTERNS
        ]

    def scan_for_injection(self, text: str) -> bool:
        """Scan text for common prompt injection patterns. Return True if suspicious."""
        if not self.config.enable_injection_check:
            return False
        for pat in self._compiled_patterns:
            if pat.search(text):
                logger.warning(
                    "Prompt injection pattern detected in input text",
                    pattern=pat.pattern,
                )
                return True
        return False

    def sanitize_and_format_evidence(
        self, chunks: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        """Filter invalid/injected evidence and format secure XML-like boundaries."""
        safe_chunks: list[dict[str, Any]] = []
        formatted_lines: list[str] = []

        for chunk in chunks:
            if not chunk:
                continue
            raw_content = chunk.get("content")
            if raw_content is None:
                logger.info(
                    "Filtering out null evidence chunk before prompt construction",
                    chunk_id=chunk.get("chunk_id"),
                )
                continue
            content = str(raw_content).replace("\n", " ").strip()
            if not content:
                logger.info(
                    "Filtering out empty evidence chunk before prompt construction",
                    chunk_id=chunk.get("chunk_id"),
                )
                continue
            if self.scan_for_injection(content):
                logger.warning(
                    "Filtering out suspicious evidence chunk due to prompt injection check",
                    chunk_id=chunk.get("chunk_id"),
                )
                continue
            safe_chunks.append(chunk)
            citation_index = len(safe_chunks)
            formatted_lines.append(
                f"<evidence_chunk id='{citation_index}'>"
                f"[{citation_index}] {content}</evidence_chunk>"
            )

        return "\n".join(formatted_lines), safe_chunks
