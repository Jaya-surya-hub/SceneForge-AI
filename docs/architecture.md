# Architecture Document
## SceneForge AI — IncuBrix SEA PS3

> **Version**: 1.0 (Phase 1 — Planning)
> **Last Updated**: Phase 1
> **Status**: DRAFT — subject to revision as implementation reveals constraints

---

## 1. System Overview

SceneForge AI is a meaning-aware, narration-driven B-roll video generation engine. It accepts a
script, a voiceover audio file, or both, and produces a narrated, captioned MP4 video with full
rights provenance, quality-validated output, and a complete audit trail.

The system is designed around four core principles:

1. **Meaning before keywords** — scene planning derives visual intent from narration semantics,
   not surface-level string matching.
2. **Deterministic routing** — media selection follows a documented, configurable priority policy
   so every output is reproducible and explainable.
3. **Rights-first** — no media asset enters the output without a verified licence record.
4. **Honest reporting** — QA checks are real and results are accurate; no metric is fabricated.

---

## 2. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CLIENT LAYER                                     │
│   React/Vite/TypeScript Web App  │  CLI batch_runner.py  │  Direct API      │
└──────────────────┬──────────────────────────┬────────────────────────────── ┘
                   │  HTTP/REST (FastAPI)      │
┌──────────────────▼──────────────────────────▼────────────────────────────── ┐
│                            API LAYER  (FastAPI)                              │
│                                                                              │
│  /jobs  /jobs/{id}  /jobs/{id}/storyboard  /jobs/{id}/scenes/{n}/replace    │
│  /jobs/{id}/render  /jobs/{id}/artifacts   /jobs/{id}/metrics               │
│  /health  /ready                                                             │
│                                                                              │
│  Middleware: CorrelationID │ RequestSizeLimit │ ErrorHandler │ HMAC-Verify   │
└──────────────────┬─────────────────────────────────────────────────────────┘
                   │  enqueue task
┌──────────────────▼─────────────────────────────────────────────────────────┐
│                         JOB QUEUE  (Redis + RQ)                             │
│                                                                              │
│   JobQueue  →  Worker  →  PipelineOrchestrator                              │
│                              │                                              │
│            ┌─────────────────┼────────────────────────────┐                │
│            │                 │                             │                │
│     AudioStage         PlannerStage               RetrievalStage            │
│            │                 │                             │                │
│     RenderStage ◄────────────┘                     RouterStage              │
│            │                                             │                  │
│      QAStage  ◄────────────────────────────────────────  │                  │
│            │                                                                 │
│      ArtifactStage  (upload to MinIO, write manifests)                      │
└────────────┬───────────────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                            │
│                                                                              │
│  PostgreSQL (jobs, scenes, rights, metrics)                                  │
│  Redis      (job queue, idempotency keys, rate limits)                       │
│  MinIO S3   (uploads, rendered segments, final artifacts)                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Module Responsibilities

### 3.1 `src/sceneforge/api/`

**Responsibility**: HTTP surface — routing, validation, authentication, error handling.

| File | Purpose |
|---|---|
| `app.py` | FastAPI application factory; mounts routers; adds middleware |
| `routes/jobs.py` | Job CRUD, upload, status, storyboard, artifact download |
| `routes/health.py` | `/health` and `/ready` endpoints |
| `middleware/correlation.py` | Injects `X-Correlation-ID` on every request/response |
| `middleware/size_limit.py` | Rejects oversized payloads before parsing |
| `callbacks.py` | Outbound webhook signing and inbound HMAC verification |
| `errors.py` | Global exception handlers; maps domain errors to IS-03 schema |
| `dependencies.py` | FastAPI `Depends()` factories (DB session, storage client, queue) |

**Key design decisions**:
- All request/response types are Pydantic models — no raw dicts in routes.
- Idempotency is enforced at the route layer using a Redis-backed key store.
- File uploads are streamed to MinIO; they are never written to the API container's filesystem.
- Presigned URLs are used for artifact downloads to avoid streaming large files through the API.

---

### 3.2 `src/sceneforge/jobs/`

**Responsibility**: Job lifecycle, state machine, persistence, queue management.

