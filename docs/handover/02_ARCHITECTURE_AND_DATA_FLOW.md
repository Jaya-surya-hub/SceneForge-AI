# Architecture & Data Flow

---

## High-Level Pipeline

```
Script Input
    ↓
[Audio Pipeline]  ← TTS (real or mock)
    ↓
[Scene Planner]   ← Extract visual concepts
    ↓
[Media Retrieval] ← Search + rank candidates
    ↓
[Source Router]   ← Deterministic selection
    ↓
[Rights Passport] ← Validate licences
    ↓
[Timeline Builder] ← Construct schedule
    ↓
[FFmpeg Renderer] ← Encode video
    ↓
[QA Module]       ← Validate output
    ↓
[Artifact Storage] ← Store all 7 files
    ↓
Job Complete
```

---

## Core Components

### 1. API Layer (FastAPI)

**File:** `src/sceneforge/api/`

- POST `/jobs` — Create job (with idempotency)
- GET `/jobs/{id}` — Job status
- GET `/jobs/{id}/artifacts` — List artifacts
- GET `/files/{bucket}/{path}` — Download artifact
- POST `/jobs/{id}/cancel` — Cancel job
- GET `/health` — Liveness
- GET `/ready` — Readiness

**Responsibilities:**
- Request validation (Pydantic)
- Job creation (generate UUID, store in DB)
- Callback webhooks (optional)
- Idempotency key tracking
- CORS and security headers

---

### 2. Job Orchestration (RQ + PostgreSQL)

**File:** `src/sceneforge/jobs/`

**State Machine:**
```
PENDING → QUEUED → VALIDATING → PLANNING → RETRIEVING → RENDERING → QA → COMPLETED
                        ↓
                    FAILED (at any stage)
```

**Database Models:**
- `Job` — Metadata, status, timestamps
- `Scene` — Per-scene data (narration, visual, asset)
- `RightsRecord` — Licence tracking

**Job Repository:** CRUD + state transitions

---

### 3. Audio Pipeline

**File:** `src/sceneforge/audio/`

**Flow:**
```
Script Text
    ↓
[TTS Adapter] → audio_bytes (MP3)
    ↓
[Validation] → Check duration, sample rate
    ↓
[Storage] → Save to temp file
    ↓
[Return] → narration object
```

**Adapters:**
- `mock_tts` — Silent WAV (always works)
- `edge_tts` — Azure TTS (requires network)
- `host_tts` — Pre-generated MP3 (requires TTS_PRE_GENERATED_PATH)

---

### 4. Scene Planning (Rule-Based)

**File:** `src/sceneforge/planner/`

**Flow:**
```
Narration Script
    ↓
[Segmenter] → Split into sentences
    ↓
[Concept Extractor] → Extract visual concepts
    ↓
[Visual Route Suggester] → Suggest asset type
    ↓
[Scenes] → List of scene objects
```

**Routes:**
- `stock_footage` — Real video (if available)
- `generated_visual` — AI/procedural (not implemented)
- `typography_card` — Colored cards with text
- `recorded_failure` — Placeholder, logged

---

### 5. Media Retrieval & Ranking

**File:** `src/sceneforge/retrieval/`

**Flow:**
```
Scene (concept, visual route)
    ↓
[Provider Adapter] → Search candidates
    ↓
[Ranker] → Score relevance
    ↓
[Router] → Apply deterministic routing policy
    ↓
[Selected Asset]
```

**Providers:**
- `mock` — Returns mock assets
- `pexels` — Real Pexels API (requires key)
- `pixabay` — Real Pixabay API (requires key)

**Routing Policy:**
1. If route == `stock_footage`: search Pexels → Pixabay → fallback to card
2. If route == `generated_visual`: fallback to card (not implemented)
3. If route == `typography_card`: generate card immediately
4. If route == `recorded_failure`: log error, use card

---

### 6. Rights Passport

