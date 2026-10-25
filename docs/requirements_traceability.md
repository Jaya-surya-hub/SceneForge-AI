# Requirements Traceability Matrix
## SceneForge AI — IncuBrix SEA PS3

> **PROVISIONAL NOTICE**: No official assessment brief PDF was found in the workspace at session start.
> This matrix is derived from the requirements supplied in the project prompt (sections 1–14).
> Before asserting full compliance, the official brief must be reviewed and this document updated
> to match its exact wording. Any discrepancy between this matrix and the official brief must be
> recorded as a gap and resolved before submission.
>
> **Last Updated**: Phase 1 (initial planning)
> **Deadline**: October 25, 2026 — 11:59 PM IST

---

## Legend

| Status | Meaning |
|---|---|
| `NOT_STARTED` | No implementation exists |
| `IN_PROGRESS` | Implementation under way but not validated |
| `PASS` | Test or valid evidence demonstrates requirement is met |
| `FAIL` | Test ran and failed |
| `BLOCKED` | Cannot proceed without external resource / clarification |

---

## Part A — Eight Must-Have Requirements

> Extracted from prompt Section 6 (Integration Standard) cross-referenced with Section 1 (Product Vision) and Section 13 (Definition of Done). The eight core must-haves are the functional pillars of the pipeline.

---

### MH-01 — End-to-end video generation from script and/or voiceover

| Field | Value |
|---|---|
| **Requirement ID** | MH-01 |
| **Original Wording** | "At least one end-to-end job produces a real, validated MP4 using the configured pipeline." (§13 gate 4) |
| **Implementation Module** | `src/sceneforge/jobs/`, `src/sceneforge/rendering/`, `src/sceneforge/api/` |
| **Acceptance Criteria** | A POST to `/jobs` with a valid script or audio file completes with status `COMPLETED`; `output.mp4` exists, is a valid H.264/AAC MP4, has positive duration, matches timeline duration within tolerance |
| **Test File** | `tests/unit/test_rendering.py`, `docs/e2e_milestone.md` |
| **Test Case** | `test_render_complete_with_mocked_ffmpeg` (mock); real MP4 requires Docker |
| **Evidence Location** | `docs/e2e_milestone.md`, live Docker job `5040480d-db1d-4502-9428-edc25049c239` |
| **Status** | `PASS` — Fully verified. Docker E2E job `5040480d-db1d-4502-9428-edc25049c239` completed through full pipeline: retrieved stock video assets via MediaDownloader, rendered 3 moving footage segments with FFmpeg, mixed synchronized audio and captions, and passed all 14 QA checks (`qa_overall: PASS`). Output MP4 is 7.34 MB, 1920x1080@30fps H.264/AAC. |

---

### MH-02 — Meaning-aware scene planning (not keyword matching)

| Field | Value |
|---|---|
| **Requirement ID** | MH-02 |
| **Original Wording** | "The application must understand the meaning of each narration segment rather than selecting footage using simple keyword matching alone." (§1) |
| **Implementation Module** | `src/sceneforge/planner/adapters/rule_based.py`, `src/sceneforge/planner/disambiguation.py`, `src/sceneforge/planner/segmenter.py` |
| **Acceptance Criteria** | Planner produces structured scene objects with `intended_meaning`, `visual_concept`, `key_entities`, `search_queries`, and `suggested_visual_type`; disambiguates "bank" (financial vs. river) and "cloud" (computing vs. weather) in test inputs; rule-based planner works without LLM key |
| **Test File** | `tests/unit/test_planner.py` |
| **Test Case** | `test_bank_disambiguation` (HC-03), `test_cloud_disambiguation` (HC-04), `test_trust_takes_time_is_typography` (HC-01), `test_percentage_is_data_card` (HC-02), `test_named_person_excluded_from_search` (HC-05), plus 28 more |
| **Evidence Location** | `tests/unit/evidence/phase3_test_run.txt` |
| **Status** | `IN_PROGRESS` — Rule-based planner implemented; 33 planner tests PASS including HC-01 to HC-07; LLM enhancement deferred to advanced features |

---

### MH-03 — Semantic media retrieval with rights provenance