| File | Purpose |
|---|---|
| `models.py` | SQLAlchemy ORM models: `Job`, `Scene`, `RightsRecord`, `Metric` |
| `repository.py` | DB access layer; all SQL here, none in routes or workers |
| `state_machine.py` | Defines valid transitions; raises on invalid; stamps timestamps |
| `worker.py` | RQ worker entry point; runs `PipelineOrchestrator` |
| `orchestrator.py` | Coordinates pipeline stages; handles retries and error propagation |
| `retry.py` | Configurable exponential backoff; distinguishes transient vs. permanent |
| `schemas.py` | Pydantic schemas for job create/read/update |

**State machine transitions**:
```
QUEUED → VALIDATING → PLANNING → RETRIEVING → RENDERING → QA → COMPLETED
                                                               ↘
Any state → FAILED (with error code)
Any state → CANCELLED (explicit user request)
FAILED → QUEUED (explicit retry, limited attempts)
```

**Idempotency**:
- `Idempotency-Key` header required for `POST /jobs`.
- Key stored in Redis with TTL of 24 h.
- Same key + same payload hash → return existing job, HTTP 200.
- Same key + different payload hash → HTTP 409 with `IDEMPOTENCY_CONFLICT`.

---

### 3.3 `src/sceneforge/audio/`

**Responsibility**: TTS, STT, audio metadata inspection, word-timestamp alignment.

```
audio/
  interfaces.py        # Abstract base classes: TTSAdapter, STTAdapter, AudioInspector
  adapters/
    mock_tts.py        # Deterministic mock: returns pre-made WAV bytes
    mock_stt.py        # Deterministic mock: returns fixed transcript + word timestamps
    edge_tts.py        # edge-tts adapter (Microsoft, free for personal use — verify)
    whisper_stt.py     # OpenAI Whisper (local model, MIT licence)
    audio_inspector.py # ffprobe-based: duration, sample rate, channels, codec
  pipeline.py          # Decides TTS/STT/combined path; returns NarrationResult
  validation.py        # Rejects empty, unsupported, silent, corrupted, music-only
```

**Input routing logic** (implemented in `pipeline.py`):

| Input | Action |
|---|---|
| Text only | Generate audio via TTS adapter |
| Audio only | Transcribe via STT adapter; extract word timestamps |
| Text + Audio | Use supplied audio; transcribe; compare with script; report mismatches |
| Empty script | Raise `ValidationError(EMPTY_SCRIPT)` |
| Unsupported format | Raise `ValidationError(UNSUPPORTED_AUDIO_FORMAT)` |
| Silent/music-only | Warn `SPEECH_NOT_DETECTED`; do not start render |
| Corrupted file | Raise `ValidationError(CORRUPTED_AUDIO)` |

**NarrationResult** (output of `pipeline.py`):
```python
@dataclass
class NarrationResult:
    audio_path: str          # path in MinIO
    transcript: str
    word_timestamps: list[WordTimestamp]
    duration_seconds: float
    tts_used: bool
    adapter_name: str        # e.g. "mock", "whisper", "edge_tts"
    warnings: list[str]
```

---

### 3.4 `src/sceneforge/planner/`

**Responsibility**: Turn narration + word timestamps into structured scene plans.

```
planner/
  interfaces.py        # Abstract PlannerAdapter
  adapters/
    rule_based.py      # Deterministic NLP-free planner (no LLM key required)
    llm_openai.py      # Optional GPT-4o adapter (behind feature flag)
  scene_planner.py     # Orchestrates segmentation → planning → schema validation
  segmenter.py         # Splits transcript into coherent scenes by pause/phrase/topic
  schema_validator.py  # Validates model output against ScenePlan JSON schema
  disambiguation.py    # Context-based term disambiguation rules
```

**ScenePlan** (output per scene):
```python
@dataclass
class ScenePlan:
    scene_id: str
    narration_text: str
    start_time: float
    end_time: float
    key_entities: list[str]
    intended_meaning: str
    visual_concept: str
    search_queries: list[str]
    suggested_visual_type: Literal["stock_footage","generated_image","typography_card","data_card"]
    negative_terms: list[str]
    safety_constraints: list[str]
    confidence: float
    preferred_source_route: str
    caption_text: str
```

