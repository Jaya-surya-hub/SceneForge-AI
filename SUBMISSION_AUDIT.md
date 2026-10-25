# SceneForge AI — IncuBrix Integration Standard Compliance Audit

**Project**: SceneForge AI — Script & Voiceover to B-roll Video Engine  
**Assessment**: IncuBrix Engineering Assessment 3  
**Project Root**: `C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3`  
**Audit Date**: October 21, 2026  
**Auditor**: Antigravity Pair-Programming Agent & Candidate  

---

## IncuBrix Integration Standard Checklist (10 Requirements)

| # | Standard Requirement | IncuBrix Brief Specification | Project Status | Evidence / Details | Remaining Action |
|---|---|---|---|---|---|
| **1** | **One-command start and test** | `docker compose up` starts the service and everything it needs (database, storage, local test servers). One command runs all tests (unit, integration and at least one end-to-end) with no API keys. A `.env.example` lists every setting. | **PASS** | • Docker Compose defines 6 services: `api`, `worker`, `db` (PostgreSQL 15), `redis` (Redis 7), `minio` (S3 object storage), `web` (Nginx). Verified all 6 running healthy via `docker compose ps`.<br>• Full test suite runs offline with mock adapters: `$env:PYTHONPATH="src"; python -m pytest` (**517 passed in 4.36s**).<br>• `.env.example` lists every setting with documented placeholders. | None. Fully operational. |
| **2** | **Documented HTTP API** | An `openapi.yaml` (OpenAPI 3.1) that matches the running service exactly. All routes under `/api/v1/`. | **PASS** | • `openapi.yaml` declares `openapi: 3.1.0`.<br>• All routes mounted under `/api/v1/`: `/api/v1/health`, `/api/v1/ready`, `/api/v1/jobs`, `/api/v1/jobs/upload-audio`, `/api/v1/jobs/{job_id}`, `/api/v1/jobs/{job_id}/storyboard`, `/api/v1/jobs/{job_id}/artifacts`, `/api/v1/jobs/{job_id}/artifacts/{filename}`, `/api/v1/jobs/{job_id}/cancel`.<br>• Validated by `tests/unit/test_openapi.py` (4 passed). | None. Spec and routes match. |
| **3** | **Background jobs** | Anything slower than 2 seconds runs as a job: `POST` returns 202 with a `job_id`; `GET /api/v1/jobs/{job_id}` returns status (queued, running, succeeded, failed), progress 0-100 and result links. Optional callback URL, signed with HMAC-SHA256 in an `X-IncuBrix-Signature` header. | **PASS** | • `POST /api/v1/jobs` returns HTTP 202 Accepted with `job_id`, `status: "QUEUED"`, `progress: 0.0`, and `result_links` object mapping `status`, `artifacts`, and `storyboard`.<br>• Verified live via `curl -X POST http://localhost:8000/api/v1/jobs` returning job `ab834a60-6121-4192-9272-625ca8753315`.<br>• HMAC-SHA256 callback signing implemented in `src/sceneforge/callbacks/notifier.py` with `X-IncuBrix-Signature` and verified in `tests/unit/test_callbacks.py` (12 passed). | None. |
| **4** | **Safe retries** | An `Idempotency-Key` header on every `POST`: sending the same request twice with the same key returns the same job and never does the work twice. | **PASS** | • Verified live: `POST /api/v1/jobs` with `Idempotency-Key: test-bg-job-01` returned existing job `ab834a60-6121-4192-9272-625ca8753315` without duplicate execution.<br>• Conflicting payload with the same key returned HTTP 409 Conflict with `code: "IDEMPOTENCY_CONFLICT"`.<br>• Verified by `tests/integration/test_api_jobs.py::TestIdempotency` (3 passed). | None. |
| **5** | **Clear errors** | Errors are JSON: `{"error": {"code", "message", "retryable", "details"}}`. Codes are `UPPER_SNAKE_CASE` and listed in the README. | **PASS** | • Schema strictly enforced via `src/sceneforge/schemas/errors.py`.<br>• Verified live on 409 response: `{"error": {"code": "IDEMPOTENCY_CONFLICT", "message": "...", "retryable": false, "correlation_id": "...", "details": {}}}`.<br>• Verified on 422: `EMPTY_SCRIPT`.<br>• Documented in README: `EMPTY_SCRIPT`, `AUDIO_DURATION_EXCEEDED`, `UNSUPPORTED_AUDIO_FORMAT`, `CORRUPTED_AUDIO`, `SPEECH_NOT_DETECTED`, `IDEMPOTENCY_CONFLICT`, `NOT_FOUND`, `LICENCE_VERIFICATION_FAILED`, `PROVIDER_ERROR`, `MEDIA_PROVIDER_UNAVAILABLE`.<br>• Verified by `tests/unit/test_error_schema.py` (14 passed). | None. |
| **6** | **Configuration** | All settings, paths, model names and limits come from environment variables or a config file. No hard-coded paths or keys. | **PASS** | • All environment settings centralized via `os.getenv` with defaults.<br>• Key variables: `STOCK_PROVIDER`, `PIXABAY_API_KEY`, `TTS_ADAPTER`, `STT_ADAPTER`, `STORAGE_BACKEND`, `MINIO_ENDPOINT`, `MAX_AUDIO_DURATION_SECONDS`, `MAX_UPLOAD_BYTES`, `IDEMPOTENCY_KEY_TTL`.<br>• Sensitive variables in `.env` (excluded from git via `.gitignore`). Template in `.env.example`. | None. |
| **7** | **Files in, files out** | Inputs accepted as an upload or a URL. Outputs saved to S3-compatible storage (MinIO in the compose file is fine) and returned as download links. | **PASS** | • Audio upload endpoint: `POST /api/v1/jobs/upload-audio` (multipart form-data). Tested with `voiceover_lake.mp3` (`55,296 bytes`).<br>• Audio URL inputs supported via `audio_url` parameter.<br>• S3-compatible storage: MinIO running on port 9090 with buckets `sceneforge-uploads`, `sceneforge-artifacts`, `sceneforge-cache`.<br>• Artifact listing: `GET /api/v1/jobs/{id}/artifacts` lists all 7 artifacts (`output.mp4`, `timeline.json`, `rights.json`, `metrics.json`, `captions.srt`, `manifest.json`, `job.log`).<br>• Artifact download: `GET /api/v1/jobs/{id}/artifacts/{filename}` returns 302 redirect to presigned/direct file URL. | None. |
| **8** | **Logs and health** | Structured JSON logs with timestamp, level, `job_id` and the `X-Correlation-Id` from the request. `GET /health` and `GET /ready` endpoints. | **PASS** | • Structlog configured with `JSONRenderer` emitting ISO timestamps, severity level, `job_id`, and `correlation_id`.<br>• `GET /api/v1/health` verified returning HTTP 200 `{"status": "ok", "version": "0.1.0", "environment": "development"}`.<br>• `GET /api/v1/ready` verified returning HTTP 200 `{"status": "ok", "checks": {"database": "ok", "redis": "ok"}}`.<br>• All responses include `x-correlation-id` header. | None. |
| **9** | **Output manifest** | Every result includes a JSON manifest: which models/providers and versions were used, settings, seed, timings, cost estimate, warnings, and licence/rights information. | **PASS** | • `manifest.json` generated for every job.<br>• Verified live on job `ab834a60-6121-4192-9272-625ca8753315` and job `a89874ff-b596-43d5-b95e-6cec68a7d441`: includes `providers` (tts, stock, models), `settings` (aspect_ratio, burn_captions, target_fps, resolution), `timings_ms` (validate, plan, retrieve, render, qa), `cost_estimate`, `warnings`, `rights_summary`, `real_mp4_rendered: true`, `tts_adapter`, `tts_is_mock`, `narration_audio_present`, `qa_overall`. | None. |
| **10** | **Batch runner** | A command-line tool that runs a folder or file of test inputs against the API and writes all results to one folder. We use this to test every submission the same way. | **PASS** | • CLI script: `scripts/batch_runner.py`.<br>• Tested against live API: `python scripts/batch_runner.py --cases tests/fixtures/batch_cases.json --base-url http://localhost:8000 --output batch_report.json`.<br>• Output: **5/5 test cases passed (100%)**:<br>  1. `basic-text-only`: PASS (COMPLETED, 10.09s)<br>  2. `abstract-concept`: PASS (COMPLETED, 10.07s)<br>  3. `numeric-claim`: PASS (COMPLETED, 5.03s)<br>  4. `portrait-mode`: PASS (COMPLETED, 10.09s)<br>  5. `empty-script`: PASS (FAILED with 422 as expected).<br>• Machine-readable `batch_report.json` generated and verified. | None. |

---

## Summary of Verification Commands & Test Results

```powershell
# 1. Full Offline Test Suite (Unit, Hard Cases, Integration)
$env:PYTHONPATH="src"; & "C:\Python314\python.exe" -m pytest -q
# Result: 517 passed, 1 warning in 4.36s (100% pass rate)

# 2. Live API Readiness & Health
curl.exe -i -s http://localhost:8000/api/v1/ready
# Result: HTTP 200 OK {"status":"ok","checks":{"database":"ok","redis":"ok"}}

# 3. Batch Runner Execution
& "C:\Python314\python.exe" scripts/batch_runner.py --cases tests/fixtures/batch_cases.json --base-url http://localhost:8000 --output batch_report.json
# Result: 5/5 cases passed (100%)

# 4. End-to-End Live Video Generation (Genuine Footage)
# Job a89874ff-b596-43d5-b95e-6cec68a7d441 (Script to Video with gTTS & Pixabay B-roll)
# Result: H.264/AAC MP4, 1920x1080@30fps, 8.76s, 9.3 MB, QA overall: PASS (16/16 checks)
```
