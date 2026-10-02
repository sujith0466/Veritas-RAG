"""Unit tests for HtmlExtractor, DOM parsing, and metadata normalization."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

from backend.document.extractors import create_default_registry
from backend.document.extractors.html_extractor import HtmlExtractor
from backend.document.schemas.errors import DocumentDomainException

if TYPE_CHECKING:
    from backend.document.extractors.base import ExtractedContent


@pytest.fixture
def extractor() -> HtmlExtractor:
    return HtmlExtractor()


class TestHtmlExtractorContentExtraction:
    """Tests for HTML structure parsing, heading retention, and tag stripping."""

    @pytest.mark.asyncio
    async def test_normal_html_page_extraction(self, extractor: HtmlExtractor) -> None:
        html_doc = """<!DOCTYPE html>
        <html>
            <head>
                <title>Veritas RAG Architecture</title>
                <link rel="canonical" href="https://example.com/docs/architecture" />
                <meta name="description" content="Technical overview of Veritas RAG" />
            </head>
            <body>
                <header><nav><a href="/home">Home</a></nav></header>
                <main>
                    <h1>Veritas RAG Overview</h1>
                    <p>Veritas RAG provides high-assurance grounded retrieval.</p>
                    <h2>Key Components</h2>
                    <ul>
                        <li>Vector Storage</li>
                        <li>Hybrid Retrieval</li>
                        <li>Citation Extraction</li>
                    </ul>
                </main>
                <footer><p>Copyright 2026</p></footer>
            </body>
        </html>
        """
        stream = io.BytesIO(html_doc.encode("utf-8"))
        result: ExtractedContent = await extractor.extract(stream, "test.html", "text/html")

        assert "Veritas RAG Overview" in result.text
        assert "Veritas RAG provides high-assurance grounded retrieval." in result.text
        assert "Vector Storage" in result.text
        assert result.metadata.get("title") == "Veritas RAG Architecture"
        assert result.metadata.get("canonical_url") == "https://example.com/docs/architecture"
        assert result.metadata.get("description") == "Technical overview of Veritas RAG"
        assert result.word_count > 10

    @pytest.mark.asyncio
    async def test_scripts_styles_and_nav_are_stripped(self, extractor: HtmlExtractor) -> None:
        html_doc = """
        <html>
            <head>
                <style>body { font-size: 16px; color: red; }</style>
                <script>window.analytics.track('pageview'); function evil() { return 42; }</script>
            </head>
            <body>
                <nav><p>Navigational Link 1 | Navigational Link 2</p></nav>
                <h1>Clean Body Title</h1>
                <p>This is meaningful text that must be preserved in extraction.</p>
                <script type="text/javascript">console.log("drop me");</script>
                <aside><p>Sponsored Ads</p></aside>
            </body>
        </html>
        """
        stream = io.BytesIO(html_doc.encode("utf-8"))
        result = await extractor.extract(stream, "clean.html", "text/html")

        assert "Clean Body Title" in result.text
        assert "This is meaningful text that must be preserved in extraction." in result.text
        # Stripped elements
        assert "font-size: 16px" not in result.text
        assert "window.analytics" not in result.text
        assert "console.log" not in result.text
        assert "drop me" not in result.text

    @pytest.mark.asyncio
    async def test_html_entities_and_unicode_handling(self, extractor: HtmlExtractor) -> None:
        html_doc = """
        <html>
            <head><title>Entities &amp; Symbols &gt; Overview</title></head>
            <body>
                <h1>Tom &amp; Jerry&#39;s &quot;Great Adventure&quot;</h1>
                <p>Prices start at &euro;50 / &pound;40 for caf&eacute; delicacies in Z&uuml;rich.</p>
                <p>Japanese text: &#12371;&#12435;&#12395;&#12385;&#12399;&#19990;&#30028; (Konnichiwa Sekai).</p>
            </body>
        </html>
        """
        stream = io.BytesIO(html_doc.encode("utf-8"))
        result = await extractor.extract(stream, "entities.html", "text/html")

        assert 'Tom & Jerry\'s "Great Adventure"' in result.text
        assert "€50" in result.text or "50" in result.text
        assert "café" in result.text or "Zürich" in result.text
        assert result.metadata.get("title") == "Entities & Symbols > Overview"

    @pytest.mark.asyncio
    async def test_malformed_html_parsed_safely(self, extractor: HtmlExtractor) -> None:
        malformed_html = """
        <title>Malformed Document</title>
        <div>
            <h1>Header without closing tags
            <p>First paragraph with broken <br> tag
            <p>Second paragraph <b>unclosed bold
            <div>Nested without tags
        """
        stream = io.BytesIO(malformed_html.encode("utf-8"))
        result = await extractor.extract(stream, "malformed.html", "text/html")

        assert "Header without closing tags" in result.text
        assert "First paragraph with broken" in result.text
        assert result.word_count > 5

    @pytest.mark.asyncio
    async def test_empty_or_whitespace_html_raises_extract_error(self, extractor: HtmlExtractor) -> None:
        empty_html = "<html><head></head><body>    \n\n\t </body></html>"
        stream = io.BytesIO(empty_html.encode("utf-8"))

        with pytest.raises(DocumentDomainException) as exc:
            await extractor.extract(stream, "empty.html", "text/html")

        assert exc.value.code == "EXTRACT_001"
        assert "insufficient textual knowledge" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_completely_empty_stream_raises_extract_error(self, extractor: HtmlExtractor) -> None:
        stream = io.BytesIO(b"")
        with pytest.raises(DocumentDomainException) as exc:
            await extractor.extract(stream, "blank.html", "text/html")

        assert exc.value.code == "EXTRACT_001"
        assert "completely empty" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_extraction_determinism(self, extractor: HtmlExtractor) -> None:
        html_doc = """
        <html>
            <head><title>Deterministic Test</title></head>
            <body>
                <h1>Deterministic Knowledge Title</h1>
                <p>Every execution of this extraction must produce identical bytes and hashes.</p>
            </body>
        </html>
        """
        stream1 = io.BytesIO(html_doc.encode("utf-8"))
        res1 = await extractor.extract(stream1, "doc.html", "text/html")

        stream2 = io.BytesIO(html_doc.encode("utf-8"))
        res2 = await extractor.extract(stream2, "doc.html", "text/html")

        assert res1.text == res2.text
        assert res1.word_count == res2.word_count
        assert res1.metadata == res2.metadata


class TestExtractorRegistryIntegration:
    """Tests for registry routing and priority resolution."""

    def test_html_extractor_registered_with_highest_priority(self) -> None:
        registry = create_default_registry()
        matched_extractor = registry.get_extractor(mime_type="text/html", extension=".html")

        assert matched_extractor is not None
        assert isinstance(matched_extractor, HtmlExtractor)
        assert matched_extractor.capability.priority == 25
