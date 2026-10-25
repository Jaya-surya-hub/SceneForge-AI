"""Job reconciler for worker restart recovery (HC-22).

Detects jobs stuck in ACTIVE_STATES due to worker crash, container restart,
or network partitions, and transitions them safely to FAILED with error_code
WORKER_RESTART. If the job hasn't exceeded max_retries, it remains retryable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from sceneforge.jobs.models import Job
from sceneforge.jobs.state_machine import ACTIVE_STATES, JobStatus
from sceneforge.observability.logging import get_logger

log = get_logger(__name__)


def find_stale_jobs(
    session: Session,
    *,
    stale_threshold_minutes: int = 30,
) -> list[Job]:
    """Find jobs in ACTIVE_STATES whose last update is older than the threshold."""
    active_values = [s.value if hasattr(s, "value") else str(s) for s in ACTIVE_STATES]
    if stale_threshold_minutes <= 0:
        stmt = select(Job).where(Job.status.in_(active_values))
        return list(session.scalars(stmt))
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_threshold_minutes)
    stmt = (
        select(Job)
        .where(
            Job.status.in_(active_values),
            Job.updated_at < cutoff,
        )
    )
    return list(session.scalars(stmt))


def reconcile_stale_jobs(
    session: Session,
    *,
    stale_threshold_minutes: int = 30,
    max_retries: int = 3,
) -> int:
    """Detect and reset stale active jobs to FAILED."""
    stale_jobs = find_stale_jobs(session, stale_threshold_minutes=stale_threshold_minutes)
    count = 0
    now = datetime.now(timezone.utc)

    for job in stale_jobs:
        job.retry_count += 1
        is_retryable = job.retry_count < max_retries
        job.status = JobStatus.FAILED.value
        job.error_code = "WORKER_RESTART"
        job.error_message = (
            f"Worker crashed or was restarted while job was in progress. "
            f"Retry count: {job.retry_count}/{max_retries}."
        )
        job.retryable = is_retryable
        job.updated_at = now
        job.completed_at = now
        count += 1
        log.warning(
            "reconciled_stale_job",
            job_id=str(job.id),
            retry_count=job.retry_count,
            retryable=is_retryable,
        )

    if count:
        session.flush()

    return count