| Field | Value |
|---|---|
| **Requirement ID** | MH-03 |
| **Original Wording** | "Search permitted media sources and rank candidate clips semantically… Rights provenance is present for every external asset." (§1 steps 9–11; §13 gate 5) |
| **Implementation Module** | `src/sceneforge/retrieval/` (searcher, ranker, router, factory), `src/sceneforge/rights/` (passport, validator, serialiser) |
| **Acceptance Criteria** | Every selected asset has a corresponding entry in `rights.json`; entry contains asset ID, provider, licence name, commercial-use eligibility, attribution text, SHA-256 hash, retrieval timestamp; assets with unknown/incompatible licence are excluded |
| **Test File** | `tests/unit/test_retrieval.py` |
| **Test Case** | `test_create_rights_record_basic`, `test_sha256_computed_when_bytes_provided`, `test_missing_licence_raises_when_required`, `test_non_commercial_always_raises`, plus 68 more |
| **Evidence Location** | `tests/unit/evidence/phase4_test_run.txt` |
| **Status** | `IN_PROGRESS` — Retrieval stack implemented (searcher, ranker, router, rights); 71 Phase 4 tests PASS; live provider tests deferred (require API keys) |

---

### MH-04 — Deterministic source routing with documented policy

| Field | Value |
|---|---|
| **Requirement ID** | MH-04 |
| **Original Wording** | "Implement a configurable router with a documented selection policy… Record the selected route, candidates, scores, reason and fallback attempts in the timeline." (§4.5) |
| **Implementation Module** | `src/sceneforge/retrieval/router.py` |
| **Acceptance Criteria** | Router follows priority: stock → generated visual → typography/data card → recorded failure; selection reason and fallback chain are present in `timeline.json` for every scene; thresholds are configurable via environment/config; stock-provider outage does not crash system |
| **Test File** | `tests/unit/test_retrieval.py::TestSourceRouter` |
| **Test Case** | `test_stock_selected_above_threshold`, `test_stock_not_selected_below_threshold`, `test_card_scenes_route_directly`, `test_fallback_to_card_when_no_stock_no_generated`, `test_fallback_attempts_recorded`, plus 6 more |
| **Evidence Location** | `tests/unit/evidence/phase4_test_run.txt` |
| **Status** | `IN_PROGRESS` — Router implemented with configurable thresholds; 11 router tests PASS; timeline integration in orchestrator |

---

### MH-05 — Automated quality assurance after rendering

| Field | Value |
|---|---|
| **Requirement ID** | MH-05 |
| **Original Wording** | "After rendering, validate: output exists and can be opened… codec and container match… frame rate and dimensions are correct… audio present when required… subtitle timings valid… no unintended black or frozen frames… audio drift within tolerance… duplicate scenes flagged… rights records exist for all external media." (§4.9) |
| **Implementation Module** | `src/sceneforge/quality/checker.py` |
| **Acceptance Criteria** | QA module runs all listed checks via ffprobe; reports each check as pass/fail; failed check triggers scene-level retry or marks job FAILED with diagnostic; QA result reflected in `metrics.json` and `manifest.json`; no check silently skipped |
| **Test File** | `tests/unit/test_rendering.py::TestQAChecker` |
| **Test Case** | `test_check_video_codec_fail_wrong_codec`, `test_check_dimensions_fail_wrong_size`, `test_check_duration_fail_zero`, `test_check_audio_present_fail_when_required`, `test_check_duplicate_scenes_fail_on_repeat`, `test_ffprobe_unavailable_gives_unknown`, `test_overall_pass_with_mocked_probe`, plus 8 more |
| **Evidence Location** | `tests/unit/evidence/phase5_test_run.txt` |
| **Status** | `IN_PROGRESS` — QAChecker with 14 checks implemented; 21 QA tests pass. Checks use PASS/FAIL/UNKNOWN outcomes. ffprobe required for media checks; returns UNKNOWN (not PASS) when unavailable. |

---

### MH-06 — Required output contract (all seven artifacts)

