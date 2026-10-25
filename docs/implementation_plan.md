# Implementation Plan
## SceneForge AI — IncuBrix SEA PS3

> **Version**: 1.0 (Phase 1 — Planning)
> **Deadline**: October 25, 2026 — 11:59 PM IST
> **Current Phase**: 1 of 7 (complete)

---

## Phase Overview

| Phase | Scope | Priority | Dependencies |
|---|---|---|---|
| 1 | Inspect, plan, document | Mandatory | None |
| 2 | Skeleton: DB, state machine, storage, mock adapters, API contracts | Mandatory | Phase 1 |
| 3 | Audio pipeline, TTS/STT, scene planning, timeline | Mandatory | Phase 2 |
| 4 | Media retrieval, semantic ranking, routing, rights passport | Mandatory | Phase 3 |
| 5 | FFmpeg rendering, subtitles, QA, incremental cache, manifests | Mandatory | Phase 4 |
| 6 | Integration Standard, hard-case suite, batch runner, metrics | Mandatory | Phase 5 |
| 7 | Frontend, end-to-end tests, final docs, submission checklist | Mandatory | Phase 6 |

**Advanced features** (only after all phases pass):
- Human-calibrated VLM relevance judge
- Multilingual support (Hindi, Tamil)
- Performance benchmark report

---

## Phase 1 — Inspect and Plan ✓

**Goal**: Understand the full requirement surface; produce traceability matrix and architecture
before writing any implementation code.

### Deliverables

- [x] `docs/requirements_traceability.md` — 8 MH, 10 IS, 24 HC, 14 DoD gates
- [x] `docs/architecture.md` — module map, data flow, DB schema, security design
- [x] `docs/implementation_plan.md` — this document
- [x] Directory structure created
- [ ] `README.md`, `REPORT.md`, `SOURCES.md`, `AI_USE.md` skeletons (Phase 1 step 5)
- [ ] `.env.example` (Phase 1 step 6)

### Identified Gaps

- GAP-01: No official brief PDF found — matrix uses prompt as provisional source.
- GAP-02: Audio test fixtures must be generated synthetically.
- GAP-03: Stock provider API keys (Pexels/Pixabay) required for live retrieval.
- GAP-04: TTS provider licence verification pending.
- GAP-05: LLM adapter is optional; rule-based planner is mandatory primary.
- GAP-06: Assessment workbook fields require manual completion.

---

## Phase 2 — Project Skeleton

**Goal**: Runnable application with DB, queue, storage, state machine, and typed API
contracts. Zero business logic yet — all external calls go through mock adapters.
End state: `docker compose up` works; `POST /jobs` creates a job that moves through
states using mock adapters and lands in COMPLETED with placeholder artifacts.

### Task List

#### 2.1 Python package setup
- [ ] `pyproject.toml` (or `setup.cfg`) with all dependencies pinned
- [ ] `requirements.txt` (production) and `requirements-dev.txt`
- [ ] `src/sceneforge/__init__.py` and all sub-package `__init__.py` files

#### 2.2 Database
- [ ] SQLAlchemy models: `Job`, `Scene`, `RightsRecord`, `Metric`
- [ ] Alembic configuration and initial migration
- [ ] `JobRepository` with CRUD and idempotency check
- [ ] Unit tests: `tests/unit/test_repository.py`

#### 2.3 State machine
- [ ] `state_machine.py` with all states and valid transitions
- [ ] Timestamp stamping per transition
- [ ] Invalid transition raises `InvalidTransitionError`
- [ ] Unit tests: `tests/unit/test_state_machine.py`

#### 2.4 Object storage
- [ ] MinIO client wrapper (`storage/client.py`)
- [ ] Canonical path helpers (`storage/paths.py`)
- [ ] Presigned URL generator (`storage/presigned.py`)
- [ ] Integration test: `tests/integration/test_storage.py`