**Rule-based planner strategy** (no LLM):
- Segment by sentence boundaries and pause gaps > 1.0 s.
- Extract nouns/verbs using a lightweight built-in tokeniser (no heavy NLP model).
- Apply a disambiguation rule table (e.g. `bank + financial/money → financial_bank`).
- Abstract concepts (trust, hope, freedom) → `typography_card`.
- Numeric/statistical claims → `data_card`.
- Concrete visual scenes → `stock_footage` with fallback to `generated_image`.
- Safety: named persons → `search_queries` exclude the name; add `negative_terms = [name]`.

---

### 3.5 `src/sceneforge/retrieval/`

**Responsibility**: Fetch, rank, and select media assets for each scene.

```
retrieval/
  interfaces.py           # Abstract: StockProvider, GeneratedProvider, EmbeddingModel
  adapters/
    mock_stock.py         # Returns deterministic fixture assets
    mock_generated.py     # Returns deterministic fixture still images
    pexels.py             # Pexels API adapter (free commercial licence)
    pixabay.py            # Pixabay API adapter (free commercial licence)
    sentence_transformer.py  # Local embedding model (all-MiniLM-L6-v2, Apache 2.0)
  searcher.py             # Multi-query search; deduplication; metadata validation
  ranker.py               # Cosine similarity scoring; duplicate penalty; score recording
  router.py               # Source routing policy (see §3.6)
```

**Retrieval pipeline per scene**:
1. Generate 2–4 search queries from `scene.search_queries`.
2. Query stock provider(s) with each query; collect up to 20 candidates.
3. Validate each candidate: metadata complete, licence known, commercial OK.
4. Embed visual concept and each candidate description using sentence-transformer.
5. Score candidates by cosine similarity; apply duplicate penalty (-0.1 per repeat).
6. Record all scores and reasons.
7. Pass top-N candidates to router with scores.

---

### 3.6 `src/sceneforge/retrieval/router.py`

**Responsibility**: Apply documented selection policy; record decision.

**Default policy** (configurable via `ROUTER_*` env vars):

```
Priority 1: Stock footage
  Condition: score >= ROUTER_STOCK_MIN_RELEVANCE (default 0.62)
             AND licence commercially verified
  
Priority 2: Generated visual (still + motion effect)
  Condition: stock unavailable or score < threshold
             AND score >= ROUTER_GENERATED_MIN_RELEVANCE (default 0.55)
             AND generated provider available
             AND licence commercially verified

Priority 3: Typography / Data card (programmatic)
  Condition: visual_type == typography_card OR data_card
             OR both external providers failed
  
Priority 4: Recorded failure
  Condition: none of above succeeded
  Action:    record RouteResult(route=FAILED, reason=...) in timeline
             do NOT crash pipeline; other scenes continue
```

**RouteResult** (stored in timeline per scene):
```python
@dataclass
class RouteResult:
    route: Literal["stock","generated","card","failed"]
    selected_asset_id: str | None
    candidate_scores: list[CandidateScore]
    reason: str
    fallback_attempts: list[str]
```

---

### 3.7 `src/sceneforge/rights/`

**Responsibility**: Create, validate, and persist rights records per asset.

```
rights/
  passport.py     # Creates RightsRecord from provider metadata
  validator.py    # Checks licence compatibility; rejects unverified
  serialiser.py   # Writes rights.json; links into manifest.json
```

**RightsRecord** (stored in DB and rights.json):
```python
@dataclass
class RightsRecord:
    asset_id: str
    provider_name: str
    source_url: str
    provider_asset_url: str
    licence_name: str
    licence_evidence_url: str
    commercial_use_eligible: bool
    attribution_required: bool
    attribution_text: str
    retrieval_timestamp: datetime
    sha256_hash: str
    asset_type: Literal["stock","generated","programmatic"]
    model_provenance: str | None
```

**Validation rules**:
- `commercial_use_eligible` must be `True` before asset is routed.
- `licence_name` must not be empty or "unknown".
- `sha256_hash` must be computed after download, not trusted from provider.
- Failed validation → asset excluded; fallback routing triggered.

---

### 3.8 `src/sceneforge/timeline/`

**Responsibility**: Assemble a deterministic, schema-valid timeline from scenes and routes.

```
timeline/
  builder.py       # Assembles TimelineEntry list from scenes + routes
  pacing.py        # Merges short scenes; aligns cuts to phrase boundaries
  serialiser.py    # Writes timeline.json; validates against schema
```

