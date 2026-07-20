"""Unicode normalization and line break sanitization (`normalizer.py`).

Enforces NFC Unicode form (`ADR-005`), consistent `\\n` line breaks, and strips unparseable control characters.
"""

import re
import unicodedata

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
