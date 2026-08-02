from backend.modules.validation.services.claim_extractor import ClaimExtractor


def test_extract_atomic_claims():
    extractor = ClaimExtractor()
    text = "The sky is blue [1]. Water is wet."
    results = extractor.extract_atomic_claims(text)

    assert len(results) == 2
    assert results[0][0] == "The sky is blue [1]."
    assert results[0][1] == 1
    assert results[1][0] == "Water is wet."
    assert results[1][1] is None
