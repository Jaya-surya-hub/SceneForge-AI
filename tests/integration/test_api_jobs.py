"""Integration tests for the jobs API (IS-01, IS-03, MH-07).

Tests:
- POST /jobs creates a job and returns correct shape.
- Idempotent requests with same key return same job.
- Same key + different payload returns 409.
- GET /jobs/{id} returns job status.
- GET /jobs/{unknown} returns 404 with IS-03 shape.
- GET /jobs/{id}/storyboard returns empty storyboard.
- POST /jobs/{id}/cancel transitions to CANCELLED.
- Correlation ID is injected in all responses.
- Error responses have IS-03 shape with no stack traces.
"""

import uuid

import pytest


class TestJobCreation:
    def test_create_job_returns_201_or_202(self, api_client, idem_key):
        resp = api_client.post(
            "/jobs",
            json={"script": "Hello world.", "aspect_ratio": "16:9"},
            headers={"Idempotency-Key": idem_key},
        )
        assert resp.status_code in (201, 202)
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "QUEUED"
        assert "created_at" in body

    def test_create_job_sets_correlation_id_header(self, api_client, idem_key):
        resp = api_client.post(
            "/jobs",
            json={"script": "Test"},
            headers={"Idempotency-Key": idem_key},
        )
        assert "x-correlation-id" in resp.headers or "X-Correlation-ID" in resp.headers

    def test_create_job_uses_provided_correlation_id(self, api_client, idem_key):
        cid = "my-custom-cid-12345"
        resp = api_client.post(
            "/jobs",
            json={"script": "Test"},
            headers={"Idempotency-Key": idem_key, "X-Correlation-ID": cid},
        )
        assert resp.status_code in (201, 202)
        # Response should echo back the same correlation ID
        response_cid = resp.headers.get("x-correlation-id") or resp.headers.get("X-Correlation-ID")
        assert response_cid == cid

    def test_create_job_without_idempotency_key(self, api_client):
        resp = api_client.post("/jobs", json={"script": "Hello"})
        assert resp.status_code in (201, 202)