| Field | Value |
|---|---|
| **Requirement ID** | MH-06 |
| **Original Wording** | "Every successful job must produce: output.mp4, timeline.json, manifest.json, rights.json, captions.srt, metrics.json, job.log" (§5) |
| **Implementation Module** | `src/sceneforge/jobs/`, `src/sceneforge/rendering/`, `src/sceneforge/quality/`, `src/sceneforge/storage/` |
| **Acceptance Criteria** | All seven artifacts present in object storage after job COMPLETED; each validates against its JSON schema; SRT captions are parseable and timecodes are valid; job.log contains structured JSON entries with correlation ID |
| **Test File** | `tests/unit/test_rendering.py`, `tests/unit/test_timeline.py` |
| **Test Case** | `test_basic_srt_generation`, `test_validate_srt_valid`, `test_rights_to_dict_has_records`, `test_full_pipeline_text_to_timeline` |
| **Evidence Location** | `tests/unit/evidence/phase5_test_run.txt` |
| **Status** | `IN_PROGRESS` — All 7 artifacts produced by orchestrator and uploaded to MinIO. captions.srt validated (SRT writer + validator). timeline.json and rights.json validated against JSON schema. Real ffprobe validation of output.mp4 requires Docker. |

---

### MH-07 — Background job processing with state machine

| Field | Value |
|---|---|
| **Requirement ID** | MH-07 |
| **Original Wording** | "Use background processing for long-running operations. Persist job states: QUEUED, VALIDATING, PLANNING, RETRIEVING, RENDERING, QA, COMPLETED, FAILED, CANCELLED. Use a state machine with valid transitions, timestamps, useful error codes and retry metadata." (§4.1) |
| **Implementation Module** | `src/sceneforge/jobs/state_machine.py`, `src/sceneforge/jobs/worker.py` |
| **Acceptance Criteria** | Invalid transitions raise an error and are not persisted; all state changes are timestamped; FAILED jobs carry error code and retryable flag; job survives worker restart (Redis/DB persistence); concurrent jobs do not corrupt each other |
| **Test File** | `tests/unit/test_state_machine.py`, `tests/unit/test_repository.py` |
| **Test Case** | `test_invalid_transition_rejected`, `test_timestamps_recorded_per_transition`, 38 state machine tests, 17 repository tests |
| **Evidence Location** | `tests/unit/evidence/phase2_test_run.txt` |
| **Status** | `IN_PROGRESS` — State machine (38 tests PASS) and repository (17 tests PASS) implemented; worker restart resilience test requires running RQ (Phase 6) |

---

### MH-08 — Complete test suite running without external API keys

| Field | Value |
|---|---|
| **Requirement ID** | MH-08 |
| **Original Wording** | "A complete test suite that runs without external API keys." (§6 item 8) |
| **Implementation Module** | `tests/`, `src/sceneforge/audio/adapters/mock.py`, `src/sceneforge/retrieval/adapters/mock.py`, `src/sceneforge/planner/adapters/mock.py` |
| **Acceptance Criteria** | `pytest tests/` completes with 0 failures when no external API keys are set; all provider interfaces have deterministic mock implementations; mocks are clearly labelled and do not claim real generation or transcription |
| **Test File** | All test files |
| **Test Case** | All 307 tests in the no-key suite (Phase 3 baseline) |
| **Evidence Location** | `tests/unit/evidence/phase3_test_run.txt` |
| **Status** | `IN_PROGRESS` — 307/307 tests pass with no external keys; count grows in Phases 4-6 |

---

## Part B — Ten Integration Standard Requirements

---

### IS-01 — Idempotent job creation

| Field | Value |
|---|---|
| **Requirement ID** | IS-01 |
| **Original Wording** | "Idempotent job creation." (§6 item 1); "Repeated job-creation requests using the same idempotency key and equivalent payload must not create duplicate jobs." (§4.1) |
| **Implementation Module** | `src/sceneforge/api/routes/jobs.py`, `src/sceneforge/jobs/repository.py` |
| **Acceptance Criteria** | POST `/jobs` with identical `Idempotency-Key` header and payload returns the same job ID and HTTP 200 (not 201) on repeat; a second request with the same key but different payload returns 409; DB contains exactly one job record per key |
| **Test File** | `tests/integration/test_api_jobs.py` |
| **Test Case** | `test_same_key_returns_same_job`, `test_same_key_different_payload_returns_409`, `test_different_keys_create_different_jobs` |
| **Evidence Location** | `tests/unit/evidence/phase2_test_run.txt` |
| **Status** | `IN_PROGRESS` — Logic implemented and tested in mock mode; full DB persistence test requires PostgreSQL (Phase 6) |

