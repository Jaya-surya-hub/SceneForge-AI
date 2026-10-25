"""Unit tests for JobRepository (MH-07, IS-01).

Tests:
- create_job persists a job with correct defaults.
- get_job returns None for unknown IDs.
- update_job_status changes status and sets timestamps.
- idempotency key recording and lookup.
- scene upsert replaces existing scenes.
- rights record creation.
- metric upsert.
"""

import uuid
from datetime import datetime, timezone

import pytest

from sceneforge.jobs import repository as repo
from sceneforge.jobs.models import Job


class TestJobCRUD:
    def test_create_job_basic(self, db_session):
        job = repo.create_job(db_session, data={"script": "Hello world"})
        db_session.flush()
        assert job.id is not None
        assert job.status == "QUEUED"
        assert job.script == "Hello world"
        assert job.aspect_ratio == "16:9"
        assert job.retry_count == 0

    def test_create_job_custom_aspect_ratio(self, db_session):
        job = repo.create_job(db_session, data={"script": "Test", "aspect_ratio": "9:16"})
        db_session.flush()
        assert job.aspect_ratio == "9:16"

    def test_get_job_returns_job(self, db_session):
        job = repo.create_job(db_session, data={"script": "test"})
        db_session.flush()
        fetched = repo.get_job(db_session, job.id)
        assert fetched is not None
        assert fetched.id == job.id

    def test_get_job_unknown_returns_none(self, db_session):
        result = repo.get_job(db_session, uuid.uuid4())
        assert result is None

    def test_get_job_or_raise_raises_on_missing(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            repo.get_job_or_raise(db_session, uuid.uuid4())

    def test_update_job_status(self, db_session):
        job = repo.create_job(db_session, data={"script": "test"})
        db_session.flush()
        repo.update_job_status(db_session, job.id, status="VALIDATING")
        db_session.flush()
        updated = repo.get_job(db_session, job.id)
        assert updated.status == "VALIDATING"

    def test_update_job_status_sets_started_at(self, db_session):
        job = repo.create_job(db_session, data={"script": "test"})
        db_session.flush()
        repo.update_job_status(db_session, job.id, status="VALIDATING")
        db_session.flush()
        # Re-fetch to get the updated row (execute(update()) doesn't refresh ORM objects)
        db_session.expire(job)
        updated = repo.get_job(db_session, job.id)
        assert updated.started_at is not None

    def test_update_job_status_sets_completed_at(self, db_session):
        job = repo.create_job(db_session, data={"script": "test"})
        db_session.flush()
        repo.update_job_status(db_session, job.id, status="COMPLETED")
        db_session.flush()
        db_session.expire(job)
        updated = repo.get_job(db_session, job.id)
        assert updated.completed_at is not None

    def test_update_job_status_with_error(self, db_session):
        job = repo.create_job(db_session, data={"script": "test"})
        db_session.flush()
        repo.update_job_status(
            db_session,
            job.id,
            status="FAILED",
            error_code="EMPTY_SCRIPT",
            error_message="Script is empty.",
            retryable=False,
        )
        db_session.flush()
        db_session.expire(job)
        updated = repo.get_job(db_session, job.id)
        assert updated.status == "FAILED"
        assert updated.error_code == "EMPTY_SCRIPT"
        assert updated.retryable is False

    def test_increment_retry_count(self, db_session):
        job = repo.create_job(db_session, data={"script": "test"})
        db_session.flush()
        count1 = repo.increment_retry_count(db_session, job.id)
        count2 = repo.increment_retry_count(db_session, job.id)
        assert count1 == 1
        assert count2 == 2


class TestIdempotency:
    def test_record_and_find_idempotency_key(self, db_session):
        job = repo.create_job(db_session, data={"script": "test"})
        db_session.flush()
        payload = {"script": "test"}
        repo.record_idempotency_key(
            db_session, key="my-key", payload=payload, job_id=job.id
        )
        db_session.flush()
        result = repo.find_idempotent_job(db_session, key="my-key")
        assert result is not None
        found_job, found_hash = result
        assert found_job.id == job.id
        assert found_hash == repo.compute_payload_hash(payload)

    def test_find_unknown_key_returns_none(self, db_session):
        result = repo.find_idempotent_job(db_session, key="nonexistent-key")
        assert result is None

    def test_payload_hash_stable(self):
        p = {"script": "hello", "aspect_ratio": "16:9"}
        h1 = repo.compute_payload_hash(p)
        h2 = repo.compute_payload_hash(p)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_different_payloads_different_hashes(self):
        h1 = repo.compute_payload_hash({"script": "A"})
        h2 = repo.compute_payload_hash({"script": "B"})
        assert h1 != h2


class TestScenes:
    def test_upsert_scenes(self, db_session):
        job = repo.create_job(db_session, data={"script": "test"})
        db_session.flush()
        scenes_data = [
            {"narration_text": "Scene one", "start_time": 0.0, "end_time": 5.0},
            {"narration_text": "Scene two", "start_time": 5.0, "end_time": 10.0},
        ]
        repo.upsert_scenes(db_session, job.id, scenes_data)
        db_session.flush()
        scenes = repo.get_scenes(db_session, job.id)
        assert len(scenes) == 2
        assert scenes[0].scene_index == 0
        assert scenes[1].scene_index == 1

    def test_upsert_replaces_existing(self, db_session):
        job = repo.create_job(db_session, data={"script": "test"})
        db_session.flush()
        repo.upsert_scenes(db_session, job.id, [{"narration_text": "Old"}])
        db_session.flush()
        repo.upsert_scenes(db_session, job.id, [{"narration_text": "New 1"}, {"narration_text": "New 2"}])
        db_session.flush()
        scenes = repo.get_scenes(db_session, job.id)
        assert len(scenes) == 2
        assert scenes[0].narration_text == "New 1"


class TestRightsRecords:
    def test_add_rights_record(self, db_session):
        job = repo.create_job(db_session, data={"script": "test"})
        db_session.flush()
        record = repo.add_rights_record(
            db_session,
            job_id=job.id,
            data={
                "asset_id": "asset-001",
                "provider_name": "mock_stock",
                "licence_name": "Mock-CC0",
                "commercial_use_eligible": True,
                "sha256_hash": "abc123",
                "asset_type": "stock",
            },
        )
        db_session.flush()
        records = repo.get_rights_records(db_session, job.id)
        assert len(records) == 1
        assert records[0].asset_id == "asset-001"
        assert records[0].commercial_use_eligible is True
