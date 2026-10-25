"""RQ worker entry point.

The worker imports this module. The function `run_pipeline` is the RQ task.

Usage (started by Docker Compose or manually):
    rq worker --url redis://redis:6379/0 default
"""

from __future__ import annotations

import uuid

from sceneforge.jobs.orchestrator import PipelineOrchestrator
from sceneforge.observability.logging import configure_logging, get_logger, set_job_id

configure_logging()
log = get_logger(__name__)


def run_pipeline(job_id: str) -> None:
    """RQ task entry point. Runs the full pipeline for *job_id*.

    All exceptions are caught here; the job is marked FAILED with a
    useful error code so the API can surface it to the caller.
    """
    set_job_id(job_id)
    log.info("pipeline_started", job_id=job_id)
    try:
        from sceneforge.jobs.database import get_session
        from sceneforge.jobs import repository as repo
        with get_session() as session:
            job = repo.get_job(session, uuid.UUID(job_id))
            if job and job.status in ("COMPLETED", "CANCELLED"):
                log.warning("pipeline_skipped_terminal_job", job_id=job_id, status=job.status)
                return
        orchestrator = PipelineOrchestrator(job_id=uuid.UUID(job_id))
        orchestrator.run()
        log.info("pipeline_completed", job_id=job_id)
    except Exception as exc:
        log.exception("pipeline_unhandled_error", job_id=job_id, exc=str(exc))
        # Attempt to mark job FAILED in DB
        try:
            from sceneforge.jobs.database import get_session
            from sceneforge.jobs import repository as repo
            with get_session() as session:
                job = repo.get_job(session, uuid.UUID(job_id))
                if job and job.status not in ("COMPLETED", "CANCELLED", "FAILED"):
                    repo.update_job_status(
                        session,
                        uuid.UUID(job_id),
                        status="FAILED",
                        error_code="PIPELINE_ERROR",
                        error_message="An unexpected error stopped the pipeline.",
                        retryable=True,
                    )
        except Exception as inner:
            log.error("failed_to_mark_job_failed", job_id=job_id, error=str(inner))