**Constraints**:
- Scene start ≥ 0; end > start.
- No gap between consecutive scenes (or documented gap with reason).
- Asset IDs not repeated unless `reuse_permitted = True`.
- Simple fade transitions between scenes (configurable).

---

### 3.9 `src/sceneforge/rendering/`

**Responsibility**: FFmpeg-based video assembly, subtitle burning, reframing.

```
rendering/
  renderer.py        # Builds and executes FFmpeg filter graph
  subtitle_writer.py # Generates captions.srt from scene captions + timings
  reframer.py        # Portrait crop: subject-aware or blurred-pad fallback
  normaliser.py      # Colour normalisation; pixel format standardisation
  cache.py           # Content-addressed segment cache
  ffprobe.py         # Thin wrapper around ffprobe JSON output
```

**Output defaults** (all configurable):
- Container: MP4
- Video codec: H.264 (libx264)
- Audio codec: AAC
- Frame rate: 30 fps
- Pixel format: yuv420p
- Landscape: 1920×1080 (16:9)
- Portrait: 1080×1920 (9:16)

**Incremental cache** (`cache.py`):
- Cache key = SHA-256 of (source_media_hash + trim_start + trim_end + aspect_ratio +
  caption_text + caption_style + render_params_hash + processing_version).
- Hit → symlink/copy from cache; log `CACHE_HIT`.
- Miss → render; store; log `CACHE_MISS`.
- Cache is isolated per job to prevent cross-user leakage.

**Reframing strategy** (portrait mode):
1. Attempt subject-aware crop using ffmpeg `cropdetect` or face-detection heuristic.
2. Fallback: scale source to fit width; pad top/bottom with blurred source frame.
3. Record strategy used in timeline entry.

---

### 3.10 `src/sceneforge/quality/`

**Responsibility**: Post-render automated quality assurance.

```
quality/
  checker.py        # Runs all QA checks; returns QAReport
  checks/
    codec_check.py
    frame_rate_check.py
    dimension_check.py
    duration_check.py
    audio_check.py
    subtitle_check.py
    black_frame_check.py
    frozen_frame_check.py
    audio_drift_check.py
    duplicate_scene_check.py
    rights_coverage_check.py
    artifact_download_check.py
```

**QAReport**:
```python
@dataclass
class QAReport:
    job_id: str
    overall: Literal["PASS","FAIL"]
    checks: list[QACheckResult]   # one per check above
    failed_scenes: list[str]
    recommendations: list[str]
```

**QACheckResult**:
```python
@dataclass
class QACheckResult:
    check_name: str
    status: Literal["PASS","FAIL","SKIPPED"]
    detail: str
    evidence: dict   # raw ffprobe output or computed values
```

**Recovery flow**:
- Scene-level failure → attempt scene replacement and re-render that segment.
- If replacement fails → mark scene as `FAILED` in timeline; continue with remaining scenes.
- If > 50% of scenes fail → mark entire job `FAILED`.

---

### 3.11 `src/sceneforge/storage/`

**Responsibility**: MinIO-compatible S3 object storage abstraction.

```
storage/
  client.py        # boto3-based MinIO client wrapper
  paths.py         # Canonical key naming: jobs/{job_id}/artifacts/{filename}
  presigned.py     # Generates time-limited presigned GET URLs
```

**Bucket layout**:
```
sceneforge-uploads/
  jobs/{job_id}/input/script.txt
  jobs/{job_id}/input/voiceover.{ext}

sceneforge-artifacts/
  jobs/{job_id}/output.mp4
  jobs/{job_id}/timeline.json
  jobs/{job_id}/manifest.json
  jobs/{job_id}/rights.json
  jobs/{job_id}/captions.srt
  jobs/{job_id}/metrics.json
  jobs/{job_id}/job.log

sceneforge-cache/
  segments/{cache_key}.mp4
```

---

### 3.12 `src/sceneforge/observability/`

**Responsibility**: Structured JSON logging, correlation ID propagation, metrics collection.

```
observability/
  logging.py       # structlog configuration; JSON formatter
  correlation.py   # Context var for correlation_id; propagated through workers
  metrics.py       # Runtime measurement; writes metrics.json
```

**Log line schema**:
```json
{
  "timestamp": "2026-10-19T10:00:00.000Z",
  "level": "info",
  "correlation_id": "req-uuid",
  "job_id": "job-uuid",
  "module": "sceneforge.rendering.renderer",
  "event": "scene_rendered",
  "scene_id": "scene-001",
  "duration_ms": 1234
}
```

