# Repository Map & File Guide

**Project Root:** `C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3`

---

## Top-Level Files

| File | Purpose |
|---|---|
| `.env.example` | Environment template (copy to `.env`) |
| `README.md` | Main documentation |
| `REPORT.md` | Engineering progress report |
| `SOURCES.md` | Attribution and sources |
| `AI_USE.md` | AI usage disclosure |
| `pyproject.toml` | Python project config |
| `requirements.txt` | Production dependencies |
| `requirements-dev.txt` | Dev + test dependencies |
| `Dockerfile` | Container image definition |
| `docker-compose.yml` | Multi-service orchestration |
| `alembic.ini` | Database migration config |
| `openapi.json` | OpenAPI 3.1 spec (generated) |

---

## Core Directories

### `src/sceneforge/` — Main Application (12 modules)

```
sceneforge/
├── __init__.py
├── api/                    → FastAPI routes & middleware
├── audio/                  → TTS, STT, validation
├── jobs/                   → Job orchestration, state machine
├── observability/          → Logging, correlation IDs
├── planner/                → Scene planning, segmentation
├── providers/              → Abstract provider interfaces
├── quality/                → QA checks
├── rendering/              → FFmpeg, subtitles, cache
├── retrieval/              → Media search, ranking, routing
├── rights/                 → Licence tracking, passport
├── schemas/                → Pydantic/dataclass models
├── storage/                → Filesystem + MinIO backends
└── timeline/               → Timeline building, SRT generation
```

### `tests/` — Test Suite

```
tests/
├── unit/                   → 449+ unit tests
│   ├── test_*.py          → Individual module tests
│   └── test_fixtures/     → Mock data
├── integration/            → API + end-to-end tests
│   ├── test_api_jobs.py   → Job creation/status
│   └── ...
├── fixtures/               → Shared test data
│   └── batch_cases.json   → Batch runner test cases
└── conftest.py            → Pytest configuration
```

### `alembic/` — Database Migrations

```
alembic/
├── versions/              → Individual migration files
│   ├── 001_initial.py
│   ├── 002_add_fields.py
│   └── ...
├── env.py                 → Migration runtime config
└── script.py.mako         → Migration template
```

### `schemas/` — JSON Schemas

```
schemas/
├── job_create_request.json
├── job_status_response.json
├── timeline.json
├── rights_record.json
└── manifest.json
```

### `scripts/` — Utility Scripts

```
scripts/
├── pre_generate_tts.py    → Generate real TTS audio on host
├── batch_runner.py        → Batch job CLI
└── install_font.py        → Download Roboto font
```

### `apps/` — Frontend (if present)

Currently minimal; no active web UI.

### `docs/` — Documentation

```
docs/
├── handover/              → This handover package
│   ├── 00_START_HERE.md  → Entry point
│   ├── 01_PROJECT_REQUIREMENTS.md
│   ├── 02_ARCHITECTURE_AND_DATA_FLOW.md
│   ├── 03_REPOSITORY_MAP.md (this file)
│   ├── 04_IMPLEMENTATION_STATUS.md
│   ├── 05_END_TO_END_EVIDENCE.md
│   ├── 06_SETUP_AND_COMMANDS.md
│   ├── 07_ENVIRONMENT_AND_SECRETS.md
│   ├── 08_TESTING_AND_DEBUGGING.md
│   ├── 09_KNOWN_GAPS_AND_NEXT_STEPS.md
│   ├── 10_DECISION_LOG.md
│   └── 11_ANTIGRAVITY_FIRST_TASK.md
├── architecture.md        → System design
├── e2e_milestone.md       → Previous E2E report
└── ...
```

---

## Key Source Modules

### `api/app.py`
- FastAPI app creation
- Middleware setup
- Lifespan events (startup, shutdown)

### `api/routes/jobs.py`
- POST /jobs — Create job
- GET /jobs/{id} — Job status
- GET /jobs/{id}/artifacts
- POST /jobs/{id}/cancel

### `jobs/orchestrator.py`
- Main pipeline orchestration (6 stages)
- Job state machine
- Error handling

### `jobs/repository.py`
- Database CRUD for Job, Scene, RightsRecord
- State transition logic

### `audio/pipeline.py`
- TTS → validation → storage flow

### `audio/factory.py`
- TTS adapter selection (mock, edge_tts, host_tts)

### `planner/segmenter.py`
- Sentence segmentation
- Concept extraction

### `retrieval/searcher.py` & `retrieval/ranker.py`
- Media search
- Relevance scoring
- Routing policy

### `rendering/renderer.py`
- FFmpeg orchestration
- Subtitle burning
- Quality check

### `storage/client.py`
- Storage abstraction (filesystem or MinIO)

---

## Important Files to Know

| Path | Purpose | Status |
|---|---|---|
| `src/sceneforge/audio/adapters/host_tts.py` | Host-assisted TTS | ✅ NEW (Kiro added) |
| `src/sceneforge/audio/adapters/mock_tts.py` | Mock TTS (silent) | ✅ Working |
| `src/sceneforge/audio/adapters/edge_tts_adapter.py` | Real TTS (network) | ⚠️ Blocked in Docker |
| `src/sceneforge/storage/filesystem_client.py` | Local disk storage | ✅ NEW (Kiro added) |
| `scripts/pre_generate_tts.py` | TTS pre-gen on host | ✅ NEW (Kiro added) |
| `scripts/batch_runner.py` | Batch job CLI | ✅ NEW (Kiro added) |
| `.env.example` | Config template | ✅ Updated |
| `docker-compose.yml` | Services config | ✅ Updated |
| `Dockerfile` | Container build | ✅ Updated |

---

## What to Read First

1. **Understanding the project:** `README.md` → `REPORT.md`
2. **For API usage:** `openapi.json` or `api/routes/jobs.py`
3. **For data models:** `schemas/` directory
4. **For tests:** `tests/unit/` (start with a simple one)
5. **For orchestration:** `jobs/orchestrator.py`
6. **For debugging:** `observability/logging.py`

---

## Do NOT Edit Without Reason

- `alembic/versions/` — Database schemas (breaking!)
- `src/sceneforge/schemas/` — Data models (requires migration)
- Core business logic without understanding the purpose

---

## Safe to Modify

- `scripts/` — Utility scripts
- `tests/` — Add new tests
- Configuration in `docker-compose.yml`
- Environment variables in `.env`
- Documentation in `docs/`

---

**Prepared by:** Kiro AI  
**Last Updated:** 2026-10-20
