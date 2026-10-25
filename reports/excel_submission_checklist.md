# IncuBrix Engineering Assessment 3 — Submission Workbook Checklist

Use the verified facts in this checklist to populate the official IncuBrix submission form.

---

## 1. Candidate & Project Information

- **Candidate / Developer**: Software Engineer Candidate
- **Assessment Name**: IncuBrix 2027 Software Engineer Assessment — PS3
- **Project Title**: SceneForge AI
- **Repository Location**: `C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3`
- **Application URL (Localhost Web App)**: `http://localhost:3000` (Nginx) & `http://localhost:8000` (FastAPI)
- **API Documentation**: `http://localhost:8000/docs` & `openapi.yaml` (OpenAPI 3.1.0)
- **Core Technology Stack**:
  - Backend: FastAPI, SQLAlchemy 2.0, PostgreSQL 15, Redis 7, RQ (Redis Queue), MinIO (S3)
  - Processing: FFmpeg 6.0, edge-tts, openai-whisper, sentence-transformers
  - Stock Video: Pixabay Video API (`https://pixabay.com/api/videos/`)
  - Frontend: Responsive Dark-Themed Web Studio (`apps/web/public/index.html`)

---

## 2. Mandatory Requirements (Must-Haves) Checklist

| # | Brief Requirement | Workbook Entry | Evidence Reference |
|---|---|---|---|
| **MH-01** | Text and audio input handling | **YES / PASS** | Supported audio formats validated via magic bytes (WAV, MP3, OGG, FLAC, M4A, WebM); 10-minute maximum limit strictly enforced with `AUDIO_DURATION_EXCEEDED` (HTTP 422). |
| **MH-02** | Meaning-aware scene planning | **YES / PASS** | Sentence boundary segmenter with semantic disambiguation ("bank" financial vs river; "cloud" computing vs weather); entity extraction and safety rules for named individuals and brands. |
| **MH-03** | Commercial rights verification | **YES / PASS** | Every selected clip verified against commercial clearance whitelist; real SHA-256 hash computed on downloaded file; `rights.json` output produced for every job. |
| **MH-04** | Aspect ratio rendering | **YES / PASS** | 16:9 Landscape (1920×1080), 9:16 Portrait (1080×1920), and 1:1 Square (1080×1080) reframed via geometric center-crop or blurred-padding; black/frozen frames and audio drift checked. |
| **MH-05** | No repeated clips & relevance | **YES / PASS** | Duplicate penalty applied in candidate ranker; QA check `duplicate_scenes` reports FAIL on repeat; semantic score computed from text embeddings and tag overlap. |
| **MH-06** | Safe handling of sensitive topics | **YES / PASS** | Named people and commercial brands excluded from media search queries; sensitive/sad content handled with neutral visual concepts without fabricated imagery. |
| **MH-07** | Background job resilience | **YES / PASS** | Asynchronous RQ queue; state machine with timestamps; worker reconciler resumes or safely retries stale jobs; interrupted renders clean temporary directories without corrupting artifacts. |
| **MH-08** | Working demo & integration | **YES / PASS** | Full Docker Compose stack starts with a single command; zero-dependency web app streams generated video in browser; all 10 Integration Standards satisfied. |

---

## 3. Integration Standards Checklist

| Standard | Standard Requirement | Workbook Entry |
|---|---|---|
| **IS-01** | Docker Compose & no-key test suite | **PASS** — `docker compose up` starts API, Worker, DB, Redis, MinIO, Web. `pytest` executes 500 tests with 0 failures offline. |
| **IS-02** | OpenAPI 3.1 & `/api/v1/` documentation | **PASS** — `openapi.yaml` adheres to OpenAPI 3.1.0; all routes documented under `/api/v1/` and `/`. |
| **IS-03** | HTTP 202, progress, links & signed callbacks | **PASS** — `POST /api/v1/jobs` returns HTTP 202 with `job_id`, `progress: 0.0`, and `result_links`. Callbacks signed with `X-IncuBrix-Signature` (HMAC-SHA256). |
| **IS-04** | Idempotency-Key support | **PASS** — `Idempotency-Key` header cached in Redis + DB. Duplicate requests return existing job (HTTP 200); payload conflicts return HTTP 409. |
| **IS-05** | UPPER_SNAKE_CASE error schema | **PASS** — Errors follow `{"error": {"code": "...", "message": "...", "retryable": bool, "correlation_id": "..."}}`. No stack traces exposed. |
| **IS-06** | Configuration via environment | **PASS** — 89 `os.getenv` calls configure all limits, timeouts, and providers. Secrets isolated in `.env` (excluded from git). |
| **IS-07** | File uploads & S3/MinIO storage | **PASS** — Audio uploaded via multipart/form-data; all 7 artifacts stored in MinIO object storage with presigned download links. |
| **IS-08** | Structured JSON logs & `/health` | **PASS** — Structlog JSON logs with timestamps, levels, job IDs, and correlation IDs. `/health` and `/ready` return HTTP 200. |
| **IS-09** | Complete manifest | **PASS** — `manifest.json` contains providers, model versions, settings, timings, cost estimates, warnings, and rights summaries. |
| **IS-10** | Batch runner CLI | **PASS** — `scripts/batch_runner.py` processes input files or folders and outputs `batch_report.json` with per-case artifacts. |

---

## 4. Assessment Level Claim

- **Claimed Level**: **Advanced Level (Verified)** + Selective **Outstanding Level** capabilities.
- **Evidence Reference**:
  - `reports/assessment_compliance.md`
  - `reports/video_pack_manifest.md`
  - `reports/test_pack_index.md`
  - `REPORT.md`
