"""Job state machine with validated transitions and timestamps.

Valid states:
    QUEUED → VALIDATING → PLANNING → RETRIEVING → RENDERING → QA → COMPLETED
    Any state → FAILED  (with error_code + retryable flag)
    Any state → CANCELLED
    FAILED   → QUEUED   (explicit retry, subject to retry_count limit)

Raises InvalidTransitionError for any other transition.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    PLANNING = "PLANNING"
    RETRIEVING = "RETRIEVING"
    AWAITING_SELECTION = "AWAITING_SELECTION"
    RENDERING = "RENDERING"
    QA = "QA"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class InvalidTransitionError(Exception):
    """Raised when a state transition is not permitted."""

    def __init__(self, from_status: str, to_status: str) -> None:
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Invalid job state transition: {from_status!r} → {to_status!r}"
        )


# Defines which target states are reachable from each source state.
# Terminal states (COMPLETED, CANCELLED) have no outbound transitions.
_TRANSITIONS: dict[str, set[str]] = {
    JobStatus.QUEUED: {
        JobStatus.VALIDATING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.VALIDATING: {
        JobStatus.PLANNING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.PLANNING: {
        JobStatus.RETRIEVING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.RETRIEVING: {
        JobStatus.RENDERING,
        JobStatus.AWAITING_SELECTION,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.AWAITING_SELECTION: {
        JobStatus.RENDERING,
        JobStatus.RETRIEVING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.RENDERING: {
        JobStatus.QA,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.QA: {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.COMPLETED: set(),   # terminal
    JobStatus.CANCELLED: set(),   # terminal
    JobStatus.FAILED: {
        JobStatus.QUEUED,         # explicit retry only
        JobStatus.CANCELLED,
    },
}

# States that represent terminal outcomes (no further processing possible
# unless an explicit retry re-queues the job)
TERMINAL_STATES: frozenset[str] = frozenset(
    {JobStatus.COMPLETED, JobStatus.CANCELLED}
    # NOTE: FAILED is not terminal — it allows retry to QUEUED
)

# States where a worker is actively doing work
ACTIVE_STATES: frozenset[str] = frozenset(
    {
        JobStatus.VALIDATING,
        JobStatus.PLANNING,
        JobStatus.RETRIEVING,
        JobStatus.RENDERING,
        JobStatus.QA,
    }
)


def validate_transition(from_status: str, to_status: str) -> None:
    """Raise InvalidTransitionError if the transition is not permitted.

    Args:
        from_status: Current job status string.
        to_status:   Proposed next status string.

    Raises:
        InvalidTransitionError: If the transition is not in the allowed table.
        ValueError: If either status value is unrecognised.
    """
    # Normalise to enum values to catch typos early
    try:
        from_enum = JobStatus(from_status)
    except ValueError:
        raise ValueError(f"Unknown job status: {from_status!r}")
    try:
        to_enum = JobStatus(to_status)
    except ValueError:
        raise ValueError(f"Unknown job status: {to_status!r}")

    allowed = _TRANSITIONS.get(from_enum, set())
    if to_enum not in allowed:
        raise InvalidTransitionError(from_status, to_status)


def is_terminal(status: str) -> bool:
    """Return True if the status is a terminal state."""
    return status in TERMINAL_STATES


def allowed_next_states(status: str) -> set[str]:
    """Return the set of states reachable from *status*."""
    try:
        enum_status = JobStatus(status)
    except ValueError:
        return set()
    return {s.value for s in _TRANSITIONS.get(enum_status, set())}


# ---------------------------------------------------------------------------
# Transition helper — used by orchestrator and worker
# ---------------------------------------------------------------------------

class TransitionResult:
    """Carries the outcome of a state transition."""

    __slots__ = ("success", "new_status", "error")

    def __init__(
        self,
        *,
        success: bool,
        new_status: str,
        error: Optional[str] = None,
    ) -> None:
        self.success = success
        self.new_status = new_status
        self.error = error


def apply_transition(
    current_status: str,
    target_status: str,
) -> TransitionResult:
    """Validate and apply a transition; return a TransitionResult.

    Does NOT touch the database — the caller is responsible for persisting
    the new status via the repository.
    """
    try:
        validate_transition(current_status, target_status)
        return TransitionResult(success=True, new_status=target_status)
    except (InvalidTransitionError, ValueError) as exc:
        return TransitionResult(
            success=False,
            new_status=current_status,
            error=str(exc),
        )
