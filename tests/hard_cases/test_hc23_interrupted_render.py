"""HC-23 — Interrupted Render Recovery.

Tests for verifying system behavior when rendering is interrupted or fails:
1. Simulating a render failing midway through execution.
2. Verifying temporary files in work_dir are cleaned up.
3. Verifying incomplete output is never published as a successful final artifact.
4. Verifying cache consistency (atomic tmp-to-dest rename prevents partial segments).
5. Verifying retry behavior, state transitions, and artifact integrity.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from unittest.mock import MagicMock, patch

import pytest

from sceneforge.jobs import repository as repo
from sceneforge.jobs.models import Job
from sceneforge.jobs.state_machine import JobStatus, validate_transition
from sceneforge.quality.checker import QAChecker, QAReport
from sceneforge.rendering.cache import CacheKey, RenderCache, build_cache_key
from sceneforge.rendering.normaliser import OutputProfile, get_profile
from sceneforge.rendering.renderer import VideoRenderer
from sceneforge.schemas.exceptions import RenderError
from sceneforge.timeline.builder import Timeline, TimelineEntry


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_timeline():
    return Timeline(
        job_id="test-job-hc23",
        entries=[
            TimelineEntry(
                scene_id="scene-001",
                scene_index=0,
                narration_text="Intro scene.",
                start_time=0.0,
                end_time=2.5,
                duration=2.5,
                visual_concept="Intro",
                suggested_visual_type="typography_card",
                intended_meaning="Introduction",
                search_queries=[],
                caption_text="Intro scene.",
                route="card",
            ),
            TimelineEntry(
                scene_id="scene-002",
                scene_index=1,
                narration_text="Second scene.",
                start_time=2.5,
                end_time=5.0,
                duration=2.5,
                visual_concept="Body",
                suggested_visual_type="typography_card",
                intended_meaning="Body content",
                search_queries=[],
                caption_text="Second scene.",
                route="card",
            ),
        ],
        total_duration=5.0,
    )


# ---------------------------------------------------------------------------
# Tests: Temp file cleanup on render interruption
# ---------------------------------------------------------------------------

class TestRenderTempFileCleanup:
    def test_renderer_cleans_owned_work_dir_on_error(self, sample_timeline):
        """When VideoRenderer owns work_dir and an error occurs, it must rmtree the work_dir."""
        profile = get_profile("16:9")
        renderer = VideoRenderer(profile)

        # Mock _render_inner to raise RenderError and capture the work_dir path
        captured_work_dir = []

        def failing_render_inner(timeline, output_path, job_id, work_dir):
            captured_work_dir.append(work_dir)
            assert os.path.isdir(work_dir)
            # Create a dummy partial file inside work_dir
            with open(os.path.join(work_dir, "partial.tmp"), "wb") as f:
                f.write(b"partial video data")
            raise RenderError("Simulated FFmpeg interruption / crash")

        with patch.object(renderer, "_render_inner", side_effect=failing_render_inner):
            with pytest.raises(RenderError, match="Simulated FFmpeg interruption"):
                renderer.render(sample_timeline, "fake_out.mp4")

        assert len(captured_work_dir) == 1
        work_dir = captured_work_dir[0]
        # Must be cleaned up by finally block
        assert not os.path.exists(work_dir), "Working directory was not cleaned up on RenderError!"

    def test_orchestrator_stage_render_cleans_work_dir_on_unhandled_exception(self, db_session):
        """PipelineOrchestrator._stage_render cleans up work_dir even on unhandled exception."""
        from sceneforge.jobs.orchestrator import PipelineOrchestrator

        job = repo.create_job(db_session, data={"script": "Test script"})
        job.status = "RETRIEVING"
        db_session.flush()

        orchestrator = PipelineOrchestrator(job.id)

        # We simulate an unexpected exception occurring during render stage
        captured_dir = []
        original_mkdtemp = tempfile.mkdtemp

        def custom_mkdtemp(*args, **kwargs):
            path = original_mkdtemp(*args, **kwargs)
            if "sf_render_" in path:
                captured_dir.append(path)
            return path

        with patch("sceneforge.jobs.orchestrator.get_session") as mock_sess:
            session_ctx = MagicMock()
            session_ctx.__enter__ = MagicMock(return_value=db_session)
            session_ctx.__exit__ = MagicMock(return_value=False)
            mock_sess.return_value = session_ctx

            with patch("tempfile.mkdtemp", side_effect=custom_mkdtemp):
                with patch("sceneforge.rendering.ffprobe.is_ffmpeg_available", side_effect=RuntimeError("Unexpected OS error")):
                    with pytest.raises(RuntimeError, match="Unexpected OS error"):
                        orchestrator._stage_render()

        assert len(captured_dir) == 1
        assert not os.path.exists(captured_dir[0]), "Orchestrator work_dir leaked on unhandled error!"


# ---------------------------------------------------------------------------
# Tests: Cache consistency & atomic writes
# ---------------------------------------------------------------------------

class TestRenderCacheConsistency:
    def test_interrupted_cache_write_leaves_no_corrupt_files(self, tmp_path):
        """If a cache write is interrupted before completion, .get() returns None."""
        cache_dir = str(tmp_path / "cache")
        job_id = "job-cache-test"
        cache = RenderCache(cache_dir, job_id)
        profile = get_profile("16:9")

        key = build_cache_key(
            asset_id="asset-123",
            trim_start=0.0,
            trim_end=3.0,
            aspect_ratio="16:9",
            caption_text="Test caption",
            profile=profile,
        )

        # Before put: cache miss
        assert cache.get(key) is None

        # Simulate an interrupted write where destination file is empty (corrupt 0 bytes)
        digest = key.digest()
        corrupt_path = os.path.join(cache._root, f"{digest}.mp4")
        with open(corrupt_path, "wb") as f:
            pass  # 0 bytes

        # .get() must detect 0-byte corrupt files and treat as cache miss
        assert cache.get(key) is None

        # Now put a real valid segment (atomic replace)
        valid_source = str(tmp_path / "valid_segment.mp4")
        with open(valid_source, "wb") as f:
            f.write(b"valid h264 segment data of positive length")

        cached_path = cache.put(key, valid_source)
        assert os.path.exists(cached_path)
        assert os.path.getsize(cached_path) > 0

        # Now .get() must hit
        hit = cache.get(key)
        assert hit == cached_path

    def test_cache_keys_are_sensitive_to_render_parameters(self):
        """Altering any parameter that affects output changes the cache key."""
        profile = get_profile("16:9")
        k1 = build_cache_key("asset-1", 0.0, 2.0, "16:9", "Caption", profile)
        k2 = build_cache_key("asset-1", 0.0, 2.0, "9:16", "Caption", profile)  # different aspect ratio
        k3 = build_cache_key("asset-1", 0.0, 2.1, "16:9", "Caption", profile)  # different trim
        k4 = build_cache_key("asset-1", 0.0, 2.0, "16:9", "Different", profile)  # different caption

        assert k1.digest() != k2.digest()
        assert k1.digest() != k3.digest()
        assert k1.digest() != k4.digest()


# ---------------------------------------------------------------------------
# Tests: Incomplete output is never certified as PASS
# ---------------------------------------------------------------------------

class TestIncompleteOutputDetection:
    def test_qa_checker_fails_on_empty_or_truncated_file(self, tmp_path, sample_timeline):
        """QA checker fails immediately on missing, empty, or truncated video files."""
        empty_mp4 = str(tmp_path / "empty.mp4")
        with open(empty_mp4, "wb") as f:
            pass  # 0 bytes

        profile = get_profile("16:9")
        checker = QAChecker(
            empty_mp4,
            timeline=sample_timeline,
            expected_profile=profile,
            job_id="test-incomplete",
        )
        report = checker.run()
        assert report.overall == "FAIL"

        fail_names = [c.check_name for c in report.checks if c.status == "FAIL"]
        assert "file_nonempty" in fail_names

    def test_placeholder_mp4_cannot_pass_qa(self, tmp_path, sample_timeline):
        """The placeholder MP4 bytes generated on render error fail QA checks."""
        from sceneforge.jobs.orchestrator import PipelineOrchestrator

        placeholder_bytes = PipelineOrchestrator._placeholder_mp4_bytes()
        placeholder_file = str(tmp_path / "placeholder.mp4")
        with open(placeholder_file, "wb") as f:
            f.write(placeholder_bytes)

        profile = get_profile("16:9")
        checker = QAChecker(
            placeholder_file,
            timeline=sample_timeline,
            expected_profile=profile,
            job_id="test-placeholder",
        )
        report = checker.run()
        # The placeholder is not a valid video stream and fails QA
        assert report.overall in ("FAIL", "UNKNOWN")
        assert report.overall != "PASS"


# ---------------------------------------------------------------------------
# Tests: State transitions and retry on render failure
# ---------------------------------------------------------------------------

class TestRenderFailureStateTransitions:
    def test_render_failure_allows_transition_to_failed(self):
        """RENDERING -> FAILED is a valid transition."""
        validate_transition(JobStatus.RENDERING, JobStatus.FAILED)

    def test_failed_render_can_be_retried_to_queued(self):
        """FAILED -> QUEUED allows retry of an interrupted render."""
        validate_transition(JobStatus.FAILED, JobStatus.QUEUED)

    def test_rendering_cannot_skip_to_completed_directly(self):
        """Rendering cannot mark job completed without QA stage."""
        with pytest.raises(Exception):
            validate_transition(JobStatus.RENDERING, JobStatus.COMPLETED)
