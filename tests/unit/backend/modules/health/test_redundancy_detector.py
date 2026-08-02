import pytest

from backend.modules.health.services.redundancy_detector import RedundancyDetector


@pytest.mark.asyncio
async def test_detect_redundancy():
    detector = RedundancyDetector(threshold=0.8)
    documents = [
        {"id": "doc1", "content": "The quick brown fox jumps over the lazy dog."},
        {"id": "doc2", "content": "The quick brown fox jumps over the lazy dog."},
        {"id": "doc3", "content": "A completely different document here."}
    ]

    issues = await detector.detect(documents)
    assert len(issues) == 1
    assert issues[0].document_id == "doc1"
    assert "doc2" in issues[0].related_document_ids