---

### IS-02 — HMAC-SHA256 signed callbacks

| Field | Value |
|---|---|
| **Requirement ID** | IS-02 |
| **Original Wording** | "HMAC-SHA256-signed callbacks, with timestamp validation and constant-time signature verification." (§6 item 2) |
| **Implementation Module** | `src/sceneforge/api/callbacks.py` |
| **Acceptance Criteria** | Outbound callbacks include `X-SceneForge-Signature` (HMAC-SHA256) and `X-SceneForge-Timestamp` headers; inbound callback verification uses `hmac.compare_digest`; replayed requests with timestamp > tolerance are rejected; requests with wrong signature are rejected with 401 |
| **Test File** | `tests/unit/test_callbacks.py` |
| **Test Case** | `test_valid_signature_accepted`, `test_invalid_signature_rejected_401`, `test_replayed_timestamp_rejected`, `test_missing_signature_rejected`, `test_missing_timestamp_rejected`, `test_malformed_timestamp_rejected` |
| **Evidence Location** | `tests/unit/evidence/phase2_test_run.txt` |
| **Status** | `IN_PROGRESS` — Sign/verify logic implemented and 12 tests pass; outbound webhook dispatch requires live job execution (Phase 5) |

---

### IS-03 — Consistent error response schema

| Field | Value |
|---|---|
| **Requirement ID** | IS-03 |
| **Original Wording** | "A consistent error response schema with machine-readable code, message, retryability and correlation ID." (§6 item 3) |
| **Implementation Module** | `src/sceneforge/api/errors.py`, `src/sceneforge/schemas/errors.py` |
| **Acceptance Criteria** | All 4xx and 5xx responses include `{"error": {"code": "...", "message": "...", "retryable": bool, "correlation_id": "...", "details": {}}}` ; no stack traces in responses; schema matches OpenAPI definition; codes are machine-readable uppercase strings |
| **Test File** | `tests/unit/test_error_schema.py` |
| **Test Case** | `test_make_error_response_structure`, `test_model_dump_has_error_key`, `test_not_found_returns_error_shape`, `test_validation_error_returns_error_shape`, `test_no_stack_trace_in_error_response`, `test_all_sceneforge_errors_have_required_attrs` |
| **Evidence Location** | `tests/unit/evidence/phase2_test_run.txt` |
| **Status** | `IN_PROGRESS` — Schema and handlers implemented; 14 tests pass; OpenAPI export pending (Phase 6) |

---

### IS-04 — MinIO-compatible object storage

| Field | Value |
|---|---|
| **Requirement ID** | IS-04 |
| **Original Wording** | "MinIO-compatible object storage." (§6 item 4) |
| **Implementation Module** | `src/sceneforge/storage/`, `docker-compose.yml` |
| **Acceptance Criteria** | All uploads and generated artifacts are stored and retrieved via MinIO S3-compatible API; presigned download URLs work; artifacts are isolated per job/user; no artifact leaks between jobs |
| **Test File** | `tests/integration/test_storage.py` |
| **Test Case** | `test_upload_and_retrieve_artifact`, `test_presigned_url_works`, `test_artifact_isolation_between_jobs` |
| **Evidence Location** | `tests/integration/evidence/storage/` |
| **Status** | `NOT_STARTED` |

---

### IS-05 — Structured logs with job IDs and correlation IDs

| Field | Value |
|---|---|
| **Requirement ID** | IS-05 |
| **Original Wording** | "Structured logs with job IDs and correlation IDs." (§6 item 5) |
| **Implementation Module** | `src/sceneforge/observability/` |
| **Acceptance Criteria** | Every log line is valid JSON; contains `job_id`, `correlation_id`, `timestamp`, `level`, `module`, `message`; log output matches entries in `job.log` artifact; no sensitive data (keys, tokens) in logs |
| **Test File** | `tests/unit/test_logging.py` |
| **Test Case** | `test_log_line_is_valid_json`, `test_log_contains_job_id`, `test_log_contains_correlation_id`, `test_no_secrets_in_logs` |
| **Evidence Location** | `tests/unit/evidence/logging/` |
| **Status** | `NOT_STARTED` |

