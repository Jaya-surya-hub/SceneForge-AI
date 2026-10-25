# SceneForge AI — Test Pack & Evidence Index

**Project**: SceneForge AI (IncuBrix 2027 SEA PS3)  
**Test Suite Status**: 500 passed, 0 failed in 3.90s  
**Integration Status**: All 10 Integration Standards verified  
**Hard-Case Coverage**: 24/24 hard cases implemented or tested  

---

## 1. Test Suite Summary

| Test Group | File Path | Tests Passed | Focus Areas |
|---|---|---|---|
| **Hard Cases: Worker Restart** | `tests/hard_cases/test_hc22_worker_restart.py` | 27 | Reconciler detection of stale jobs, state transition recovery, terminal state guards. |
| **Hard Cases: Interrupted Render** | `tests/hard_cases/test_hc23_interrupted_render.py` | 9 | Mid-render crash cleanup, atomic cache writes, placeholder failure detection in QA. |
| **Hard Cases: Concurrency Isolation** | `tests/hard_cases/test_is08_concurrent_isolation.py` | 4 | Thread-safety, artifact namespace isolation, cache partitioning, DB locking. |
| **API & Job Management** | `tests/integration/test_api_jobs.py` | 17 | `POST /jobs`, `POST /api/v1/jobs` (HTTP 202), Idempotency-Key (200 / 409), Correlation-ID. |
| **OpenAPI 3.1 Specification** | `tests/unit/test_openapi.py` | 4 | `openapi.yaml` format, OpenAPI 3.1.0 schema, `/api/v1/` routes coverage, 1:1 ratio. |
| **Audio Inspection & Probing** | `tests/unit/test_audio_inspector.py` | 14 | Sample rate, channels, codec parsing, duration extraction via ffprobe/mock. |
| **Audio Pipeline Processing** | `tests/unit/test_audio_pipeline.py` | 39 | Text-only, audio-only, combined text+audio, script/audio mismatch detection. |
| **Audio Validation & Limits** | `tests/unit/test_audio_validation.py` | 38 | Magic byte MIME sniffing, 10-minute max limit (`AudioDurationExceededError`), silence. |
| **Signed Callbacks (IS-02)** | `tests/unit/test_callbacks.py` | 12 | HMAC-SHA256, constant-time `compare_digest`, timestamp replay protection. |
| **Media Downloader** | `tests/unit/test_downloader.py` | 6 | HTTP range requests, chunked streaming, SHA-256 verification, network retry. |
| **Error Schema (IS-03)** | `tests/unit/test_error_schema.py` | 14 | Standard JSON error shape, uppercase snake_case codes, no stack traces. |
| **Mock Adapters** | `tests/unit/test_mock_adapters.py` | 31 | Deterministic offline mocks for TTS, STT, Stock, Generative, Embeddings, LLM. |
| **Scene Planner & Semantics** | `tests/unit/test_planner.py` | 33 | "Bank" & "cloud" disambiguation, named person protection, brand exclusion, cards. |
| **Rendering & Normalisation** | `tests/unit/test_rendering.py` | 69 | FFmpeg command builder, 16:9/9:16/1:1 reframing, loudnorm, 14 QA checks. |
| **Job Repository** | `tests/unit/test_repository.py` | 17 | SQLAlchemy ORM operations, scenes, rights records, idempotency storage. |
| **Retrieval & Rights Ranking** | `tests/unit/test_retrieval.py` | 71 | Tag overlap, semantic score, duplicate penalty, commercial licence verification. |
| **Transcript Segmentation** | `tests/unit/test_segmenter.py` | 23 | Sentence boundary detection, punctuation splitting, timestamp interpolation. |
| **Job State Machine** | `tests/unit/test_state_machine.py` | 38 | State transition graph, valid vs invalid transitions, timestamp tracking. |
| **Timeline Assembly** | `tests/unit/test_timeline.py` | 34 | Pacing calculation, SRT caption generation, timeline serialization. |
| **Total Test Count** | — | **500 passed (0 failed)** | Executed in 3.90s |

---

## 2. Hard-Case Test Matrix (HC-01 to HC-24)

