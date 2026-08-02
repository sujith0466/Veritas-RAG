from backend.modules.chat.services.chat_orchestrator import compute_chat_reliability_score


def test_chat_reliability_all_checks_pass_returns_perfect_score():
    evidence = [
        {"chunk_id": "00000000-0000-0000-0000-000000000001", "document_id": "00000000-0000-0000-0000-000000000010", "document_version_id": "00000000-0000-0000-0000-000000000020", "tenant_id": "test_tenant", "rrf_score": 0.5, "final_rank": 1, "content": "RAGuard reduces hallucinations.", "score": 0.9},
    ]
    citations = [
        {"citation_index": 1, "chunk_id": "00000000-0000-0000-0000-000000000001", "document_id": "00000000-0000-0000-0000-000000000010", "document_version_id": "00000000-0000-0000-0000-000000000020", "tenant_id": "test_tenant", "rrf_score": 0.5, "final_rank": 1, "excerpt": "RAGuard reduces hallucinations."},
    ]

    score = compute_chat_reliability_score(
        answer_text="RAGuard reduces hallucinations. [1]",
        evidence_chunks=evidence,
        citations=citations,
        is_grounded=True,
    )

    assert score == 1.0


def test_chat_reliability_decreases_when_evidence_is_empty():
    evidence = [
        {"chunk_id": "00000000-0000-0000-0000-000000000001", "document_id": "00000000-0000-0000-0000-000000000010", "document_version_id": "00000000-0000-0000-0000-000000000020", "tenant_id": "test_tenant", "rrf_score": 0.5, "final_rank": 1, "content": "", "score": 0.9},
    ]
    citations = [
        {"citation_index": 1, "chunk_id": "00000000-0000-0000-0000-000000000001", "document_id": "00000000-0000-0000-0000-000000000010", "document_version_id": "00000000-0000-0000-0000-000000000020", "tenant_id": "test_tenant", "rrf_score": 0.5, "final_rank": 1, "excerpt": ""},
    ]

    score = compute_chat_reliability_score(
        answer_text="RAGuard reduces hallucinations. [1]",
        evidence_chunks=evidence,
        citations=citations,
        is_grounded=True,
    )

    assert score < 1.0
    assert score <= 0.4


def test_chat_reliability_decreases_when_citation_is_invalid():
    evidence = [
        {"chunk_id": "00000000-0000-0000-0000-000000000001", "document_id": "00000000-0000-0000-0000-000000000010", "document_version_id": "00000000-0000-0000-0000-000000000020", "tenant_id": "test_tenant", "rrf_score": 0.5, "final_rank": 1, "content": "RAGuard reduces hallucinations.", "score": 0.9},
    ]
    citations = []

    score = compute_chat_reliability_score(
        answer_text="RAGuard reduces hallucinations. [2]",
        evidence_chunks=evidence,
        citations=citations,
        is_grounded=False,
    )

    assert score < 0.6


def test_chat_reliability_decreases_when_claim_is_unsupported():
    evidence = [
        {"chunk_id": "00000000-0000-0000-0000-000000000001", "document_id": "00000000-0000-0000-0000-000000000010", "document_version_id": "00000000-0000-0000-0000-000000000020", "tenant_id": "test_tenant", "rrf_score": 0.5, "final_rank": 1, "content": "RAGuard reduces hallucinations.", "score": 0.9},
    ]
    citations = [
        {"citation_index": 1, "chunk_id": "00000000-0000-0000-0000-000000000001", "document_id": "00000000-0000-0000-0000-000000000010", "document_version_id": "00000000-0000-0000-0000-000000000020", "tenant_id": "test_tenant", "rrf_score": 0.5, "final_rank": 1, "excerpt": "RAGuard reduces hallucinations."},
    ]

    score = compute_chat_reliability_score(
        answer_text="RAGuard guarantees zero latency. [1]",
        evidence_chunks=evidence,
        citations=citations,
        is_grounded=False,
    )

    assert score < 0.8


def test_chat_reliability_decreases_for_partial_context_coverage():
    evidence = [
        {"chunk_id": "00000000-0000-0000-0000-000000000001", "document_id": "00000000-0000-0000-0000-000000000010", "document_version_id": "00000000-0000-0000-0000-000000000020", "tenant_id": "test_tenant", "rrf_score": 0.5, "final_rank": 1, "content": "RAGuard reduces hallucinations.", "score": 0.9},
    ]
    citations = [
        {"citation_index": 1, "chunk_id": "00000000-0000-0000-0000-000000000001", "document_id": "00000000-0000-0000-0000-000000000010", "document_version_id": "00000000-0000-0000-0000-000000000020", "tenant_id": "test_tenant", "rrf_score": 0.5, "final_rank": 1, "excerpt": "RAGuard reduces hallucinations."},
    ]

    score = compute_chat_reliability_score(
        answer_text="RAGuard reduces hallucinations. [1] It also guarantees zero latency.",
        evidence_chunks=evidence,
        citations=citations,
        is_grounded=False,
    )

    assert score < 0.8