---

### IS-06 — Batch-runner CLI

| Field | Value |
|---|---|
| **Requirement ID** | IS-06 |
| **Original Wording** | "A batch-runner CLI for repeatable test cases." (§6 item 6) |
| **Implementation Module** | `scripts/batch_runner.py` |
| **Acceptance Criteria** | CLI accepts a YAML/JSON test-case file; submits jobs to API; polls for completion; downloads artifacts; compares against expected outcomes; produces a reproducible report in JSON and human-readable text; exits non-zero on any failure |
| **Test File** | `tests/integration/test_batch_runner.py` |
| **Test Case** | `test_batch_runner_produces_report`, `test_batch_runner_exits_nonzero_on_failure` |
| **Evidence Location** | `tests/integration/evidence/batch/` |
| **Status** | `NOT_STARTED` |

---

### IS-07 — Mock adapters for every external provider interface

| Field | Value |
|---|---|
| **Requirement ID** | IS-07 |
| **Original Wording** | "Mock adapters for every external provider interface." (§6 item 7) |
| **Implementation Module** | `src/sceneforge/audio/adapters/mock_tts.py`, `src/sceneforge/audio/adapters/mock_stt.py`, `src/sceneforge/retrieval/adapters/mock_stock.py`, `src/sceneforge/retrieval/adapters/mock_generated.py`, `src/sceneforge/retrieval/adapters/mock_embeddings.py`, `src/sceneforge/planner/adapters/mock_llm.py` |
| **Acceptance Criteria** | Every adapter interface has a mock implementation; mocks are deterministic and configurable; mocks clearly identify themselves in logs/output as mock; no mock claims to have performed real generation or transcription |
| **Test File** | `tests/unit/test_mock_adapters.py` |
| **Test Case** | 31 mock adapter tests covering TTS, STT, stock, generated, embeddings, LLM planner |
| **Evidence Location** | `tests/unit/evidence/phase2_test_run.txt` |
| **Status** | `IN_PROGRESS` — All 6 mock adapters implemented; 31 tests PASS; real adapter implementations deferred to Phase 3 |

---

### IS-08 — Background job resilience, retries, and concurrency isolation

| Field | Value |
|---|---|
| **Requirement ID** | IS-08 |
| **Original Wording** | "Background job resilience, retries, provider failure handling and concurrency isolation." (§6 item 9) |
| **Implementation Module** | `src/sceneforge/jobs/worker.py`, `src/sceneforge/jobs/retry.py`, `src/sceneforge/jobs/reconciler.py` |
| **Acceptance Criteria** | Transient provider failures trigger retry with backoff up to configured limit; permanent failures mark job FAILED with error code; two simultaneous jobs cannot overwrite each other's inputs or outputs; worker restart does not lose an in-progress job |
| **Test File** | `tests/hard_cases/test_is08_concurrent_isolation.py`, `tests/hard_cases/test_hc22_worker_restart.py` |
| **Test Case** | `test_artifact_keys_are_strictly_isolated`, `test_render_cache_directory_isolation`, `test_concurrent_job_creation_and_isolation`, `test_concurrent_pipeline_runs_do_not_leak_state` |
| **Evidence Location** | `tests/hard_cases/` |
| **Status** | `VERIFIED` — Concurrency isolation, artifact path namespacing, render cache partitioning, and worker recovery reconciler implemented and passing 100% of tests. |

---

### IS-09 — Accurate OpenAPI documentation

| Field | Value |
|---|---|
| **Requirement ID** | IS-09 |
| **Original Wording** | "Accurate OpenAPI documentation and a reproducible Docker Compose setup." (§6 item 10) |
| **Implementation Module** | `openapi.yaml`, `src/sceneforge/api/` |
| **Acceptance Criteria** | `openapi.yaml` validates against OpenAPI 3.1 spec; every implemented endpoint is documented; request/response schemas match Pydantic models; error shapes match IS-03; FastAPI auto-generated docs agree with `openapi.yaml` |
| **Test File** | `tests/unit/test_openapi.py` |
| **Test Case** | `test_openapi_validates`, `test_all_endpoints_documented`, `test_schemas_match_pydantic_models` |
| **Evidence Location** | `tests/unit/evidence/openapi/` |
| **Status** | `NOT_STARTED` |

