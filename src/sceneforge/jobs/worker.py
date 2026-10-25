"""RQ worker entry point.

The worker imports this module. The function `run_pipeline` is the RQ task.

Usage (started by Docker Compose or manually):
    rq worker --url redis://redis:6379/0 default
"""

from __future__ import annotations

import os
import signal
import sys
import uuid

from sceneforge.jobs.orchestrator import PipelineOrchestrator
from sceneforge.observability.logging import configure_logging, get_logger, set_job_id

configure_logging()
log = get_logger(__name__)


def on_pipeline_failure(job, connection, type, value, traceback) -> None:
    """RQ failure callback invoked by worker when a job fails or is killed.

    Ensures the job in PostgreSQL transitions to terminal FAILED state even
    if the child workhorse process was killed, timed out, or crashed.
    """
    job_id = None
    if job and job.args:
        job_id = str(job.args[0])
    elif job and job.id:
        job_id = str(job.id)

    if not job_id:
        log.warning("rq_on_pipeline_failure_missing_job_id")
        return

    set_job_id(job_id)
    log.error(
        "rq_on_pipeline_failure_triggered",
        job_id=job_id,
        exc_type=str(type),
        exc_val=str(value),
    )

    try:
        from sceneforge.jobs.database import get_session
        from sceneforge.jobs import repository as repo

        with get_session() as session:
            job_obj = repo.get_job(session, uuid.UUID(job_id))
            if job_obj and job_obj.status not in ("COMPLETED", "CANCELLED", "FAILED"):
                err_code = "RENDER_FAILED" if job_obj.status == "RENDERING" else "PIPELINE_ERROR"
                err_msg = str(value) if value else "Background worker execution failed or was terminated."
                repo.update_job_status(
                    session,
                    uuid.UUID(job_id),
                    status="FAILED",
                    error_code=err_code,
                    error_message=err_msg,
                    retryable=True,
                )
                log.info("job_transitioned_to_failed_by_rq_callback", job_id=job_id, error_code=err_code)
    except Exception as exc:
        log.error("failed_to_update_job_in_rq_failure_callback", job_id=job_id, error=str(exc))


def run_pipeline(job_id: str) -> None:
    """RQ task entry point. Runs the full pipeline for *job_id*.

    Catches all exceptions (including BaseException / timeout / signal)
    and ensures the job is marked FAILED in DB if interrupted.
    """
    set_job_id(job_id)
    log.info("pipeline_started", job_id=job_id)

    # Register signal handler for graceful shutdown on SIGTERM (e.g. Render redeploy)
    def _sigterm_handler(signum, frame):
        log.warning("worker_received_sigterm_marking_failed", job_id=job_id)
        try:
            from sceneforge.jobs.database import get_session
            from sceneforge.jobs import repository as repo
            with get_session() as session:
                j = repo.get_job(session, uuid.UUID(job_id))
                if j and j.status not in ("COMPLETED", "CANCELLED", "FAILED"):
                    repo.update_job_status(
                        session,
                        uuid.UUID(job_id),
                        status="FAILED",
                        error_code="WORKER_TERMINATED",
                        error_message="Worker terminated by SIGTERM (service restart or deployment).",
                        retryable=True,
                    )
        except Exception as e:
            log.error("sigterm_db_update_failed", job_id=job_id, error=str(e))
        sys.exit(143)

    prev_sigterm = None
    try:
        prev_sigterm = signal.signal(signal.SIGTERM, _sigterm_handler)
    except (ValueError, AttributeError):
        # On Windows or non-main thread, signal registration may not be supported
        pass

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
    except BaseException as exc:
        log.exception("pipeline_unhandled_error", job_id=job_id, exc=str(exc))
        try:
            from sceneforge.jobs.database import get_session
            from sceneforge.jobs import repository as repo
            with get_session() as session:
                job = repo.get_job(session, uuid.UUID(job_id))
                if job and job.status not in ("COMPLETED", "CANCELLED", "FAILED"):
                    err_code = "RENDER_FAILED" if job.status == "RENDERING" else "PIPELINE_ERROR"
                    repo.update_job_status(
                        session,
                        uuid.UUID(job_id),
                        status="FAILED",
                        error_code=err_code,
                        error_message=f"Pipeline error: {exc}",
                        retryable=True,
                    )
        except Exception as inner:
            log.error("failed_to_mark_job_failed", job_id=job_id, error=str(inner))
        raise
    finally:
        if prev_sigterm is not None:
            try:
                signal.signal(signal.SIGTERM, prev_sigterm)
            except (ValueError, AttributeError):
                pass
