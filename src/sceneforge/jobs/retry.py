"""Retry policy for pipeline stages.

Distinguishes transient errors (retryable) from permanent errors (non-retryable).
Uses configurable exponential backoff.

Default configuration (from environment):
    JOB_MAX_RETRIES=3
    JOB_RETRY_BACKOFF_BASE=2   # delay = base ^ attempt (seconds)
"""

from __future__ import annotations

import os
import time
from typing import Callable, TypeVar

from sceneforge.observability.logging import get_logger
from sceneforge.schemas.exceptions import SceneForgeError

log = get_logger(__name__)

T = TypeVar("T")

_MAX_RETRIES = int(os.getenv("JOB_MAX_RETRIES", "3"))
_BACKOFF_BASE = float(os.getenv("JOB_RETRY_BACKOFF_BASE", "2"))


def retry_stage(
    fn: Callable[[], T],
    *,
    stage_name: str,
    job_id: str,
    max_retries: int = _MAX_RETRIES,
    backoff_base: float = _BACKOFF_BASE,
) -> T:
    """Execute *fn* with retry logic.

    Retries only for transient (retryable=True) SceneForgeErrors and
    generic Exception. Non-retryable SceneForgeErrors propagate immediately.

    Args:
        fn:           Callable to execute.
        stage_name:   Name for logging.
        job_id:       Job ID for logging.
        max_retries:  Maximum retry attempts.
        backoff_base: Exponential backoff base in seconds.

    Returns:
        Result of *fn*.

    Raises:
        SceneForgeError or Exception after all retries exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except SceneForgeError as exc:
            if not exc.retryable or attempt >= max_retries:
                log.warning(
                    "stage_failed_permanent",
                    stage=stage_name,
                    job_id=job_id,
                    attempt=attempt,
                    error=exc.message,
                    code=exc.code,
                )
                raise
            last_exc = exc
        except Exception as exc:
            if attempt >= max_retries:
                log.error(
                    "stage_failed_exhausted",
                    stage=stage_name,
                    job_id=job_id,
                    attempt=attempt,
                    error=str(exc),
                )
                raise
            last_exc = exc

        delay = backoff_base ** attempt
        log.info(
            "stage_retrying",
            stage=stage_name,
            job_id=job_id,
            attempt=attempt + 1,
            delay_s=delay,
        )
        time.sleep(delay)

    raise last_exc  # type: ignore[misc]