**File:** `src/sceneforge/rights/`

**Each Asset Has:**
- `provider_name` (e.g., "pexels", "sceneforge_internal")
- `licence_name` (e.g., "CC0", "SceneForge Internal")
- `commercial_use_eligible` (bool)
- `source_url`, `provider_asset_url`
- `sha256_hash`
- `retrieved_at` timestamp

**Policy:** No asset enters final video without a verified record.

---

### 7. Timeline & Subtitles

**File:** `src/sceneforge/timeline/`

**Timeline Entry:**
- `start_time` (seconds)
- `end_time` (seconds)
- `narration_text`
- `scene_id`
- `asset_id`
- `caption_text`

**SRT Generation:** Build from timeline entries with proper timecoding.

---

### 8. FFmpeg Rendering

**File:** `src/sceneforge/rendering/`

**Pipeline:**
```
Timeline + Assets
    ↓
[Card Generator] → Create individual card MP4s
    ↓
[Normalizer] → Ensure consistent format
    ↓
[Cache] → Content-addressed storage
    ↓
[Reframer] → Adjust aspect ratio if needed
    ↓
[Subtitle Writer] → Burn captions (optional)
    ↓
[FFmpeg Muxer] → Concatenate + encode
    ↓
output.mp4
```

**Codecs:** H.264 video, AAC audio, 30 FPS

---

### 9. Quality Assurance

**File:** `src/sceneforge/quality/`

**14 Checks:**
1. file_exists
2. file_nonempty
3. ffprobe_available
4. container (expected mp4)
5. video_codec (expected h264)
6. audio_codec (expected aac)
7. frame_rate (expected 30)
8. dimensions (expected 1920×1080)
9. duration (> 0.5s)
10. audio_present (if required)
11. pixel_format (yuv420p)
12. subtitles (valid SRT)
13. rights_coverage (asset tracked)
14. duplicate_scenes (no repeated clips)

**Results:** PASS / SKIP / FAIL

---

### 10. Storage

**File:** `src/sceneforge/storage/`

**Backends:**
- `FilesystemStorageClient` — Local disk (current)
- `MinIOStorageClient` — S3-compatible (blocked)

**Buckets:**
- `sceneforge-uploads` — User uploads
- `sceneforge-artifacts` — Job outputs
- `sceneforge-cache` — Rendering cache

**Artifacts Stored:**
1. output.mp4
2. timeline.json
3. rights.json
4. captions.srt
5. manifest.json
6. metrics.json
7. job.log

---

## Docker Services

| Service | Image | Purpose | Ports |
|---|---|---|---|
| `db` | postgres:15 | Job/scene/rights data | 5432 |
| `redis` | redis:7 | Job queue + cache | 6379 |
| `api` | Dockerfile (runtime) | FastAPI server | 8000 |
| `worker` | Dockerfile (runtime) | RQ job processor | — |
| `minio` | (optional) | S3-compatible storage | 9090 |

**Current Setup:** Filesystem backend (MinIO not used due to Docker Hub 403)

---

## Environment & Configuration

**Critical Env Vars:**
- `DATABASE_URL` — PostgreSQL connection
- `REDIS_URL` — Redis connection
- `STORAGE_BACKEND` — filesystem or s3
- `STORAGE_ROOT` — Filesystem storage directory
- `TTS_ADAPTER` — mock, edge_tts, or host_tts
- `TTS_PRE_GENERATED_PATH` — For host_tts
- `CALLBACK_HMAC_SECRET` — Webhook security
- `LOG_FORMAT` — console or json

---

## Error Handling & Fallback

**TTS Failure:** Falls back to mock (silent narration)
**Stock Footage Failure:** Falls back to programmatic card
**Rendering Failure:** Job marked FAILED; error logged
**QA Failure:** Still completes; QA status recorded

---

**Prepared by:** Kiro AI  
**Last Updated:** 2026-10-20
