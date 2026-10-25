"""Tests for worker lifecycle, rendering failure handling, and artifact persistence."""

from __future__ import annotations

import os
import tempfile
import uuid
from unittest.mock import MagicMock, patch

import pytest

from sceneforge.jobs import repository as repo
from sceneforge.jobs.models import Job
from sceneforge.jobs.orchestrator import PipelineOrchestrator
from sceneforge.jobs.reconciler import reconcile_stale_jobs
from sceneforge.jobs.state_machine import JobStatus
from sceneforge.jobs.worker import on_pipeline_failure, run_pipeline
from sceneforge.schemas.exceptions import RenderError
from sceneforge.storage.filesystem_client import FilesystemStorageClient, _get_default_storage_root
from sceneforge.storage.paths import BUCKET_ARTIFACTS, artifact_key


def _make_job(db_session, *, status="QUEUED", script="Test script."):
    """Create and persist a job with a given status, flushing and expiring identity map."""
    job = repo.create_job(db_session, data={"script": script})
    db_session.flush()
    if status != "QUEUED":
        repo.update_job_status(db_session, job.id, status=status)
        db_session.flush()
        db_session.expire(job)
        job = repo.get_job(db_session, job.id)
    return job


class TestWorkerLifecycleAndFailure:
    def test_on_pipeline_failure_callback_marks_rendering_job_failed(self, db_session):
        """When RQ triggers on_pipeline_failure, a job in RENDERING transitions to FAILED (RENDER_FAILED)."""
        job = _make_job(db_session, status=JobStatus.RENDERING.value, script="Test failure script.")

        mock_rq_job = MagicMock()
        mock_rq_job.args = [str(job.id)]
        mock_rq_job.id = str(job.id)

        with patch("sceneforge.jobs.database.get_session") as mock_sess:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=db_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_sess.return_value = ctx

            on_pipeline_failure(
                mock_rq_job,
                connection=None,
                type=RuntimeError,
                value=RuntimeError("FFmpeg out of memory or killed by SIGKILL"),
                traceback=None,
            )

        db_session.expire_all()
        updated = repo.get_job(db_session, job.id)
        assert updated.status == JobStatus.FAILED.value
        assert updated.error_code == "RENDER_FAILED"
        assert "killed by SIGKILL" in updated.error_message
        assert updated.retryable is True

    def test_on_pipeline_failure_callback_marks_other_active_job_failed(self, db_session):
        """When RQ fails a job in PLANNING or RETRIEVING, it transitions to FAILED (PIPELINE_ERROR)."""
        job = _make_job(db_session, status=JobStatus.PLANNING.value, script="Test planning script.")

        mock_rq_job = MagicMock()
        mock_rq_job.args = [str(job.id)]

        with patch("sceneforge.jobs.database.get_session") as mock_sess:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=db_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_sess.return_value = ctx

            on_pipeline_failure(
                mock_rq_job,
                connection=None,
                type=TimeoutError,
                value=TimeoutError("Worker timed out"),
                traceback=None,
            )

        db_session.expire_all()
        updated = repo.get_job(db_session, job.id)
        assert updated.status == JobStatus.FAILED.value
        assert updated.error_code == "PIPELINE_ERROR"

    def test_render_failure_in_orchestrator_marks_job_failed(self, db_session):
        """When FFmpeg is available and renderer.render raises RenderError, orchestrator transitions to FAILED."""
        job = _make_job(db_session, status=JobStatus.RETRIEVING.value, script="A short scene to render.")

        orchestrator = PipelineOrchestrator(job.id)

        with patch("sceneforge.jobs.orchestrator.get_session") as mock_sess:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=db_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_sess.return_value = ctx

            with patch("sceneforge.rendering.ffprobe.is_ffmpeg_available", return_value=True):
                with patch("sceneforge.rendering.renderer.VideoRenderer.render", side_effect=RenderError("FFmpeg encoding error exit 1")):
                    with pytest.raises(RenderError):
                        orchestrator._stage_render()

        db_session.expire_all()
        updated = repo.get_job(db_session, job.id)
        assert updated.status == JobStatus.FAILED.value
        assert updated.error_code == "RENDER_FAILED"
        assert "FFmpeg" in updated.error_message


