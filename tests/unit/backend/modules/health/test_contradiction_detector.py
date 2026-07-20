import pytest
from backend.modules.health.services.contradiction_detector import ContradictionDetector

@pytest.mark.asyncio
async def test_detect_contradiction():
    detector = ContradictionDetector()
    documents = [
        {"id": "doc1", "content": "The company revenue was 50 million dollars."},
        {"id": "doc2", "content": "The company revenue was NOT 50 million dollars."}
    ]
    
    issues = await detector.detect(documents)
    assert len(issues) == 1
    assert issues[0].document_id == "doc1"
    assert "doc2" in issues[0].related_document_ids