---

### IS-10 — Reproducible Docker Compose setup

| Field | Value |
|---|---|
| **Requirement ID** | IS-10 |
| **Original Wording** | "Accurate OpenAPI documentation and a reproducible Docker Compose setup." (§6 item 10) |
| **Implementation Module** | `docker-compose.yml`, `Dockerfile` |
| **Acceptance Criteria** | `docker compose up --build` from a clean checkout starts API, worker, PostgreSQL, Redis, MinIO, and web app; health checks pass; database migrations run automatically; API is reachable at `http://localhost:8000`; web app at `http://localhost:3000` |
| **Test File** | `tests/integration/test_docker_compose.py` (smoke test) |
| **Test Case** | `test_api_health_check_returns_200`, `test_worker_ready`, `test_minio_reachable` |
| **Evidence Location** | `tests/integration/evidence/docker/` |
| **Status** | `NOT_STARTED` |

---

## Part C — Hard-Case Test Coverage

> Each hard-case maps to a test in `tests/hard_cases/`. Status begins NOT_STARTED.

| HC-ID | Scenario | Test File | Status |
|---|---|---|---|
| HC-01 | Abstract narration: "Trust takes time." | `test_planner.py::TestAbstractNarration` | `IN_PROGRESS` — typography_card produced; 6 tests pass |
| HC-02 | Numeric statement with date | `test_planner.py::TestNumericStatements` | `IN_PROGRESS` — data_card produced; 6 tests pass |
| HC-03 | Ambiguous term: "bank" | `test_planner.py::TestBankDisambiguation` | `IN_PROGRESS` — financial vs. river disambiguation works |
| HC-04 | Ambiguous term: "cloud" | `test_planner.py::TestCloudDisambiguation` | `IN_PROGRESS` — computing vs. weather disambiguation works |
| HC-05 | Named person reference | `test_planner.py::TestNamedPersonHandling` | `IN_PROGRESS` — name excluded from search; safety constraint added |
| HC-06 | Brand/product mention | `test_planner.py::TestBrandHandling` | `IN_PROGRESS` — brand names excluded from search |
| HC-07 | Sad news / sensitive topic | `test_planner.py::TestSensitiveContent` | `IN_PROGRESS` — valid plan produced; no fabricated content |
| HC-08 | Portrait video, subject near frame edge | `test_hc_portrait_edge.py` | `NOT_STARTED` |
| HC-09 | Silent audio | `test_audio_pipeline.py::TestAudioOnly::test_silent_audio_raises` | `IN_PROGRESS` — SpeechNotDetectedError raised |
| HC-10 | Music-only audio | `test_audio_pipeline.py::TestAudioOnly::test_music_only_issues_warning` | `IN_PROGRESS` — SUSPECTED warning; not error |
| HC-11 | Wrong file type submitted | `test_audio_pipeline.py::TestAudioOnly::test_wrong_file_type_raises` | `IN_PROGRESS` — UnsupportedAudioFormatError raised |
| HC-12 | Empty script | `test_audio_pipeline.py::TestTextOnly::test_empty_script_raises` | `IN_PROGRESS` — EmptyScriptError raised |
| HC-13 | Corrupted download | `test_audio_pipeline.py::test_inspector_corrupted_error_propagates` | `IN_PROGRESS` — CorruptedAudioError propagates |
| HC-14 | Stock provider unavailable | `test_retrieval.py::TestMediaSearcher::test_provider_timeout_returns_empty_not_crash` | `IN_PROGRESS` — timeout caught; other providers continue |
| HC-15 | Generated-visual provider unavailable | `test_retrieval.py::TestSourceRouter::test_generated_provider_unavailable_falls_to_card` | `IN_PROGRESS` — card fallback; attempt recorded |
| HC-16 | Both external visual providers unavailable | `test_retrieval.py::TestSourceRouter::test_fallback_to_card_when_no_stock_no_generated` | `IN_PROGRESS` — card fallback with recorded attempts |
| HC-17 | Duplicate assets across scenes | `test_retrieval.py::TestCandidateRanker::test_duplicate_penalty_applied` | `IN_PROGRESS` — penalty applied; score reduced |
| HC-18 | Script/audio mismatch | `test_audio_pipeline.py::TestCombined::test_mismatched_script_and_transcript_warns` | `IN_PROGRESS` — mismatch warning issued |
| HC-19 | Invalid callback signature | `test_callbacks.py::TestVerifySignature::test_wrong_signature_rejected` | `IN_PROGRESS` — CallbackAuthError raised |
| HC-20 | Repeated idempotency key | `test_api_jobs.py::TestIdempotency::test_same_key_same_payload_returns_same_job` | `IN_PROGRESS` — same job returned |
| HC-21 | Concurrent users | `test_audio_pipeline.py::TestConcurrentIsolation` | `IN_PROGRESS` — isolation verified |
| HC-22 | Worker restart during job | `test_hc22_worker_restart.py` | `VERIFIED` — 27 tests pass; reconciler detects stale jobs, transitions to FAILED+retryable, guards terminal states |
| HC-23 | Interrupted rendering | `test_hc23_interrupted_render.py` | `VERIFIED` — 9 tests pass; work_dir cleanup on error, atomic cache writes, placeholder fails QA |
| HC-24 | Missing/invalid licence information | `test_retrieval.py::TestRightsValidator::test_missing_licence_raises_when_required` | `IN_PROGRESS` — LicenceVerificationError raised on missing/invalid licence |