#### 2.5 Mock adapters (all providers)
- [ ] `audio/adapters/mock_tts.py` — returns deterministic WAV bytes
- [ ] `audio/adapters/mock_stt.py` — returns fixed transcript + word timestamps
- [ ] `retrieval/adapters/mock_stock.py` — returns 3 fixture video assets
- [ ] `retrieval/adapters/mock_generated.py` — returns 1 fixture still image
- [ ] `planner/adapters/mock_llm.py` — returns pre-built ScenePlan list
- [ ] Unit tests: `tests/unit/test_mock_adapters.py`

#### 2.6 API contracts
- [ ] Pydantic schemas: `JobCreate`, `JobRead`, `JobStatus`, `ErrorResponse`
- [ ] `POST /jobs` (create + idempotency)
- [ ] `GET /jobs/{id}` (status + progress)
- [ ] `GET /jobs/{id}/storyboard`
- [ ] `GET /jobs/{id}/artifacts/{filename}` (presigned redirect)
- [ ] `GET /health` and `GET /ready`
- [ ] Error handler → IS-03 schema
- [ ] Correlation ID middleware
- [ ] Unit tests: `tests/unit/test_api_contracts.py`

#### 2.7 Background worker
- [ ] RQ worker entry point
- [ ] `PipelineOrchestrator` stub (calls mock adapters, advances states)
- [ ] Job retry logic with exponential backoff
- [ ] Integration test: `tests/integration/test_worker_basic.py`

#### 2.8 Observability
- [ ] structlog JSON configuration
- [ ] Correlation ID context var
- [ ] Unit tests: `tests/unit/test_logging.py`

#### 2.9 Docker Compose
- [ ] `Dockerfile` (multi-stage: builder + runtime)
- [ ] `docker-compose.yml` (api, worker, db, redis, minio, web placeholder)
- [ ] Health checks for all services
- [ ] Alembic auto-run on API startup

#### 2.10 HMAC callbacks
- [ ] `api/callbacks.py` — sign outbound, verify inbound
- [ ] Constant-time comparison, timestamp window
- [ ] Unit tests: `tests/unit/test_callbacks.py`

### Phase 2 Exit Criteria
- `docker compose up --build` starts cleanly
- `GET /health` returns 200
- `POST /jobs` with mock adapters creates a job and returns job_id
- `GET /jobs/{id}` shows COMPLETED status after worker runs
- All unit tests in Phase 2 pass
- No external API keys required

---

## Phase 3 — Audio Pipeline and Scene Planning

**Goal**: Real TTS and STT adapters (with mocks as fallback); working scene planner;
deterministic timeline generation from narration.

### Task List

#### 3.1 Audio inspection
- [ ] `audio/adapters/audio_inspector.py` (ffprobe wrapper)
- [ ] Detect: duration, codec, channels, sample rate, silence, music-only
- [ ] Unit tests: `tests/unit/test_audio_inspector.py`

#### 3.2 Audio validation
- [ ] `audio/validation.py` — empty, unsupported, silent, music-only, corrupted
- [ ] Unit tests: `tests/unit/test_audio_validation.py`
- [ ] Hard cases: HC-09 (silent), HC-10 (music), HC-11 (wrong type), HC-12 (empty script)

#### 3.3 TTS adapter (edge-tts or Coqui)
- [ ] `audio/adapters/edge_tts.py` — generate WAV from text
- [ ] Feature-flagged: `TTS_ADAPTER=edge_tts` (default) or `TTS_ADAPTER=mock`
- [ ] Unit tests: `tests/unit/test_tts_adapter.py` (mock mode)

#### 3.4 STT adapter (Whisper local)
- [ ] `audio/adapters/whisper_stt.py` — transcribe + word timestamps
- [ ] Feature-flagged: `STT_ADAPTER=whisper` or `STT_ADAPTER=mock`
- [ ] Unit tests: `tests/unit/test_stt_adapter.py` (mock mode)