| Hard Case ID | Scenario Description | Tested Behavior | Verification File |
|---|---|---|---|
| **HC-01** | Abstract narration ("Trust takes time.") | Routes to programmatic typography card; avoids hallucinated literal imagery. | `test_planner.py` |
| **HC-02** | Numeric statement with date ("Revenue grew 25% in 2024") | Generates data card with exact numbers from narration. | `test_planner.py` |
| **HC-03** | Ambiguous term "bank" (financial vs. river) | Semantic context disambiguation selects appropriate search query. | `test_planner.py` |
| **HC-04** | Ambiguous term "cloud" (computing vs. weather) | Distinguishes data server concepts from storm weather imagery. | `test_planner.py` |
| **HC-05** | Named person mention | Excludes individual names from video search; adds safety constraints. | `test_planner.py` |
| **HC-06** | Brand / product mention | Excludes commercial trademarks from queries to prevent false endorsement. | `test_planner.py` |
| **HC-07** | Sensitive topic / sad news | Formulates safe visual concept; avoids sensationalized footage. | `test_planner.py` |
| **HC-08** | Portrait video framing | Applies center-crop or blurred-pad reframing to adapt landscape clips. | `test_rendering.py` |
| **HC-09** | Silent audio input | Detects absence of speech; raises `SPEECH_NOT_DETECTED` (HTTP 422). | `test_audio_validation.py` |
| **HC-10** | Music-only audio | Identifies low speech harmonicity; issues `MUSIC_ONLY_SUSPECTED` advisory. | `test_audio_validation.py` |
| **HC-11** | Wrong / unsupported file type | Sniffs magic bytes; rejects non-audio with `UNSUPPORTED_AUDIO_FORMAT`. | `test_audio_validation.py` |
| **HC-12** | Empty script submission | Rejects blank text with `EMPTY_SCRIPT` (HTTP 422). | `test_audio_validation.py` |
| **HC-13** | Corrupted audio upload | Detects truncated header; raises `CORRUPTED_AUDIO` (HTTP 422). | `test_audio_validation.py` |
| **HC-14** | Stock provider timeout / 5xx | Gracefully catches timeout; falls back to secondary provider or card. | `test_retrieval.py` |
| **HC-15** | Generative visual provider failure | Deterministically falls back to programmatic cards with reason logged. | `test_retrieval.py` |
| **HC-16** | All external media sources down | Completes video using clean programmatic typography cards. | `test_retrieval.py` |
| **HC-17** | Duplicate assets across scenes | Applies penalty score to already-selected clips; QA check flags repeats. | `test_retrieval.py` |
| **HC-18** | Script and audio mismatch | Calculates word-level overlap; issues `SCRIPT_AUDIO_MISMATCH` warning. | `test_audio_pipeline.py` |
| **HC-19** | Invalid webhook signature | Constant-time HMAC comparison rejects forged requests with HTTP 401. | `test_callbacks.py` |
| **HC-20** | Repeated idempotency key | Returns existing job (HTTP 200) for same payload; HTTP 409 for conflict. | `test_api_jobs.py` |
| **HC-21** | Concurrent user isolation | Independent SQLite/Postgres transactions; isolated render directories. | `test_is08_concurrent_isolation.py` |
| **HC-22** | Worker restart recovery | Reconciler transitions orphaned active jobs to FAILED (retryable). | `test_hc22_worker_restart.py` |
| **HC-23** | Interrupted render recovery | Unconditional cleanup of temp dirs; incomplete output fails QA. | `test_hc23_interrupted_render.py` |
| **HC-24** | Rights rejection (non-commercial) | Excludes assets without verified commercial clearance. | `test_retrieval.py` |

---

## 3. Batch Runner Execution Evidence

Command executed:
```bash
python scripts/batch_runner.py --cases tests/fixtures/batch_cases.json --base-url http://localhost:8000 --output batch_report.json
```

Output:
```text
Running 5 test cases against http://localhost:8000
  [1/5] basic-text-only... PASS (COMPLETED, 5.18s)
  [2/5] abstract-concept... PASS (COMPLETED, 5.06s)
  [3/5] numeric-claim... PASS (COMPLETED, 5.03s)
  [4/5] portrait-mode... PASS (COMPLETED, 10.09s)
  [5/5] empty-script... PASS (FAILED, 0.0s)

Report written to batch_report.json
Passed: 5/5
Failed: 0/5
```
