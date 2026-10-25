"""Unit tests for the job state machine (MH-07).

Tests:
- All valid transitions are accepted.
- Invalid transitions raise InvalidTransitionError.
- Terminal states have no outbound transitions.
- apply_transition returns correct TransitionResult.
- Unknown status values raise ValueError.
"""

import pytest

from sceneforge.jobs.state_machine import (
    InvalidTransitionError,
    JobStatus,
    TransitionResult,
    allowed_next_states,
    apply_transition,
    is_terminal,
    validate_transition,
)


class TestValidTransitions:
    """All valid forward pipeline transitions must be accepted."""

    @pytest.mark.parametrize("from_s, to_s", [
        (JobStatus.QUEUED, JobStatus.VALIDATING),
        (JobStatus.VALIDATING, JobStatus.PLANNING),
        (JobStatus.PLANNING, JobStatus.RETRIEVING),
        (JobStatus.RETRIEVING, JobStatus.RENDERING),
        (JobStatus.RENDERING, JobStatus.QA),
        (JobStatus.QA, JobStatus.COMPLETED),
    ])
    def test_forward_pipeline(self, from_s, to_s):
        validate_transition(from_s, to_s)  # must not raise

    @pytest.mark.parametrize("from_s", [
        JobStatus.QUEUED, JobStatus.VALIDATING, JobStatus.PLANNING,
        JobStatus.RETRIEVING, JobStatus.RENDERING, JobStatus.QA,
    ])
    def test_any_active_to_failed(self, from_s):
        validate_transition(from_s, JobStatus.FAILED)

    @pytest.mark.parametrize("from_s", [
        JobStatus.QUEUED, JobStatus.VALIDATING, JobStatus.PLANNING,
        JobStatus.RETRIEVING, JobStatus.RENDERING, JobStatus.QA,
        JobStatus.FAILED,
    ])
    def test_any_to_cancelled(self, from_s):
        validate_transition(from_s, JobStatus.CANCELLED)

    def test_failed_to_queued_retry(self):
        validate_transition(JobStatus.FAILED, JobStatus.QUEUED)


class TestInvalidTransitions:
    """Skipping states, reversing, and leaving terminal states must be rejected."""

    @pytest.mark.parametrize("from_s, to_s", [
        (JobStatus.QUEUED, JobStatus.PLANNING),       # skip VALIDATING
        (JobStatus.QUEUED, JobStatus.COMPLETED),      # skip everything
        (JobStatus.VALIDATING, JobStatus.QUEUED),     # reverse
        (JobStatus.RENDERING, JobStatus.PLANNING),    # reverse
        (JobStatus.COMPLETED, JobStatus.QUEUED),      # terminal → any
        (JobStatus.COMPLETED, JobStatus.FAILED),      # terminal → any
        (JobStatus.CANCELLED, JobStatus.QUEUED),      # terminal → any
        (JobStatus.QA, JobStatus.VALIDATING),         # backward skip
    ])
    def test_invalid_raises(self, from_s, to_s):
        with pytest.raises(InvalidTransitionError):
            validate_transition(from_s, to_s)


class TestTerminalStates:
    def test_completed_is_terminal(self):
        assert is_terminal(JobStatus.COMPLETED)

    def test_cancelled_is_terminal(self):
        assert is_terminal(JobStatus.CANCELLED)

    def test_queued_not_terminal(self):
        assert not is_terminal(JobStatus.QUEUED)

    def test_failed_not_terminal(self):
        # FAILED is not terminal because it allows retry to QUEUED
        assert not is_terminal(JobStatus.FAILED)

    def test_terminal_has_no_allowed_successors(self):
        assert allowed_next_states(JobStatus.COMPLETED) == set()
        assert allowed_next_states(JobStatus.CANCELLED) == set()


class TestApplyTransition:
    def test_valid_transition_returns_success(self):
        result = apply_transition(JobStatus.QUEUED, JobStatus.VALIDATING)
        assert isinstance(result, TransitionResult)
        assert result.success is True
        assert result.new_status == JobStatus.VALIDATING
        assert result.error is None

    def test_invalid_transition_returns_failure(self):
        result = apply_transition(JobStatus.COMPLETED, JobStatus.QUEUED)
        assert result.success is False
        assert result.new_status == JobStatus.COMPLETED  # unchanged
        assert result.error is not None

    def test_error_message_mentions_states(self):
        result = apply_transition(JobStatus.COMPLETED, JobStatus.QUEUED)
        assert "COMPLETED" in result.error
        assert "QUEUED" in result.error


class TestUnknownStatus:
    def test_unknown_from_status_raises(self):
        with pytest.raises(ValueError, match="Unknown job status"):
            validate_transition("BANANA", JobStatus.FAILED)

    def test_unknown_to_status_raises(self):
        with pytest.raises(ValueError, match="Unknown job status"):
            validate_transition(JobStatus.QUEUED, "BANANA")