---

## 4. Data Flow — Complete Pipeline

```
POST /jobs  ──►  Validate input  ──►  Enqueue job  ──►  Return job_id
                                                              │
                                                     Worker picks up job
                                                              │
                                                    ┌─── AudioStage ───┐
                                                    │  TTS or STT or   │
                                                    │  combined path   │
                                                    └──────┬───────────┘
                                                           │ NarrationResult
                                                    ┌──────▼───────────┐
                                                    │   PlannerStage   │
                                                    │  segment + plan  │
                                                    └──────┬───────────┘
                                                           │ list[ScenePlan]
                                                    ┌──────▼───────────┐
                                                    │  RetrievalStage  │
                                                    │  search + rank   │
                                                    └──────┬───────────┘
                                                           │ candidates
                                                    ┌──────▼───────────┐
                                                    │   RouterStage    │
                                                    │  select + rights │
                                                    └──────┬───────────┘
                                                           │ RouteResult[]
                                                    ┌──────▼───────────┐
                                                    │  TimelineStage   │
                                                    │  build + pace    │
                                                    └──────┬───────────┘
                                                           │ Timeline
                                                    ┌──────▼───────────┐
                                                    │  RenderStage     │
                                                    │  FFmpeg + SRT    │
                                                    └──────┬───────────┘
                                                           │ output.mp4
                                                    ┌──────▼───────────┐
                                                    │    QA Stage      │
                                                    │  ffprobe checks  │
                                                    └──────┬───────────┘
                                                           │ QAReport
                                                    ┌──────▼───────────┐
                                                    │ ArtifactStage    │
                                                    │ upload → MinIO   │
                                                    │ write manifests  │
                                                    └──────┬───────────┘
                                                           │
                                                    Job → COMPLETED
```

---

## 5. Database Schema (logical)

```sql
-- Jobs table
CREATE TABLE jobs (
    id          UUID PRIMARY KEY,
    idempotency_key VARCHAR(256) UNIQUE,
    idempotency_payload_hash VARCHAR(64),
    status      VARCHAR(32) NOT NULL DEFAULT 'QUEUED',
    error_code  VARCHAR(64),
    error_message TEXT,
    retryable   BOOLEAN,
    retry_count INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL,
    queued_at   TIMESTAMPTZ,
    started_at  TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    config      JSONB,
    correlation_id VARCHAR(64)
);

-- Scenes table
CREATE TABLE scenes (
    id          UUID PRIMARY KEY,
    job_id      UUID REFERENCES jobs(id),
    scene_index INTEGER,
    narration_text TEXT,
    start_time  FLOAT,
    end_time    FLOAT,
    visual_concept TEXT,
    route       VARCHAR(32),
    asset_id    VARCHAR(256),
    relevance_score FLOAT,
    status      VARCHAR(32),
    qa_status   VARCHAR(32),
    timeline_entry JSONB
);

-- Rights records table
CREATE TABLE rights_records (
    id              UUID PRIMARY KEY,
    job_id          UUID REFERENCES jobs(id),
    scene_id        UUID REFERENCES scenes(id),
    asset_id        VARCHAR(256),
    provider_name   VARCHAR(128),
    source_url      TEXT,
    licence_name    VARCHAR(256),
    commercial_use  BOOLEAN,
    attribution_required BOOLEAN,
    attribution_text TEXT,
    sha256_hash     VARCHAR(64),
    asset_type      VARCHAR(32),
    retrieved_at    TIMESTAMPTZ
);

-- Metrics table
CREATE TABLE metrics (
    id          UUID PRIMARY KEY,
    job_id      UUID REFERENCES jobs(id),
    total_duration_ms BIGINT,
    output_duration_s FLOAT,
    stage_timings JSONB,
    retry_count INTEGER,
    fallback_count INTEGER,
    qa_passed   BOOLEAN,
    recorded_at TIMESTAMPTZ
);
```

---

## 6. External Dependencies and Licence Review