#### 3.5 Audio pipeline
- [ ] `audio/pipeline.py` — text-only / audio-only / combined path routing
- [ ] Script/audio mismatch detection and reporting
- [ ] Integration test: `tests/integration/test_audio_pipeline.py`
- [ ] Hard cases: HC-18 (mismatch), HC-09, HC-10, HC-11, HC-12

#### 3.6 Scene segmenter
- [ ] `planner/segmenter.py` — sentence split + pause gap detection
- [ ] Merge short segments below min_duration
- [ ] Unit tests: `tests/unit/test_segmenter.py`

#### 3.7 Rule-based scene planner
- [ ] `planner/adapters/rule_based.py`
- [ ] Disambiguation table (bank, cloud, etc.)
- [ ] Abstract → typography card; numeric → data card
- [ ] Safety rules: named persons, brands
- [ ] ScenePlan schema validation
- [ ] Unit tests: `tests/unit/test_planner.py`
- [ ] Hard cases: HC-01 through HC-07

#### 3.8 Timeline builder
- [ ] `timeline/builder.py` — assemble from scenes
- [ ] `timeline/pacing.py` — merge short, align to phrase boundaries
- [ ] `timeline/serialiser.py` — write timeline.json
- [ ] Schema validation against `schemas/timeline.schema.json`
- [ ] Unit tests: `tests/unit/test_timeline.py`

### Phase 3 Exit Criteria
- Text-only input → NarrationResult with real or mock TTS audio
- Audio-only input → NarrationResult with transcript and word timestamps
- Combined input → mismatch report
- ScenePlan produced for all test inputs including hard cases
- timeline.json passes schema validation
- No external API keys required in no-key mode

---

## Phase 4 — Media Retrieval, Routing, and Rights

**Goal**: Real stock provider adapters; semantic ranking with local embeddings;
deterministic routing; rights passport for every selected asset.

### Task List

#### 4.1 Embedding model
- [ ] `retrieval/adapters/sentence_transformer.py` (all-MiniLM-L6-v2)
- [ ] Cosine similarity scoring
- [ ] Unit tests: `tests/unit/test_embeddings.py`

#### 4.2 Stock provider adapters
- [ ] `retrieval/adapters/pexels.py` — search, download, metadata
- [ ] `retrieval/adapters/pixabay.py` — search, download, metadata
- [ ] Feature-flagged: `STOCK_PROVIDER=pexels|pixabay|mock`
- [ ] Validate API key present; graceful degradation if absent

#### 4.3 Multi-query searcher
- [ ] `retrieval/searcher.py` — 2–4 queries per scene; dedup; metadata validate
- [ ] Unit tests: `tests/unit/test_searcher.py`

#### 4.4 Candidate ranker
- [ ] `retrieval/ranker.py` — cosine score; duplicate penalty; record all scores
- [ ] Unit tests: `tests/unit/test_ranker.py`

#### 4.5 Source router
- [ ] `retrieval/router.py` — priority policy; RouteResult with reason
- [ ] Configurable thresholds via env
- [ ] Unit tests: `tests/unit/test_router.py`
- [ ] Hard cases: HC-14, HC-15, HC-16, HC-17

#### 4.6 Rights passport
- [ ] `rights/passport.py` — create RightsRecord from provider metadata
- [ ] `rights/validator.py` — licence compatibility check
- [ ] `rights/serialiser.py` — write rights.json; link manifest
- [ ] SHA-256 hash computed post-download
- [ ] Unit tests: `tests/unit/test_rights.py`
- [ ] Hard case: HC-24 (invalid licence)

#### 4.7 Typography and data card generator
- [ ] `rendering/card_generator.py` — FFmpeg lavfi/drawtext cards
- [ ] Unit tests: `tests/unit/test_card_generator.py`
- [ ] Hard case: HC-01 (abstract), HC-02 (numeric)

