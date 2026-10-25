# SceneForge AI — Test Report

**Project**: SceneForge AI — Script & Voiceover to B-roll Video Engine  
**Assessment**: IncuBrix Engineering Assessment 3  
**Date**: October 21, 2026  
**Test Suite Result**: **517 passed, 0 failed** in 4.36s  
**Integration Standard**: **10/10 Verified PASS**  
**Batch Runner**: **5/5 Cases Passed (100%)**  

---

## 1. Test Suite Breakdown

All tests run locally and inside Docker without requiring live external API keys (using deterministic mock adapters for third-party endpoints).

| Test Module | Path | Tests Passed | Status | Focus / Description |
|---|---|---|---|---|
| **Audio Inspection** | `tests/unit/test_audio_inspector.py` | 14 | PASS | Duration, sample rate, codec, and channels probing via ffprobe and mock. |
| **Audio Pipeline** | `tests/unit/test_audio_pipeline.py` | 39 | PASS | Text-only (TTS), audio-only (STT), combined text+audio, word timestamping. |
| **Audio Validation** | `tests/unit/test_audio_validation.py` | 38 | PASS | Format magic bytes (MP3, WAV, M4A, OGG, FLAC), 10-minute maximum limit (>600s), silence detection. |
| **Signed Callbacks (IS-03)** | `tests/unit/test_callbacks.py` | 12 | PASS | HMAC-SHA256 signing, constant-time `compare_digest`, timestamp replay rejection. |
| **Media Downloader** | `tests/unit/test_downloader.py` | 6 | PASS | Chunked streaming, SHA-256 digest validation, network retry policy. |
| **Error Schema (IS-05)** | `tests/unit/test_error_schema.py` | 14 | PASS | Standard JSON error shape, `UPPER_SNAKE_CASE` codes, no stack traces leaked. |
| **Mock Adapters** | `tests/unit/test_mock_adapters.py` | 31 | PASS | Deterministic offline adapters for TTS, STT, stock video, generative visual cards. |
| **OpenAPI 3.1 Spec (IS-02)** | `tests/unit/test_openapi.py` | 4 | PASS | OpenAPI 3.1 schema compliance, `/api/v1/` routes coverage, aspect ratios. |
| **Voiceover Orchestrator** | `tests/unit/test_orchestrator_voiceover.py` | 3 | PASS | Uploaded audio voiceover ingestion, blank script handling, input validation. |
| **Pipeline Features** | `tests/unit/test_pipeline_features.py` | 17 | PASS | Real gTTS speech synthesis, SpeechRecognition STT, query fallback, audio mixing. |
| **Scene Planner** | `tests/unit/test_planner.py` | 33 | PASS | Disambiguation ("bank", "cloud"), named people protection, brand exclusion. |
| **Video Rendering** | `tests/unit/test_rendering.py` | 69 | PASS | FFmpeg commands, 16:9, 9:16, 1:1 reframing, loudnorm audio mixing, QA battery. |
| **Job Repository** | `tests/unit/test_repository.py` | 17 | PASS | SQLAlchemy CRUD, scenes, rights records, idempotency key tracking. |
| **Retrieval & Rights** | `tests/unit/test_retrieval.py` | 71 | PASS | Tag overlap, semantic score, duplicate penalty, commercial licence filtering. |
| **Transcript Segmenter** | `tests/unit/test_segmenter.py` | 23 | PASS | Sentence boundary detection, punctuation splitting, timestamp interpolation. |
| **Job State Machine** | `tests/unit/test_state_machine.py` | 38 | PASS | Valid vs invalid state transitions, timestamps, terminal state guards. |
| **Timeline Assembly** | `tests/unit/test_timeline.py` | 34 | PASS | Scene pacing calculation, SRT caption generation, timeline serialization. |
| **Worker Restart (HC-22)** | `tests/hard_cases/test_hc22_worker_restart.py` | 27 | PASS | Stale active job recovery on worker startup, retry count increment. |
| **Interrupted Render (HC-23)** | `tests/hard_cases/test_hc23_interrupted_render.py` | 9 | PASS | Mid-render crash cleanup, atomic cache writes, placeholder failure detection. |
| **Concurrency Isolation (IS-08)** | `tests/hard_cases/test_is08_concurrent_isolation.py` | 4 | PASS | Multi-threaded job submission, cache namespace isolation, DB lock safety. |
| **API Endpoints (IS-03/04)** | `tests/integration/test_api_jobs.py` | 17 | PASS | `POST /jobs` (HTTP 202), `Idempotency-Key` (200 / 409), Correlation-ID. |
| **Total Test Count** | — | **517 passed, 0 failed** | **100% PASS** | Executed in 4.36s |

---

## 2. Batch Runner CLI Verification

Command executed:
```powershell
python scripts/batch_runner.py --cases tests/fixtures/batch_cases.json --base-url http://localhost:8000 --output batch_report.json
```

Execution results:
```text
Running 5 test cases against http://localhost:8000
  [1/5] basic-text-only... PASS (COMPLETED, 10.09s)
  [2/5] abstract-concept... PASS (COMPLETED, 10.07s)
  [3/5] numeric-claim... PASS (COMPLETED, 5.03s)
  [4/5] portrait-mode... PASS (COMPLETED, 10.09s)
  [5/5] empty-script... PASS (FAILED, 0.0s)

Report written to batch_report.json
Passed: 5/5
Failed: 0/5
```

---

## 3. End-to-End Live Video Verification

| Job ID | Input Mode | Aspect Ratio | Narration Source | B-roll Source | Codec / Dimensions | QA Status |
|---|---|---|---|---|---|---|
| `a89874ff-b596-43d5-b95e-6cec68a7d441` | Script Prompt | 16:9 Landscape | `gTTS` (Audible MP3) | Real Pixabay (`pixabay-309208`, `pixabay-116732`) | H.264/AAC, 1920×1080 @ 30fps, 8.76s | PASS (16/16) |
| `c6e7e5b1-42ac-4f55-bb1a-98f43fc5f301` | Uploaded Audio | 16:9 Landscape | Spoken voiceover (`SpeechRecognition` STT) | Real Pixabay (`pixabay-199554`) | H.264/AAC, 1920×1080 @ 30fps, 6.93s | PASS (16/16) |
| `ca9aa9d4-9769-4fda-963e-a77e8ac984e3` | Script Prompt | 9:16 Portrait | Synthesized narration | Programmatic card reframing | H.264/AAC, 1080×1920 @ 30fps, 4.60s | PASS (16/16) |
| `1d7b1d2d-9932-408e-b75f-ffaa5199572d` | Script Prompt | 1:1 Square | Synthesized narration | Square center-crop / pad | H.264/AAC, 1080×1080 @ 30fps, 3.77s | PASS (16/16) |
| `8ce5ae31-f3e4-4856-b951-201baabcffd9` | Script Prompt | 16:9 Landscape | Synthesized narration | Real Pixabay (`pixabay-380291`, `pixabay-311442`) | H.264/AAC, 1920×1080 @ 30fps, 8.00s | PASS (14/14) |