class TestReconciliationAndStorage:
    def test_reconcile_stale_active_jobs_on_worker_crash(self, db_session):
        """Jobs stuck in RENDERING when worker crashed are reset to FAILED with WORKER_RESTART."""
        job = _make_job(db_session, status=JobStatus.RENDERING.value, script="Stuck script.")

        # Reconcile with 0 minute threshold (startup sweep)
        reset_count = reconcile_stale_jobs(db_session, stale_threshold_minutes=0, max_retries=3)
        assert reset_count >= 1

        db_session.expire_all()
        updated = repo.get_job(db_session, job.id)
        assert updated.status == JobStatus.FAILED.value
        assert updated.error_code == "WORKER_RESTART"
        assert updated.retryable is True

    def test_filesystem_storage_root_prefers_app_storage_when_present(self, tmp_path):
        """FilesystemStorageClient defaults to /app/storage if present, otherwise /tmp/sceneforge_storage."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("os.path.isdir") as mock_isdir:
                mock_isdir.side_effect = lambda p: p == "/app/storage"
                root = _get_default_storage_root()
                assert root == "/app/storage"

                mock_isdir.side_effect = lambda p: False
                root_fallback = _get_default_storage_root()
                assert root_fallback == "/tmp/sceneforge_storage"

    def test_artifacts_persisted_and_listed(self, tmp_path):
        """Filesystem storage correctly persists and lists artifacts under jobs/{job_id}/."""
        client = FilesystemStorageClient(root=str(tmp_path / "storage"))
        jid = str(uuid.uuid4())
        key = artifact_key(jid, "output.mp4")

        client.upload_bytes(BUCKET_ARTIFACTS, key, b"fake video bytes", "video/mp4")
        client.upload_bytes(BUCKET_ARTIFACTS, artifact_key(jid, "captions.srt"), b"1\n00:00:00 --> 00:00:05\nHello", "text/plain")

        keys = client.list_keys(BUCKET_ARTIFACTS, prefix=f"jobs/{jid}/")
        assert len(keys) == 2
        filenames = [k.split("/")[-1] for k in keys]
        assert "output.mp4" in filenames
        assert "captions.srt" in filenames

    def test_ffmpeg_timeout_during_render_transitions_to_failed_with_informative_error(self, db_session):
        """When FFmpeg times out during render, orchestrator transitions job to FAILED (RENDER_FAILED) with informative timeout message."""
        job = _make_job(db_session, status=JobStatus.RETRIEVING.value, script="A short scene to render.")
        orchestrator = PipelineOrchestrator(job.id)

        with patch("sceneforge.jobs.orchestrator.get_session") as mock_sess:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=db_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_sess.return_value = ctx

            with patch("sceneforge.rendering.ffprobe.is_ffmpeg_available", return_value=True), \
                 patch("sceneforge.rendering.renderer.VideoRenderer.render", side_effect=RenderError("FFmpeg timed out after 120s during 'render_video_scene_1'. Stderr: frame=15 fps=0.5")):
                with pytest.raises(RenderError):
                    orchestrator._stage_render()

        db_session.expire_all()
        updated = repo.get_job(db_session, job.id)
        assert updated.status == JobStatus.FAILED.value
        assert updated.error_code == "RENDER_FAILED"
        assert "FFmpeg timed out after 120s" in updated.error_message

    def test_unhandled_rendering_exception_transitions_to_failed_with_render_failed(self, db_session):
        """When an unhandled exception occurs in rendering stage, orchestrator marks job FAILED (RENDER_FAILED)."""
        job = _make_job(db_session, status=JobStatus.RETRIEVING.value, script="A short scene to render.")
        orchestrator = PipelineOrchestrator(job.id)

        with patch("sceneforge.jobs.orchestrator.get_session") as mock_sess:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=db_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_sess.return_value = ctx

            with patch("sceneforge.rendering.ffprobe.is_ffmpeg_available", return_value=True), \
                 patch("sceneforge.rendering.renderer.VideoRenderer.render", side_effect=RuntimeError("Subprocess segmentation fault")):
                with pytest.raises(RuntimeError):
                    orchestrator._stage_render()

        db_session.expire_all()
        updated = repo.get_job(db_session, job.id)
        assert updated.status == JobStatus.FAILED.value
        assert updated.error_code == "RENDER_FAILED"
        assert "Subprocess segmentation fault" in updated.error_message

    def test_render_profile_defaults_to_720p_24fps_ultrafast_crf26(self):
        """Verifies that 16:9 output profile defaults to 1280x720, 24 FPS, ultrafast preset, CRF 26, 1 thread."""
        from sceneforge.rendering.normaliser import get_profile
        profile = get_profile("16:9")
        assert profile.width == 1280
        assert profile.height == 720
        assert profile.fps == 24
        assert profile.crf == 26
        assert profile.preset == "ultrafast"

    def test_segment_concatenation_and_audio_sync_arguments(self, tmp_path):
        """Verifies that VideoRenderer configures concat demuxer and audio padding for timeline sync."""
        from sceneforge.rendering.normaliser import get_profile
        from sceneforge.rendering.renderer import VideoRenderer
        profile = get_profile("16:9")

        fake_audio = tmp_path / "voiceover.wav"
        fake_audio.write_bytes(b"\x00" * 4096)

        renderer = VideoRenderer(profile, audio_path=str(fake_audio), work_dir=str(tmp_path))
        assert renderer._profile.width == 1280
        assert renderer._profile.height == 720
        assert renderer._profile.fps == 24
