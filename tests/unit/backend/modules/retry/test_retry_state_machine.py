import pytest

from backend.modules.confidence.schemas.confidence_dto import ConfidenceAction
from backend.modules.retry.schemas.errors import MaxRetriesExceeded, NonMonotonicImprovement
from backend.modules.retry.schemas.retry_dto import RetryState
from backend.modules.retry.services.state_machine import RetryStateMachine


def test_retry_machine_proceed_on_first_attempt():
    sm = RetryStateMachine(correlation_id="corr_1", original_query="What is RAG?")
    sm.record_retrieval_complete()
    sm.record_confidence_evaluation(confidence_score=85.0, action=ConfidenceAction.PROCEED)
    assert sm.state == RetryState.GENERATING
    sm.record_generation_complete()
    assert sm.state == RetryState.COMPLETED


def test_retry_machine_allows_one_retry_with_improvement():
    sm = RetryStateMachine(correlation_id="corr_2", original_query="How does chunking work?")

    # First attempt - RETRY
    sm.record_retrieval_complete()
    sm.record_confidence_evaluation(confidence_score=55.0, action=ConfidenceAction.RETRY)
    assert sm.state == RetryState.RETRYING

    # Second attempt - PROCEED (improved by 22 points)
    sm.record_retrieval_complete()
    sm.record_confidence_evaluation(confidence_score=77.0, action=ConfidenceAction.PROCEED, rewrite_applied=True)
    assert sm.state == RetryState.GENERATING


def test_retry_machine_aborts_on_max_retries():
    sm = RetryStateMachine(correlation_id="corr_3", original_query="Confusing query", max_retries=1)

    sm.record_retrieval_complete()
    sm.record_confidence_evaluation(confidence_score=40.0, action=ConfidenceAction.RETRY)
    assert sm.state == RetryState.RETRYING

    sm.record_retrieval_complete()
    # Attempt 2 also RETRY but exceeds max_retries=1 (already used 1 retry)
    with pytest.raises(MaxRetriesExceeded):
        sm.record_confidence_evaluation(confidence_score=55.0, action=ConfidenceAction.RETRY)
    assert sm.state == RetryState.ABORTED


def test_retry_machine_aborts_on_non_monotonic_improvement():
    sm = RetryStateMachine(correlation_id="corr_4", original_query="Stagnant query")

    sm.record_retrieval_complete()
    sm.record_confidence_evaluation(confidence_score=55.0, action=ConfidenceAction.RETRY)
    assert sm.state == RetryState.RETRYING

    sm.record_retrieval_complete()
    # Score gets worse — only improved by 1 point, below the 2.0 threshold
    with pytest.raises(NonMonotonicImprovement):
        sm.record_confidence_evaluation(confidence_score=56.0, action=ConfidenceAction.RETRY)
    assert sm.state == RetryState.ABORTED


def test_retry_machine_clarification_state():
    sm = RetryStateMachine(correlation_id="corr_5", original_query="What is apple?")
    sm.record_retrieval_complete()
    sm.record_confidence_evaluation(confidence_score=30.0, action=ConfidenceAction.CLARIFY)
    assert sm.state == RetryState.CLARIFICATION_REQUESTED


def test_retry_machine_abort_on_abort_action():
    sm = RetryStateMachine(correlation_id="corr_6", original_query="Insufficient query")
    sm.record_retrieval_complete()
    sm.record_confidence_evaluation(confidence_score=10.0, action=ConfidenceAction.ABORT)
    assert sm.state == RetryState.ABORTED


def test_retry_machine_hard_cap_enforced():
    # max_retries cap is 3, even if user passes 10
    sm = RetryStateMachine(correlation_id="corr_7", original_query="Any", max_retries=10)
    assert sm.context.max_retries == 3