### Phase 4 Exit Criteria
- All scenes have a RouteResult with reason recorded in timeline
- All selected assets have a RightsRecord with SHA-256 hash
- Unverified-licence assets are excluded
- Provider outage → graceful fallback (HC-14, HC-15, HC-16)
- No external API keys required when STOCK_PROVIDER=mock

---

## Phase 5 — Rendering, QA, and Incremental Cache

**Goal**: FFmpeg renders real output.mp4; QA validates it with ffprobe; incremental
cache reuses unchanged segments; all seven output artifacts are written to MinIO.

### Task List

#### 5.1 FFmpeg renderer
- [ ] `rendering/renderer.py` — filter graph; concat scenes; encode H.264/AAC
- [ ] `rendering/subtitle_writer.py` — captions.srt from scene captions
- [ ] `rendering/reframer.py` — portrait crop with blurred-pad fallback
- [ ] `rendering/normaliser.py` — colour + pixel format
- [ ] Integration test: `tests/integration/test_renderer.py`
- [ ] Hard case: HC-08 (portrait edge)

#### 5.2 Incremental render cache
- [ ] `rendering/cache.py` — content-addressed keys; per-job isolation
- [ ] Cache-hit test: `tests/unit/test_render_cache.py`
- [ ] Ensure no cross-user leakage: `tests/integration/test_cache_isolation.py`

#### 5.3 Manifest and metrics writers
- [ ] `jobs/manifest_writer.py` — writes manifest.json
- [ ] `observability/metrics.py` — writes metrics.json
- [ ] Schema validation against `schemas/manifest.schema.json`

#### 5.4 QA module
- [ ] All 12 QA checks implemented (see architecture §3.10)
- [ ] Scene-level retry on failure
- [ ] Unit tests: `tests/unit/test_quality.py`
- [ ] Integration test: `tests/integration/test_qa_integration.py`

#### 5.5 Artifact upload
- [ ] Upload all 7 artifacts to MinIO after QA PASS
- [ ] Artifact download endpoint returns presigned URL
- [ ] Integration test: `tests/integration/test_output_contract.py`

#### 5.6 End-to-end smoke test (mock adapters)
- [ ] `tests/integration/test_e2e_pipeline.py`
- [ ] Produces real validated MP4 with mock media
- [ ] Verifies all 7 artifacts present and schema-valid

### Phase 5 Exit Criteria
- End-to-end job produces real output.mp4 (H.264, AAC, correct dimensions)
- All 7 artifacts present in MinIO and downloadable
- QA module runs all 12 checks and reports accurately
- Unchanged scene reuses cached segment
- Modified scene triggers re-render
- No external API keys required

---

## Phase 6 — Integration Standard and Hard-Case Suite

**Goal**: All 10 Integration Standard items implemented and tested; all 24 hard cases
covered; batch runner operational; structured logs verified; performance metrics collected.

### Task List

#### 6.1 Idempotency (IS-01)
- [ ] Enforce in `POST /jobs`; Redis key store with 24h TTL
- [ ] Tests: `tests/integration/test_idempotency.py`

#### 6.2 HMAC callbacks (IS-02)
- [ ] Sign outbound webhooks; verify inbound
- [ ] Tests: `tests/unit/test_callbacks.py` (complete)

#### 6.3 Error schema (IS-03)
- [ ] All error handlers return IS-03 schema
- [ ] Tests: `tests/unit/test_error_schema.py`

#### 6.4 MinIO (IS-04)
- [ ] Already done in Phase 2/5; add complete integration test

#### 6.5 Structured logs (IS-05)
- [ ] Verify all log lines; no secrets; job_id + correlation_id present
- [ ] Tests: `tests/unit/test_logging.py` (complete)

#### 6.6 Batch runner (IS-06)
- [ ] `scripts/batch_runner.py` — YAML test cases; JSON report; non-zero on failure
- [ ] `tests/fixtures/batch_cases.yaml` — all input types
- [ ] Tests: `tests/integration/test_batch_runner.py`