---

## Part D — Definition of Done Checklist

| Gate | Description | Status |
|---|---|---|
| DoD-01 | Every official must-have has traceable implementation and passing evidence | `NOT_STARTED` |
| DoD-02 | Every Integration Standard item has traceable implementation and passing evidence | `NOT_STARTED` |
| DoD-03 | Text-only, audio-only, and combined-input workflows tested | `NOT_STARTED` |
| DoD-04 | At least one end-to-end job produces real validated MP4 | `NOT_STARTED` |
| DoD-05 | Rights provenance present for every external asset | `NOT_STARTED` |
| DoD-06 | Provider failure and recovery demonstrated | `NOT_STARTED` |
| DoD-07 | No-key test suite passes | `NOT_STARTED` |
| DoD-08 | Docker Compose setup works from clean environment | `NOT_STARTED` |
| DoD-09 | OpenAPI matches actual API | `NOT_STARTED` |
| DoD-10 | Required output files generated with valid schemas | `NOT_STARTED` |
| DoD-11 | Batch runner produces reproducible report | `NOT_STARTED` |
| DoD-12 | Repository contains no secrets | `NOT_STARTED` |
| DoD-13 | Documentation and evidence complete | `NOT_STARTED` |
| DoD-14 | System can be explained and modified during live review | `NOT_STARTED` |

---

## Gap Register

| Gap ID | Description | Action Required | Blocking |
|---|---|---|---|
| GAP-01 | No official assessment brief PDF found in workspace | Provide official brief; verify exact must-have wording and requirement count match | Yes — may alter requirement IDs or acceptance criteria |
| GAP-02 | Hard-case test fixtures (audio files, corrupted files) must be created or sourced | Create synthetic fixtures using Python / FFmpeg; no copyrighted media | No |
| GAP-03 | Stock footage provider API key (e.g., Pexels, Pixabay) required for live retrieval | Configure in `.env`; mock adapter used in no-key test suite | No |
| GAP-04 | TTS provider selection (e.g., Coqui TTS, edge-tts, ElevenLabs) pending licence verification | Select commercially permitted provider; mock adapter used in no-key tests | No |
| GAP-05 | LLM provider (optional planner enhancement) requires key and licence review | Implement rule-based planner as primary; LLM adapter is optional enhancement | No |
| GAP-06 | Assessment workbook fields requiring manual entry cannot be auto-filled | Provide checklist at Phase 7 of items requiring manual completion | No |
