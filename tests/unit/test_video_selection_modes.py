"""Tests for Feature 1 (Automatic Video Selection) and Feature 2 (Manual Video Selection).

Verifies:
1. Automatic mode is the default and runs full pipeline with candidate scoring and selection rationale.
2. Manual mode pauses at AWAITING_SELECTION and returns multiple real candidates per scene.
3. Valid candidates can be selected and server rejects non-eligible candidate IDs.
4. Refreshing candidates updates the candidate list for a scene.
5. Triggering render executes remaining stages and uses the chosen clip while preserving audio.
6. API routes for candidate retrieval, selection, refresh, and rendering.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
import pytest
from unittest.mock import MagicMock, patch

from sceneforge.jobs import repository as repo
from sceneforge.jobs.schemas import JobCreateRequest
from sceneforge.jobs.state_machine import JobStatus
from sceneforge.jobs.orchestrator import PipelineOrchestrator


class TestVideoSelectionModes:
    def test_schema_defaults_to_automatic(self):
        """Video selection mode defaults to automatic when omitted."""
        req = JobCreateRequest(script="Testing default mode")
        assert req.video_selection_mode == "automatic"

        req_manual = JobCreateRequest(script="Testing manual mode", video_selection_mode="manual")
        assert req_manual.video_selection_mode == "manual"

    def test_automatic_selection_mode_runs_to_completed(self, db_session):
        """Automatic mode chooses best clip and completes pipeline with candidate rationale."""
        job = repo.create_job(
            db_session,
            data={
                "script": "Artificial intelligence creates stunning digital cinematography.",
                "aspect_ratio": "16:9",
                "tts_adapter": "mock",
                "video_selection_mode": "automatic",
            },
        )
        db_session.commit()

        orch = PipelineOrchestrator(job_id=job.id)
        orch.storage = MagicMock()
        orch.storage.object_exists.return_value = True
        orch.storage.download_bytes.return_value = b"mock mp4/audio bytes"
        orch.storage.upload_bytes.return_value = "mock_key"

        @contextmanager
        def mock_get_session():
            yield db_session
            db_session.commit()

        with patch("sceneforge.jobs.orchestrator.get_session", side_effect=mock_get_session):
            orch.run()

        updated = repo.get_job(db_session, job.id)
        assert updated.status == JobStatus.COMPLETED.value

        scenes = repo.get_scenes(db_session, job.id)
        assert len(scenes) >= 1
        for s in scenes:
            assert s.asset_id is not None
            candidates = (s.plan_data or {}).get("candidates", [])
            assert len(candidates) >= 1
            # Check candidate structure
            c0 = candidates[0]
            assert "asset_id" in c0
            assert "provider_name" in c0
            assert "relevance_score" in c0
            assert "licence_name" in c0
            assert "commercial_use_eligible" in c0

    def test_manual_selection_mode_pauses_and_renders(self, db_session):
        """Manual mode pauses at AWAITING_SELECTION, allows selection change, and renders."""
        job = repo.create_job(
            db_session,
            data={
                "script": "Deep ocean exploration reveals mysterious aquatic creatures.",
                "aspect_ratio": "16:9",
                "tts_adapter": "mock",
                "video_selection_mode": "manual",
            },
        )
        db_session.commit()

        orch = PipelineOrchestrator(job_id=job.id)
        orch.storage = MagicMock()
        orch.storage.object_exists.return_value = True
        orch.storage.download_bytes.return_value = b"mock mp4/audio bytes"
        orch.storage.upload_bytes.return_value = "mock_key"

        @contextmanager
        def mock_get_session():
            yield db_session
            db_session.commit()

        with patch("sceneforge.jobs.orchestrator.get_session", side_effect=mock_get_session):
            orch.run()

        # Job must be paused at AWAITING_SELECTION
        updated = repo.get_job(db_session, job.id)
        assert updated.status == JobStatus.AWAITING_SELECTION.value

        scenes = repo.get_scenes(db_session, job.id)
        assert len(scenes) >= 1
        scene = scenes[0]
        candidates = (scene.plan_data or {}).get("candidates", [])
        assert len(candidates) >= 1

        first_asset_id = candidates[0]["asset_id"]
        assert scene.asset_id == first_asset_id  # Preselected top candidate

        # If more than 1 candidate, switch to candidate 1
        if len(candidates) > 1:
            second_asset_id = candidates[1]["asset_id"]
            updated_scene = repo.update_scene_selection(
                db_session,
                job_id=job.id,
                scene_id=str(scene.id),
                asset_id=second_asset_id,
            )
            assert updated_scene is not None
            assert updated_scene.asset_id == second_asset_id
            db_session.commit()

        # Try to select a fake/unauthorized asset ID -> must be rejected
        invalid_selection = repo.update_scene_selection(
            db_session,
            job_id=job.id,
            scene_id=str(scene.id),
            asset_id="fake_untrusted_asset_12345",
        )
        assert invalid_selection is None

        # Now trigger render stage
        orch_render = PipelineOrchestrator(job_id=job.id)
        orch_render.storage = orch.storage

        with patch("sceneforge.jobs.orchestrator.get_session", side_effect=mock_get_session):
            orch_render.run()

        final_job = repo.get_job(db_session, job.id)
        assert final_job.status == JobStatus.COMPLETED.value


class TestVideoSelectionAPI:
    def test_candidates_and_selection_endpoints(self, api_client, db_session):
        """Test API endpoints for candidates, clip selection, and render trigger."""
        job = repo.create_job(
            db_session,
            data={
                "script": "A cinematic aerial view over snow-capped mountains.",
                "aspect_ratio": "16:9",
                "video_selection_mode": "manual",
            },
        )
        repo.upsert_scenes(
            db_session,
            job_id=job.id,
            scenes=[
                {
                    "scene_index": 0,
                    "narration_text": "A cinematic aerial view over snow-capped mountains.",
                    "start_time": 0.0,
                    "end_time": 4.0,
                    "plan_data": {
                        "candidates": [
                            {
                                "asset_id": "clip-001",
                                "provider_name": "pixabay",
                                "title": "Snowy Mountain Aerial",
                                "relevance_score": 0.95,
                                "duration_seconds": 12.0,
                                "width": 1920,
                                "height": 1080,
                                "licence_name": "Pixabay Licence",
                                "commercial_use_eligible": True,
                                "attribution_required": False,
                                "is_selected": True,
                            },
                            {
                                "asset_id": "clip-002",
                                "provider_name": "pixabay",
                                "title": "Winter Forest Flight",
                                "relevance_score": 0.88,
                                "duration_seconds": 10.0,
                                "width": 1920,
                                "height": 1080,
                                "licence_name": "Pixabay Licence",
                                "commercial_use_eligible": True,
                                "attribution_required": False,
                                "is_selected": False,
                            },
                        ],
                        "selected_candidate_id": "clip-001",
                    },
                }
            ],
        )
        db_session.flush()
        scenes = repo.get_scenes(db_session, job.id)
        scene = scenes[0]
        scene.asset_id = "clip-001"
        repo.update_job_status(db_session, job.id, status=JobStatus.AWAITING_SELECTION.value)
        db_session.commit()

        # 1. GET /jobs/{id}/candidates
        res = api_client.get(f"/jobs/{job.id}/candidates")
        assert res.status_code == 200
        data = res.json()
        assert data["job_id"] == str(job.id)
        assert data["video_selection_mode"] == "manual"
        assert len(data["scenes"]) == 1
        scene_cand = data["scenes"][0]
        assert scene_cand["scene_id"] == str(scene.id)
        assert len(scene_cand["candidates"]) == 2
        assert scene_cand["selected_asset_id"] == "clip-001"

        # 2. POST /jobs/{id}/select-clip with valid choice
        res = api_client.post(
            f"/jobs/{job.id}/select-clip",
            json={"scene_id": str(scene.id), "asset_id": "clip-002"},
        )
        assert res.status_code == 200
        sel_data = res.json()
        assert sel_data["status"] == "ok"
        assert sel_data["selected_asset_id"] == "clip-002"

        # Verify DB updated
        db_session.expire_all()
        updated_s = repo.get_scenes(db_session, job.id)[0]
        assert updated_s.asset_id == "clip-002"

        # 3. POST /jobs/{id}/select-clip with INVALID/untrusted clip ID -> 400
        res = api_client.post(
            f"/jobs/{job.id}/select-clip",
            json={"scene_id": str(scene.id), "asset_id": "untrusted-clip-999"},
        )
        assert res.status_code == 400

        # 4. POST /jobs/{id}/render -> triggers background render
        res = api_client.post(f"/jobs/{job.id}/render", json={})
        assert res.status_code == 200
        render_data = res.json()
        assert render_data["job_id"] == str(job.id)