#### 6.7 Mock adapters (IS-07)
- [ ] Already done in Phase 2; verify all interfaces covered

#### 6.8 No-key test suite (IS-08 / MH-08)
- [ ] `pytest tests/ -m "not requires_api_key"` passes with zero failures
- [ ] Document how to run

#### 6.9 Job resilience (IS-08 behaviour)
- [ ] Retry tests, worker restart test
- [ ] Tests: `tests/integration/test_job_resilience.py`

#### 6.10 OpenAPI (IS-09)
- [ ] `openapi.yaml` generated from FastAPI and validated
- [ ] All endpoints documented; schemas match Pydantic
- [ ] Tests: `tests/unit/test_openapi.py`

#### 6.11 Docker Compose (IS-10)
- [ ] Smoke test from clean build
- [ ] Tests: `tests/integration/test_docker_compose.py`

#### 6.12 Hard-case suite
- [ ] All 24 HC tests implemented and run
- [ ] Failed tests preserved with diagnostic evidence
- [ ] Summary report generated

#### 6.13 Performance metrics
- [ ] Collect per-stage timing, retry count, fallback frequency
- [ ] Write to metrics.json; verify not fabricated

### Phase 6 Exit Criteria
- All 10 IS items have passing tests
- All 24 hard cases have tests (some may FAIL with honest diagnostics)
- Batch runner produces reproducible JSON report
- No-key suite passes: `pytest tests/ -m "not requires_api_key"`
- metrics.json contains real measured values

---

## Phase 7 — Frontend, End-to-End Tests, Documentation, Submission

**Goal**: Polished storyboard UI; complete documentation; submission checklist;
repository has no secrets; all DoD gates checked.

### Task List

#### 7.1 React frontend
- [ ] `apps/web/` — Vite + React + TypeScript + Tailwind
- [ ] Pages: dashboard, input, aspect-ratio selector, storyboard, render progress,
       artifact download, QA report, rights provenance
- [ ] API client with typed models
- [ ] Loading states, error messages, accessible controls

#### 7.2 End-to-end tests (browser + API)
- [ ] Text-only, audio-only, combined-input workflows
- [ ] Verify artifacts downloadable from UI
- [ ] Verify QA report displays accurately

#### 7.3 Documentation completion
- [ ] `README.md` — full install, run, test, demo instructions
- [ ] `REPORT.md` — problem statement, architecture, decisions, test results
- [ ] `SOURCES.md` — all libraries, models, media, licences
- [ ] `AI_USE.md` — disclosure of AI assistance
- [ ] `openapi.yaml` — final review and validate
- [ ] `schemas/timeline.schema.json` and `schemas/manifest.schema.json` — final

#### 7.4 Traceability matrix final update
- [ ] Update every requirement status to PASS (with evidence) or FAIL (with honest diagnostic)
- [ ] All DoD gates checked

#### 7.5 Submission checklist
- [ ] Identify fields requiring manual completion in assessment workbook
- [ ] List required unedited demo video segments
- [ ] List required submission links
- [ ] Confirm no secrets in repository (git-secrets scan or equivalent)

### Phase 7 Exit Criteria
- All DoD gates PASS or honestly documented as FAIL/BLOCKED
- Repository has no secrets
- `README.md` enables independent reproduction from clean checkout
- Submission checklist complete

---

## External Services and Configuration Decisions

### Stock footage providers

**Pexels** (recommended primary):
- Free tier: unlimited API calls, commercial use permitted
- Requires free account and API key: https://www.pexels.com/api/
- Configure: `PEXELS_API_KEY=<key>` in `.env`
- Mock used when key absent

**Pixabay** (secondary fallback):
- Free tier: commercial use permitted
- Requires free account and API key: https://pixabay.com/api/docs/
- Configure: `PIXABAY_API_KEY=<key>` in `.env`
- Mock used when key absent

### TTS provider

