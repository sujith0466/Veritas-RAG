"""High-Assurance HTML Knowledge Extractor.

Extracts structured, human-readable text and rich provenance metadata from raw HTML:
1. Strips non-content markup (scripts, styles, stylesheets, noscript, headers, footers, nav).
2. Extracts main body content, titles, headings, paragraphs, and lists.
3. Extracts canonical URL metadata from <link rel="canonical"> and OpenGraph tags.
4. Performs Unicode NFC normalization, entity unescaping, and whitespace cleanup.
5. Employs trafilatura as primary extraction engine with robust lxml DOM fallback.
6. Enforces minimum content threshold to prevent ingestion of empty/blank web pages.
"""

from __future__ import annotations

import html
import re
from typing import Any, BinaryIO

import lxml.html
import structlog

from backend.document.extractors.base import (
    BaseExtractor,
    ExtractedContent,
    ExtractorCapability,
)
from backend.document.extractors.normalizer import detect_language, normalize_text
from backend.document.schemas.errors import DocumentDomainException, DocumentErrorCode

logger = structlog.get_logger(__name__)


class HtmlExtractor(BaseExtractor):
    """Pluggable HTML extractor implementing BaseExtractor with priority 25."""

    MIN_TEXT_LENGTH: int = 20

    @property
    def capability(self) -> ExtractorCapability:
        return ExtractorCapability(
            name="HtmlExtractor",
            supported_mimes={"text/html", "application/xhtml+xml"},
            supported_extensions={".html", ".htm", ".xhtml"},
            priority=25,
            enabled=True,
        )

    @classmethod
    def _extract_lxml_metadata(cls, doc: Any) -> dict[str, Any]:
        """Extract metadata (title, canonical_url, description) from lxml document."""
        metadata: dict[str, Any] = {}

        # 1. Page Title
        title_nodes = doc.xpath("//title/text()")
        if title_nodes and isinstance(title_nodes, list) and str(title_nodes[0]).strip():
            metadata["title"] = html.unescape(str(title_nodes[0]).strip())
        else:
            og_title = doc.xpath("//meta[@property='og:title']/@content")
            if og_title and isinstance(og_title, list) and str(og_title[0]).strip():
                metadata["title"] = html.unescape(str(og_title[0]).strip())

        # 2. Canonical URL
        canonical_nodes = doc.xpath("//link[@rel='canonical']/@href")
        if canonical_nodes and isinstance(canonical_nodes, list) and str(canonical_nodes[0]).strip():
            metadata["canonical_url"] = str(canonical_nodes[0]).strip()
        else:
            og_url = doc.xpath("//meta[@property='og:url']/@content")
            if og_url and isinstance(og_url, list) and str(og_url[0]).strip():
                metadata["canonical_url"] = str(og_url[0]).strip()

        # 3. Meta Description
        desc_nodes = doc.xpath("//meta[@name='description']/@content")
        if desc_nodes and isinstance(desc_nodes, list) and str(desc_nodes[0]).strip():
            metadata["description"] = html.unescape(str(desc_nodes[0]).strip())

        return metadata

    @classmethod
    def _extract_lxml_text(cls, doc: Any) -> str:
        """Strip noise tags and extract structured text from lxml document."""
        for element in doc.xpath(
            "//script | //style | //noscript | //header | //footer | //nav | //aside | //svg | //iframe | //form"
        ):
            element.drop_tree()

        text_blocks: list[str] = []
        body = doc.body if doc.body is not None else doc

        target_tags = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "td", "th", "dt", "dd"}
        for el in body.iter():
            tag = el.tag.lower() if isinstance(el.tag, str) else ""
            if tag in target_tags:
                text = (el.text or "").strip()
                if text:
                    text_blocks.append(text)
                tail = (el.tail or "").strip()
                if tail:
                    text_blocks.append(tail)

        if not text_blocks:
            full_text = body.text_content()
            if full_text and full_text.strip():
                text_blocks.append(full_text.strip())

        return "\n\n".join(text_blocks)

    @classmethod
    def _extract_with_lxml(cls, raw_html: str) -> tuple[str, dict[str, Any]]:
        """Fallback DOM-based HTML extraction using lxml."""
        try:
            doc = lxml.html.fromstring(raw_html)
        except Exception as exc:
            raise DocumentDomainException(
                DocumentErrorCode.EXTRACT_001,
                f"Failed to parse HTML document structure: {exc}",
                detail={"error": str(exc)},
            ) from exc

        metadata = cls._extract_lxml_metadata(doc)
        extracted_text = cls._extract_lxml_text(doc)
        return extracted_text, metadata

    @classmethod
    def _extract_with_trafilatura(cls, raw_html: str) -> tuple[str, dict[str, Any]]:
        """Attempt extraction using trafilatura."""
        try:
            import trafilatura  # type: ignore[import-not-found]
        except ImportError:
            logger.debug("trafilatura package not present, using lxml DOM extractor")
            return "", {}

        metadata: dict[str, Any] = {}
        try:
            meta = trafilatura.extract_metadata(raw_html)
            if meta:
                for field in ("title", "url", "description", "author", "sitename"):
                    val = getattr(meta, field, None)
                    if val:
                        key = "canonical_url" if field == "url" else field
                        metadata[key] = val

            traf_text = trafilatura.extract(
                raw_html,
                include_links=True,
                include_tables=True,
                output_format="txt",
            )
            return (traf_text.strip() if traf_text else ""), metadata
        except Exception as traf_err:
            logger.warning("trafilatura extraction failed, falling back to lxml", error=str(traf_err))
            return "", {}

    async def extract(
        self, stream: BinaryIO, filename: str, mime_type: str
    ) -> ExtractedContent:
        """Extract plain text, structural metadata, and metrics from binary HTML stream."""
        try:
            raw_bytes = stream.read()
        except Exception as exc:
            raise DocumentDomainException(
                DocumentErrorCode.EXTRACT_001,
                f"Failed to read HTML binary stream for '{filename}': {exc}",
                detail={"filename": filename, "error": str(exc)},
            ) from exc

        if not raw_bytes:
            raise DocumentDomainException(
                DocumentErrorCode.EXTRACT_001,
                f"HTML document '{filename}' is completely empty (0 bytes).",
                detail={"filename": filename},
            )

        try:
            raw_html = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw_html = raw_bytes.decode("latin-1", errors="replace")

        metadata: dict[str, Any] = {"extractor": "HtmlExtractor", "mime_type": mime_type}

        traf_text, traf_meta = self._extract_with_trafilatura(raw_html)
        metadata.update(traf_meta)
        extracted_text = traf_text

        if not extracted_text:
            lxml_text, lxml_meta = self._extract_with_lxml(raw_html)
            extracted_text = lxml_text
            for k, v in lxml_meta.items():
                if k not in metadata or not metadata[k]:
                    metadata[k] = v

        # Unescape entities and normalize text
        unescaped_text = html.unescape(extracted_text)
        clean_text = normalize_text(unescaped_text)

        # Enforce minimum content threshold
        if len(clean_text.strip()) < self.MIN_TEXT_LENGTH:
            raise DocumentDomainException(
                DocumentErrorCode.EXTRACT_001,
                f"HTML document '{filename}' contains insufficient textual knowledge content (< {self.MIN_TEXT_LENGTH} characters).",
                detail={
                    "filename": filename,
                    "extracted_length": len(clean_text.strip()),
                    "min_length": self.MIN_TEXT_LENGTH,
                },
            )

        words = re.findall(r"\b\w+\b", clean_text)
        word_count = len(words)
        language = detect_language(clean_text)

        return ExtractedContent(
            text=clean_text,
            word_count=word_count,
            page_count=1,
            metadata=metadata,
            language=language,
            needs_ocr=False,
        )