| Dependency | Version Target | Licence | Use | Key Required |
|---|---|---|---|---|
| FastAPI | ≥0.111 | MIT | API framework | No |
| Pydantic | v2 | MIT | Validation | No |
| SQLAlchemy | 2.x | MIT | ORM | No |
| Alembic | latest | MIT | Migrations | No |
| Redis / redis-py | 5.x | MIT | Queue + idempotency | No |
| RQ | 1.x | BSD | Background jobs | No |
| boto3 | latest | Apache 2.0 | MinIO S3 | No |
| FFmpeg | 6.x | LGPL/GPL | Video processing | No (binary) |
| Whisper (openai-whisper) | latest | MIT | Local STT | No |
| edge-tts | latest | MIT (verify) | TTS | No |
| sentence-transformers | latest | Apache 2.0 | Embeddings | No |
| structlog | latest | Apache 2.0 | Logging | No |
| pytest | latest | MIT | Testing | No |
| Pexels API | — | Free commercial | Stock footage | Yes (free) |
| Pixabay API | — | Pixabay licence | Stock footage | Yes (free) |
| PostgreSQL | 15 | PostgreSQL | Database | No |
| MinIO | latest | AGPL-3.0 | Object storage | No |
| React | 18 | MIT | Frontend | No |
| Vite | 5.x | MIT | Frontend bundler | No |
| Tailwind CSS | 3.x | MIT | Styling | No |

**Notes**:
- FFmpeg binary is LGPL when built without GPL-only codecs. The H.264 (libx264) codec is GPL.
  The Dockerfile must build or source FFmpeg appropriately, or use a pre-built binary under
  an appropriate licence. This is a known constraint — document in SOURCES.md.
- edge-tts uses an unofficial Microsoft Edge TTS endpoint. Verify terms before production use.
  For the assessment, it works for demonstration. Mock adapter used in no-key tests.
- Whisper runs fully locally (MIT). No API key required. Requires ~150 MB model download.
- sentence-transformers `all-MiniLM-L6-v2` is Apache 2.0. Runs locally.

---

## 7. Security Design

| Concern | Mitigation |
|---|---|
| Path traversal | All file paths constructed from UUID job IDs; no user-supplied path components |
| Credential leakage | Secrets via environment variables only; `.env` in `.gitignore` |
| Stack traces | Global exception handler strips tracebacks before HTTP response |
| HMAC replay | Timestamp check: reject if `|now - ts| > 300 s` |
| HMAC timing attack | `hmac.compare_digest` used exclusively |
| Upload size | Configurable `MAX_UPLOAD_BYTES` enforced in middleware before parsing |
| File type validation | Magic-byte inspection (not extension) via ffprobe |
| Presigned URL scope | Presigned URLs scoped to single job artifacts; TTL ≤ 1 h |
| Concurrency isolation | Each job writes to `jobs/{job_id}/` namespace; no shared paths |
| No secrets in logs | structlog processor strips known secret key names |

---

## 8. Deployment Architecture (Docker Compose)

```
Services:
  api       — FastAPI on port 8000
  worker    — RQ worker (same image as api)
  db        — PostgreSQL 15
  redis     — Redis 7
  minio     — MinIO latest
  web       — Nginx serving Vite build, port 3000

Startup sequence:
  db + redis → api (runs alembic migrate) → worker → minio → web

Health checks:
  api:    GET /health → 200
  worker: RQ queue depth + worker heartbeat
  db:     pg_isready
  redis:  PING
  minio:  mc ready
```

---

## 9. Key Design Decisions and Rationale

| Decision | Rationale |
|---|---|
| Rule-based planner as primary | Ensures entire test suite runs without LLM API keys; LLM is optional enhancement |
| RQ over Celery | Simpler setup for assessment; Redis already required; sufficient concurrency |
| MinIO over local filesystem | Satisfies IS-04; enables presigned URLs; isolates jobs cleanly |
| sentence-transformers locally | No API key; Apache 2.0; sufficient for cosine ranking |
| Content-addressed render cache | Enables incremental re-render; avoids re-processing unchanged scenes |
| Pydantic v2 | FastAPI native; strict validation; schema export for OpenAPI |
| Whisper local STT | No API key; MIT licence; works offline; suitable for assessment |
| Typography/data cards | Handles abstract concepts and numeric claims without hallucinating imagery |
| SHA-256 hash in rights record | Proves file identity at retrieval time; independent of provider claims |
| Separate `rights.json` | Assessment requirement; makes provenance auditable without DB access |
