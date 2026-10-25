"""Unit tests verifying PipelineOrchestrator handling of voiceover audio."""

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest

from sceneforge.jobs import repository as repo
from sceneforge.jobs.state_machine import JobStatus
from sceneforge.jobs.orchestrator import PipelineOrchestrator


class TestOrchestratorVoiceover:
    def test_audio_only_orchestration(self, db_session):
        """Audio-only job uses uploaded voiceover audio, not TTS."""
        fake_audio = b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00isomiso2" + b"\x00" * 32
        
        job = repo.create_job(
            db_session,
            data={
                "voiceover_path": "uploads/voiceover_unit_test.m4a",
                "aspect_ratio": "16:9",
            },
        )
        db_session.flush()
        job_id = job.id

        orchestrator = PipelineOrchestrator(job_id)
        
        # Mock storage download
        orchestrator.storage = MagicMock()
        orchestrator.storage.object_exists.return_value = True
        orchestrator.storage.download_bytes.return_value = fake_audio

        with patch("sceneforge.jobs.orchestrator.get_session") as mock_sess:
            session_ctx = MagicMock()
            session_ctx.__enter__ = MagicMock(return_value=db_session)
            session_ctx.__exit__ = MagicMock(return_value=False)
            mock_sess.return_value = session_ctx

            # Run validate stage
            orchestrator._stage_validate()
            db_job = repo.get_job(db_session, job_id)
            assert db_job.status == JobStatus.VALIDATING

            # Run plan stage
            orchestrator._stage_plan()

        # Verify that voiceover audio was written to temp file for the renderer
        assert orchestrator._narration_audio_path != ""
        assert os.path.isfile(orchestrator._narration_audio_path)
        with open(orchestrator._narration_audio_path, "rb") as f:
            written_bytes = f.read()
        assert written_bytes == fake_audio

        # Cleanup temp file
        try:
            os.unlink(orchestrator._narration_audio_path)
        except OSError:
            pass

    def test_neither_script_nor_voiceover_fails_validation(self, db_session):
        """Job without script and without voiceover fails with EMPTY_INPUT."""
        job = repo.create_job(
            db_session,
            data={
                "aspect_ratio": "16:9",
            },
        )
        db_session.flush()
        job_id = job.id

        orchestrator = PipelineOrchestrator(job_id)

        with patch("sceneforge.jobs.orchestrator.get_session") as mock_sess:
            session_ctx = MagicMock()
            session_ctx.__enter__ = MagicMock(return_value=db_session)
            session_ctx.__exit__ = MagicMock(return_value=False)
            mock_sess.return_value = session_ctx

            with pytest.raises(StopIteration):
                orchestrator._stage_validate()

        db_session.commit()
        db_job = repo.get_job(db_session, job_id)
        assert db_job.status == JobStatus.FAILED
        assert db_job.error_code == "EMPTY_INPUT"

    def test_blank_script_without_voiceover_fails_validation(self, db_session):
        """Job with blank script and no voiceover fails with EMPTY_SCRIPT."""
        job = repo.create_job(
            db_session,
            data={
                "script": "   ",
                "aspect_ratio": "16:9",
            },
        )
        db_session.flush()
        job_id = job.id

        orchestrator = PipelineOrchestrator(job_id)

        with patch("sceneforge.jobs.orchestrator.get_session") as mock_sess:
            session_ctx = MagicMock()
            session_ctx.__enter__ = MagicMock(return_value=db_session)
            session_ctx.__exit__ = MagicMock(return_value=False)
            mock_sess.return_value = session_ctx

            with pytest.raises(StopIteration):
                orchestrator._stage_validate()

        db_session.commit()
        db_job = repo.get_job(db_session, job_id)
        assert db_job.status == JobStatus.FAILED
        assert db_job.error_code == "EMPTY_SCRIPT"
