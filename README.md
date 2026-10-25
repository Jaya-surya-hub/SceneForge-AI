# SceneForge AI

**Script and Voiceover to B-roll Video Engine**
IncuBrix Software Engineer Assessment — PS3

> A meaning-aware, narration-driven video generation engine that transforms a script,
> voiceover, or both into a narrated, captioned, rights-verified MP4 with full audit trail.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Environment Setup](#environment-setup)
5. [Startup](#startup)
6. [Database Migrations](#database-migrations)
7. [Running Tests](#running-tests)
8. [Generating a Video](#generating-a-video)
9. [Batch Runner](#batch-runner)
10. [API Documentation](#api-documentation)
11. [Troubleshooting](#troubleshooting)
12. [Known Limitations](#known-limitations)

---

## Project Overview

SceneForge AI accepts a script, a voiceover audio file, or both, and produces:

- `output.mp4` — H.264/AAC narrated B-roll video (landscape 16:9 or portrait 9:16)
- `timeline.json` — scene-by-scene plan with asset selection reasons and rights references
- `manifest.json` — job metadata, format details, validation results
- `rights.json` — full provenance record for every external media asset
- `captions.srt` — subtitle file with accurate timecodes
- `metrics.json` — runtime, cost estimates, QA status, performance data
- `job.log` — structured JSON log export for the job

Key differentiators:
- **Meaning-aware planning** — scenes are planned from narration semantics, not keyword matching
- **Deterministic routing** — stock → generated visual → typography card → recorded failure
- **Rights-first** — no asset enters output without a verified licence record
- **Honest QA** — all quality checks use real ffprobe measurements; nothing is fabricated

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker | ≥ 24.0 | With Docker Compose v2 plugin |
| Docker Compose | ≥ 2.20 | `docker compose` (not `docker-compose`) |
| Git | any | For cloning |
| 4 GB RAM | minimum | Whisper STT model + FFmpeg rendering |
| 10 GB disk | minimum | Models, MinIO storage, Docker images |

For local development without Docker:

| Requirement | Version |
|---|---|
| Python | 3.11 |
| FFmpeg + ffprobe | 6.x |
| PostgreSQL | 15 |
| Redis | 7 |

---

## Installation

```bash
# 1. Clone the repository
git clone <repo-url> sceneforge-ai
cd sceneforge-ai

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env — add API keys if you have them (optional; mock adapters used otherwise)
# See "Environment Setup" section below
```

---

## Environment Setup

Open `.env` and review the settings. All keys are optional for the no-key test suite.
The application runs fully with mock adapters when API keys are absent.

```bash
# Minimum required for Docker Compose (already set in .env.example):
POSTGRES_PASSWORD=change_me_in_production
MINIO_ROOT_PASSWORD=change_me_in_production

# Optional — enables live stock footage retrieval:
PEXELS_API_KEY=your_pexels_key_here
PIXABAY_API_KEY=your_pixabay_key_here

# Optional — selects TTS/STT adapters:
TTS_ADAPTER=mock          # or: edge_tts, coqui
STT_ADAPTER=mock          # or: whisper
STOCK_PROVIDER=mock       # or: pexels, pixabay

# For local development without Docker (prevents hanging on service connections):
SKIP_STARTUP_CHECKS=true
DATABASE_URL=sqlite:///./dev.db
```

See `.env.example` for the full list of configurable settings with descriptions.

> **Security**: Never commit a `.env` file with real secrets. The `.gitignore` excludes `.env`.

---

## Startup

```bash
# Build and start all services (API, worker, DB, Redis, MinIO, web)
docker compose up --build

# Or start in detached mode
docker compose up --build -d

# View logs
docker compose logs -f api
docker compose logs -f worker
```

Services will be available at:

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| API Docs (ReDoc) | http://localhost:8000/redoc |
| Web App | http://localhost:3000 |
| MinIO Console | http://localhost:9001 |

---

## Database Migrations

Migrations run automatically on API startup. To run manually:

```bash
# Inside the API container
docker compose exec api alembic upgrade head

# Or locally (with DB_URL set)
cd src
alembic upgrade head
```

To create a new migration after model changes:

```bash
docker compose exec api alembic revision --autogenerate -m "description"
```

---

## Running Tests

```bash
# No-key suite — runs without any external API keys or Docker services
# (Works on any machine with Python 3.11+ and the dev dependencies installed)

# Install dev dependencies (first time only)
pip install -r requirements-dev.txt

# Run the no-key suite (Phase 5 baseline: 449 tests)
SKIP_STARTUP_CHECKS=true STOCK_PROVIDER=mock GENERATED_PROVIDER=none \
  EMBEDDING_MODEL=mock AUDIO_INSPECTOR=mock LLM_ADAPTER=none \
  python -m pytest tests/unit/ tests/integration/test_api_jobs.py \
  -p no:cacheprovider --tb=short -q

# Expected result: 449 passed, 0 failed (Phase 5 baseline)

# Inside Docker (full service stack must be running):
docker compose exec api pytest tests/ -m "not requires_api_key" -v

# Full suite (requires API keys in .env for live-provider tests)
docker compose exec api pytest tests/ -v

# Hard-case suite only
docker compose exec api pytest tests/hard_cases/ -v

# Specific module
docker compose exec api pytest tests/unit/test_state_machine.py -v

# With coverage
SKIP_STARTUP_CHECKS=true python -m pytest tests/unit/ tests/integration/test_api_jobs.py \
  --cov=sceneforge --cov-report=term-missing -p no:cacheprovider
```

Test evidence is written to `tests/unit/evidence/` and `tests/integration/evidence/`.

---

## Generating a Video

### Via the web app

1. Open http://localhost:3000
2. Click **New Project**
3. Enter a script or upload a voiceover (or both)
4. Select output aspect ratio (16:9 or 9:16)
5. Click **Generate**
6. Monitor progress in the storyboard view
7. Download artifacts when the job completes

### Via the API

```bash
# Create a text-only job
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: my-unique-key-001" \
  -d '{
    "script": "Innovation drives progress. Every great idea starts with a single step.",
    "aspect_ratio": "16:9",
    "tts_adapter": "mock",
    "stock_provider": "mock"
  }'

# Response: {"job_id": "...", "status": "QUEUED"}

# Poll for status
curl http://localhost:8000/jobs/{job_id}

# Get storyboard once COMPLETED
curl http://localhost:8000/jobs/{job_id}/storyboard

# Download all artifacts (returns presigned redirect)
curl -L http://localhost:8000/jobs/{job_id}/artifacts/output.mp4     -o output.mp4
curl -L http://localhost:8000/jobs/{job_id}/artifacts/captions.srt   -o captions.srt
curl -L http://localhost:8000/jobs/{job_id}/artifacts/timeline.json  -o timeline.json
curl -L http://localhost:8000/jobs/{job_id}/artifacts/rights.json    -o rights.json
curl -L http://localhost:8000/jobs/{job_id}/artifacts/manifest.json  -o manifest.json
curl -L http://localhost:8000/jobs/{job_id}/artifacts/metrics.json   -o metrics.json
```

### FFmpeg requirement

FFmpeg must be installed for a real MP4 to be rendered. Without FFmpeg, the
orchestrator writes a clearly-labelled placeholder MP4 and records
`manifest.json.real_mp4_rendered: false`.

**Docker Compose (recommended)**: FFmpeg is installed automatically in the
container — `docker compose up --build` handles everything.

**Local dev with real FFmpeg**: Install FFmpeg 6.x and ensure `ffmpeg` and
`ffprobe` are on PATH. Set `FFMPEG_BIN=ffmpeg` and `FFPROBE_BIN=ffprobe` in `.env`.

See `docs/e2e_milestone.md` for the complete end-to-end demo sequence.

---

## Batch Runner

The batch runner submits a set of test cases, waits for completion, and produces a report.

```bash
# Run the default test suite
python scripts/batch_runner.py --cases tests/fixtures/batch_cases.yaml --output report.json

# Run with live API (adjust base URL)
python scripts/batch_runner.py \
  --cases tests/fixtures/batch_cases.yaml \
  --base-url http://localhost:8000 \
  --output report.json \
  --report-text report.txt

# Exit code: 0 = all pass, 1 = one or more failures
```

---

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI spec**: `openapi.yaml` in the repository root

All endpoints, request/response schemas, and error formats are documented in `openapi.yaml`.

---

## Troubleshooting

**`docker compose up` fails on DB connection**
- Wait 10–15 seconds for PostgreSQL to initialise on first run.
- Check `docker compose logs db` for startup errors.

**Whisper model download is slow**
- The base Whisper model (~74 MB) is downloaded on first use.
- Set `STT_ADAPTER=mock` to skip this entirely.
- Pre-download by running `docker compose exec worker python -c "import whisper; whisper.load_model('base')"`

**Stock footage returns no results**
- Ensure `PEXELS_API_KEY` or `PIXABAY_API_KEY` is set in `.env`.
- Without a key, `STOCK_PROVIDER` defaults to `mock` automatically.

**FFmpeg not found**
- FFmpeg is installed inside the Docker image. For local dev, install FFmpeg 6.x and ensure `ffmpeg` and `ffprobe` are on PATH.

**MinIO connection refused**
- MinIO takes a few seconds to start. The API retries connection on startup.
- Check http://localhost:9001 to confirm MinIO is running.

**Job stuck in RENDERING**
- Check worker logs: `docker compose logs -f worker`
- A stuck job can be cancelled: `POST /jobs/{job_id}/cancel`

---

## Known Limitations

- **edge-tts**: Uses Microsoft Edge's browser TTS endpoint. Not officially supported for
  production use. Switch to `TTS_ADAPTER=coqui` or `TTS_ADAPTER=mock` if terms are a concern.
- **Portrait reframing**: Subject-aware crop uses a heuristic. Complex scenes with multiple
  subjects may not crop optimally; blurred-pad fallback is always available.
- **Generative video**: No generative video provider is included by default. The router
  falls back to generated stills (with motion effect) or typography cards.
- **LLM planner**: The optional LLM scene planner requires an OpenAI API key. The
  rule-based planner is the default and works without any external keys.
- **Multilingual**: Hindi and Tamil TTS/STT are in the advanced features scope and may
  not be fully implemented before the Phase 7 deadline.
- **Assessment workbook**: Certain workbook fields require manual completion by the
  submitter. See the submission checklist in `docs/submission_checklist.md`.


---

## 🚨 HANDOVER NOTICE — READ THIS FIRST

**This project has been transferred from Kiro AI to Antigravity AI.**

**👉 If you are Antigravity or inheriting this project:**

Start with: **[`docs/handover/00_START_HERE.md`](docs/handover/00_START_HERE.md)**

This document contains everything you need to understand the current state, run the tests, start the application, and continue development.

**Complete handover package:** [`docs/handover/`](docs/handover/)

**Latest status:** Functional end-to-end verification with real MP4, real TTS, real captions (2026-10-20).

---
