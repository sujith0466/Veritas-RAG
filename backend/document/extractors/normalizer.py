"""Unicode normalization, language detection, and line break sanitization (`normalizer.py`).

Enforces NFC Unicode form (`ADR-005`), consistent `\\n` line breaks, strips unparseable control characters,
and detects document primary language.
"""

import re
import unicodedata

import structlog

# Optional dependency handling for langdetect
try:
    from langdetect import detect
    from langdetect.lang_detect_exception import LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

logger = structlog.get_logger(__name__)

# Control characters except standard whitespace (\n, \r, \t)
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_text(text: str) -> str:
    """Normalize extracted document text (`NFC` form, line breaks, control characters).

    Args:
        text: Raw text extracted from document.

    Returns:
        Clean, NFC-normalized UTF-8 text string.
    """
    if not text:
        return ""

    # 1. Normalize line breaks (\r\n and \r -> \n)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Strip control characters except newline and tab
    text = CONTROL_CHAR_PATTERN.sub("", text)

    # 3. Unicode NFC Normalization (canonical decomposition followed by canonical composition)
    text = unicodedata.normalize("NFC", text)

    # 4. Collapse excessive blank lines (>2 consecutive newlines -> 2 newlines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def detect_language(text: str) -> str:
    """Detect the primary language of the text.

    Args:
        text: Normalized document text.

    Returns:
        ISO 639-1 language code (e.g., 'en', 'fr') or 'unknown'.
    """
    if not text.strip():
        return "unknown"

    if not LANGDETECT_AVAILABLE:
        logger.warning("langdetect not installed, defaulting to 'unknown'")
        return "unknown"

    try:
        # Detect on the first 10,000 chars to save time
        return detect(text[:10000])
    except LangDetectException as e:
        logger.warning("Language detection failed", error=str(e))
        return "unknown"