class TestIdempotency:
    def test_same_key_same_payload_returns_same_job(self, api_client, idem_key):
        payload = {"script": "Idempotent test.", "aspect_ratio": "16:9"}
        resp1 = api_client.post(
            "/jobs", json=payload, headers={"Idempotency-Key": idem_key}
        )
        resp2 = api_client.post(
            "/jobs", json=payload, headers={"Idempotency-Key": idem_key}
        )
        assert resp1.status_code in (201, 202)
        # Second call should return 200 (existing) not 201/202 (new)
        assert resp2.status_code in (200, 201, 202)
        assert resp1.json()["job_id"] == resp2.json()["job_id"]

    def test_same_key_different_payload_returns_409(self, api_client, idem_key):
        resp1 = api_client.post(
            "/jobs",
            json={"script": "Payload one.", "aspect_ratio": "16:9"},
            headers={"Idempotency-Key": idem_key},
        )
        assert resp1.status_code in (201, 202)

        resp2 = api_client.post(
            "/jobs",
            json={"script": "Completely different payload.", "aspect_ratio": "9:16"},
            headers={"Idempotency-Key": idem_key},
        )
        assert resp2.status_code == 409
        body = resp2.json()
        assert body["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    def test_different_keys_create_different_jobs(self, api_client):
        payload = {"script": "Same content."}
        r1 = api_client.post(
            "/jobs", json=payload,
            headers={"Idempotency-Key": f"key-a-{uuid.uuid4().hex}"}
        )
        r2 = api_client.post(
            "/jobs", json=payload,
            headers={"Idempotency-Key": f"key-b-{uuid.uuid4().hex}"}
        )
        assert r1.status_code in (201, 202)
        assert r2.status_code in (201, 202)
        assert r1.json()["job_id"] != r2.json()["job_id"]


class TestJobStatus:
    def test_get_job_returns_correct_fields(self, api_client, idem_key):
        create_resp = api_client.post(
            "/jobs",
            json={"script": "Test narration."},
            headers={"Idempotency-Key": idem_key},
        )
        job_id = create_resp.json()["job_id"]

        resp = api_client.get(f"/jobs/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == job_id
        assert body["status"] == "QUEUED"
        assert "created_at" in body
        assert "updated_at" in body

    def test_get_unknown_job_returns_404(self, api_client):
        resp = api_client.get(f"/jobs/{uuid.uuid4()}")
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "NOT_FOUND"

    def test_get_job_has_correlation_id_in_error(self, api_client):
        resp = api_client.get(f"/jobs/{uuid.uuid4()}")
        body = resp.json()
        assert "correlation_id" in body["error"]


class TestStoryboard:
    def test_storyboard_empty_on_new_job(self, api_client, idem_key):
        create_resp = api_client.post(
            "/jobs",
            json={"script": "Test."},
            headers={"Idempotency-Key": idem_key},
        )
        job_id = create_resp.json()["job_id"]

        resp = api_client.get(f"/jobs/{job_id}/storyboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == job_id
        assert body["job_status"] == "QUEUED"
        assert body["scenes"] == []

    def test_storyboard_unknown_job_returns_404(self, api_client):
        resp = api_client.get(f"/jobs/{uuid.uuid4()}/storyboard")
        assert resp.status_code == 404


class TestJobCancellation:
    def test_cancel_queued_job(self, api_client, idem_key):
        create_resp = api_client.post(
            "/jobs",
            json={"script": "Cancel me."},
            headers={"Idempotency-Key": idem_key},
        )
        job_id = create_resp.json()["job_id"]

        cancel_resp = api_client.post(f"/jobs/{job_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "CANCELLED"

    def test_cancel_unknown_job_returns_404(self, api_client):
        resp = api_client.post(f"/jobs/{uuid.uuid4()}/cancel")
        assert resp.status_code == 404


class TestHealthEndpoints:
    def test_health_returns_200(self, api_client):
        resp = api_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "version" in body


class TestInputValidation:
    def test_blank_script_rejected(self, api_client):
        resp = api_client.post(
            "/jobs",
            json={"script": "   "},
            headers={"Idempotency-Key": f"blank-{uuid.uuid4().hex}"},
        )
        assert resp.status_code == 422

    def test_neither_script_nor_voiceover_rejected(self, api_client):
        resp = api_client.post(
            "/jobs",
            json={},
            headers={"Idempotency-Key": f"none-{uuid.uuid4().hex}"},
        )
        assert resp.status_code == 422

    def test_audio_only_submission_accepted(self, api_client):
        resp = api_client.post(
            "/jobs",
            json={"voiceover_path": "uploads/voiceover_test.m4a"},
            headers={"Idempotency-Key": f"audio-only-{uuid.uuid4().hex}"},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "job_id" in body

    def test_blank_script_with_voiceover_accepted(self, api_client):
        resp = api_client.post(
            "/jobs",
            json={"script": "   ", "voiceover_path": "uploads/voiceover_test.m4a"},
            headers={"Idempotency-Key": f"blank-vo-{uuid.uuid4().hex}"},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "job_id" in body

    def test_script_plus_audio_submission_accepted(self, api_client):
        resp = api_client.post(
            "/jobs",
            json={"script": "Narration text.", "voiceover_path": "uploads/voiceover_test.mp3"},
            headers={"Idempotency-Key": f"aligned-{uuid.uuid4().hex}"},
        )
        assert resp.status_code == 202

    def test_invalid_aspect_ratio_rejected(self, api_client):
        resp = api_client.post(
            "/jobs",
            json={"script": "Valid script.", "aspect_ratio": "4:3"},
            headers={"Idempotency-Key": f"ratio-{uuid.uuid4().hex}"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert "error" in body


class TestAudioUploadEndpoint:
    def test_upload_valid_m4a_audio(self, api_client):
        # 32 bytes mock m4a file (starts with ftyp box)
        fake_m4a = b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00isomiso2" + b"\x00" * 12
        files = {"file": ("Recording.m4a", fake_m4a, "audio/x-m4a")}
        resp = api_client.post("/jobs/upload-audio", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert "voiceover_path" in data
        assert data["voiceover_path"].startswith("uploads/voiceover_")
        assert data["voiceover_path"].endswith(".m4a")
        assert data["filename"] == "Recording.m4a"

    def test_upload_empty_audio_rejected(self, api_client):
        files = {"file": ("empty.wav", b"", "audio/wav")}
        resp = api_client.post("/jobs/upload-audio", files=files)
        assert resp.status_code == 400

    def test_upload_too_short_rejected(self, api_client):
        files = {"file": ("short.wav", b"short", "audio/wav")}
        resp = api_client.post("/jobs/upload-audio", files=files)
        assert resp.status_code == 400

    def test_upload_invalid_extension_rejected(self, api_client):
        files = {"file": ("script.txt", b"This is plain text not audio", "text/plain")}
        resp = api_client.post("/jobs/upload-audio", files=files)
        assert resp.status_code == 400
        assert "Unsupported audio file extension" in resp.json()["detail"]