**edge-tts** (primary candidate):
- Uses Microsoft Edge's browser TTS endpoint
- No API key required; free for personal/demo use
- Licence: verify before production deployment
- Install: `pip install edge-tts`
- Configure: `TTS_ADAPTER=edge_tts`

**Coqui TTS** (offline alternative):
- Apache 2.0 / Mozilla Public Licence depending on model
- Runs fully locally; no network calls
- Requires model download (~100–300 MB)
- Configure: `TTS_ADAPTER=coqui`

### STT provider

**OpenAI Whisper** (local):
- MIT licence
- Models: tiny (39M), base (74M), small (244M)
- Default: `WHISPER_MODEL=base` for speed; `small` for accuracy
- Requires `openai-whisper` pip package + model download on first run
- Configure: `STT_ADAPTER=whisper`

### Embedding model

**sentence-transformers/all-MiniLM-L6-v2**:
- Apache 2.0
- 22M parameters; ~80 MB download
- Runs locally via `sentence-transformers` pip package
- No API key required

---

## Risk Register

| Risk ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | Official brief differs from prompt requirements | Medium | High | Review brief immediately; update traceability matrix; prioritise |
| R-02 | FFmpeg GPL licence concern with H.264 | Low | Medium | Use pre-built static binary from BtbN/FFmpeg-Builds (LGPL + H.264) |
| R-03 | edge-tts ToS violation for assessment submission | Medium | Medium | Switch to Coqui TTS (Apache 2.0) if ToS concern raised |
| R-04 | Whisper model too slow on available hardware | Medium | Low | Use `tiny` model; mock in no-key tests |
| R-05 | Pexels/Pixabay rate limit during demo | Low | Medium | Cache results; mock adapter always available |
| R-06 | PostgreSQL migration fail in Docker | Low | High | Test migration in CI; add retry logic in startup script |
| R-07 | Time constraint before October 25 deadline | High | High | Prioritise Phases 2–5 (core pipeline); Phase 7 frontend last |

---

## Testing Strategy Summary

### Test categories

| Category | Location | Key requirement |
|---|---|---|
| Unit tests | `tests/unit/` | No DB, no network, no API keys |
| Integration tests | `tests/integration/` | Dockerised services; no external API keys (mock mode) |
| Hard-case tests | `tests/hard_cases/` | Covers all 24 edge/failure scenarios |
| End-to-end tests | `tests/integration/test_e2e_pipeline.py` | Full pipeline with real FFmpeg |

### Running tests

```bash
# No-key suite (CI-safe):
pytest tests/ -m "not requires_api_key" -v

# With API keys (live providers):
pytest tests/ -m "requires_api_key" -v

# Hard-case suite only:
pytest tests/hard_cases/ -v

# Full suite:
pytest tests/ -v
```

### Test markers

```python
@pytest.mark.requires_api_key   # skip when no keys configured
@pytest.mark.slow               # skip in fast CI runs
@pytest.mark.hard_case          # hard-case scenarios
@pytest.mark.integration        # requires running services
```

---

## File Creation Order (Phase 2 start)

Priority order for Phase 2 implementation:

1. `pyproject.toml` + `requirements*.txt`
2. `src/sceneforge/` package structure + `__init__.py` files
3. `src/sceneforge/jobs/models.py` + `state_machine.py`
4. `alembic/` config + initial migration
5. `src/sceneforge/jobs/repository.py`
6. `src/sceneforge/storage/client.py` + `paths.py`
7. `src/sceneforge/audio/adapters/mock_*.py`
8. `src/sceneforge/retrieval/adapters/mock_*.py`
9. `src/sceneforge/planner/adapters/mock_*.py`
10. `src/sceneforge/api/app.py` + routes + error handler
11. `src/sceneforge/api/callbacks.py`
12. `src/sceneforge/observability/logging.py`
13. `src/sceneforge/jobs/worker.py` + `orchestrator.py`
14. `Dockerfile` + `docker-compose.yml`
15. All Phase 2 tests
