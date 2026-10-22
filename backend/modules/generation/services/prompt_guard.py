"""Prompt Guardrail Service — Phase 10 / WP-3B.

Protects grounded generation against prompt injections hidden inside retrieved
evidence chunks or queries, and formats evidence blocks securely with randomized
nonces and delimiter escaping.
"""
import re
import secrets
from typing import Any

from structlog import get_logger

from backend.modules.generation.schemas.generation_dto import PromptGuardrailConfigDTO
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO
from backend.observability.metrics.prometheus import record_prompt_injection

logger = get_logger(__name__)

# Expanded heuristic rules for injection, jailbreak, system leakage, and delimiter manipulation
_INJECTION_PATTERNS = [
    # Instruction overrides
    r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+instructions",
    r"forget\s+(all\s+)?(previous|prior|above|earlier)\s+instructions",
    r"system\s+prompt\s+override",
    r"override\s+(the\s+)?system\s+prompt",
    r"override\s+(all\s+)?instructions",
    # Jailbreak personas and modes
    r"you\s+are\s+now\s+a\s+helpful\s+assistant\s+without\s+rules",
    r"you\s+are\s+now\s+in\s+dan\s+mode",
    r"do\s+anything\s+now",
    r"developer\s+mode\s+enabled",
    r"\bjailbreak\b",
    r"bypass\s+(all\s+)?(safety|rules|guardrails|filters|restrictions)",
    r"unfiltered\s+assistant",
    # System prompt leakage attempts
    r"output\s+(the\s+)?(raw\s+)?system\s+prompt",
    r"print\s+(the\s+)?(raw\s+)?system\s+prompt",
    r"reveal\s+(the\s+)?(raw\s+)?system\s+prompt",
    r"repeat\s+the\s+(entire\s+)?prompt\s+above",
    r"show\s+your\s+(initial\s+)?instructions",
    r"do\s+not\s+cite\s+sources",
    r"what\s+is\s+your\s+(hidden\s+)?system\s+prompt",
    # Delimiter manipulation & XML tag breakouts
    r"</?evidence_chunk[^>]*>",
    r"\[/?evidence_chunk[^\]]*\]",
    r"<\!\[cdata\[",
]

# Regex for control characters and suspicious invisible Unicode
# Preserves standard whitespace: \t (0x09), \n (0x0A), \r (0x0D)
# Strips ASCII control chars: 0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F, 0x7F
_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Strips zero-width and directional override Unicode:
# \u200B (ZWSP), \u200C (ZWNJ), \u200D (ZWJ), \u200E/\u200F (LTR/RTL marks),
# \u202A-\u202E (bidi embeddings/overrides), \u2060 (word joiner), \u2063 (invisible sep),
# \u2066-\u2069 (directional isolates), \uFEFF (zero-width no-break space / BOM)
_INVISIBLE_UNICODE_PATTERN = re.compile(
    r"[\u200b-\u200f\u202a-\u202e\u2060\u2063\u2066-\u2069\ufeff]"
)


def sanitize_invisible_unicode_and_controls(text: str) -> str:
    """Sanitize control chars and invisible Unicode while preserving valid multilingual text."""
    if not text:
        return ""
    cleaned = _CONTROL_CHARS_PATTERN.sub("", text)
    cleaned = _INVISIBLE_UNICODE_PATTERN.sub("", cleaned)
    return cleaned


def escape_evidence_delimiters(content: str) -> str:
    """Escape closing and opening evidence_chunk XML tags inside evidence content.

    Prevents retrieved document text from prematurely terminating or forging XML boundaries.
    """
    if not content:
        return ""
    escaped = re.sub(
        r"</evidence_chunk\s*>",
        "&lt;/evidence_chunk&gt;",
        content,
        flags=re.IGNORECASE,
    )
    escaped = re.sub(
        r"<evidence_chunk(\s+[^>]*)?>",
        "&lt;evidence_chunk\\1&gt;",
        escaped,
        flags=re.IGNORECASE,
    )
    return escaped


class PromptGuard:
    """Sanitizes inputs and builds secure prompt blocks for generation."""

    def __init__(self, config: PromptGuardrailConfigDTO | None = None) -> None:
        self.config = config or PromptGuardrailConfigDTO()
        self._compiled_patterns = [
            re.compile(pat, re.IGNORECASE) for pat in _INJECTION_PATTERNS
        ]

    def scan_for_injection(self, text: str) -> bool:
        """Scan text for prompt injection patterns. Return True if suspicious."""
        if not self.config.enable_injection_check or not text:
            return False

        # First clean invisible unicode and control characters before pattern matching
        normalized = sanitize_invisible_unicode_and_controls(text)

        for pat in self._compiled_patterns:
            if pat.search(normalized) or pat.search(text):
                logger.warning(
                    "Prompt injection pattern detected in input text",
                    pattern=pat.pattern,
                )
                try:
                    record_prompt_injection()
                except Exception:
                    pass
                return True
        return False

    def sanitize_and_format_evidence(
        self, chunks: list[RankedEvidenceDTO]
    ) -> tuple[str, list[RankedEvidenceDTO]]:
        """Filter invalid/injected evidence and format secure XML boundaries with randomized nonces."""
        safe_chunks: list[RankedEvidenceDTO] = []
        formatted_lines: list[str] = []

        for chunk in chunks:
            if not chunk:
                continue
            raw_content = (
                chunk.content if hasattr(chunk, "content") else chunk.get("content", "")
            )
            if not raw_content:
                logger.info(
                    "Filtering out empty evidence chunk before prompt construction",
                    chunk_id=str(
                        chunk.chunk_id
                        if hasattr(chunk, "chunk_id")
                        else chunk.get("chunk_id", "")
                    ),
                )
                continue

            cleaned_content = sanitize_invisible_unicode_and_controls(str(raw_content))
            content = cleaned_content.replace("\n", " ").strip()
            if not content:
                logger.info(
                    "Filtering out empty evidence chunk before prompt construction",
                    chunk_id=str(
                        chunk.chunk_id
                        if hasattr(chunk, "chunk_id")
                        else chunk.get("chunk_id", "")
                    ),
                )
                continue

            # Check injection patterns on raw and cleaned content
            if self.scan_for_injection(raw_content) or self.scan_for_injection(content):
                logger.warning(
                    "Filtering out suspicious evidence chunk due to prompt injection check",
                    chunk_id=str(
                        chunk.chunk_id
                        if hasattr(chunk, "chunk_id")
                        else chunk.get("chunk_id", "")
                    ),
                )
                continue

            safe_chunks.append(chunk)
            citation_index = len(safe_chunks)

            # Generate random boundary nonce for cryptographic boundary isolation
            nonce = secrets.token_hex(8)

            # Strictly escape any closing tags inside content so text cannot escape XML boundaries
            escaped_content = escape_evidence_delimiters(content)

            formatted_lines.append(
                f'<evidence_chunk id="{citation_index}" token="{nonce}">'
                f"[{citation_index}] {escaped_content}</evidence_chunk>"
            )

        return "\n".join(formatted_lines), safe_chunks
