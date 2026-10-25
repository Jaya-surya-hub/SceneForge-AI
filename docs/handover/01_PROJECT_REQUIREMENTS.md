# Project Requirements & Compliance Matrix

**Status:** PARTIALLY RECOVERED (full assessment brief unavailable)  
**Source:** Code inspection, README.md, REPORT.md, implementation analysis  

---

## Section A: Core Problem Statement

**Objective:** Build a production-quality video generation engine that transforms a script (with or without pre-recorded audio) into a narrated, captioned, rights-verified MP4 with full audit trail and quality assurance.

**Key Constraints:**
- Meaning-aware asset selection (not just keyword matching)
- Commercial-licence verification for all media
- Deterministic fallback to programmatic cards or recorded failure
- Real-time or near-real-time processing
- Docker containerized deployment
- No hardcoded secrets or API keys
- Mock adapters for all providers (for no-key testing)

**Expected Deliverables:**
1. `output.mp4` — H.264/AAC video, 16:9 (or 9:16, 1:1), 30 FPS
2. `timeline.json` — Scene-by-scene plan with reasons and rights refs
3. `manifest.json` — Job metadata, format validation, stats
4. `rights.json` — Provenance for every external asset
5. `captions.srt` — Subtitle file with valid timecodes
6. `metrics.json` — Runtime, cost estimates, QA results
7. `job.log` — Structured JSON log export

---

## Section B: Mandatory Requirements (The 8 Must-Haves)

**STATUS: PARTIALLY RECOVERED** — The official assessment brief was not located. The following requirements are inferred from code, tests, and documentation. **Obtain the official brief for confirmation.**

| # | Requirement | Status | Evidence | Remaining |
|---|---|---|---|---|
| 1 | **API accepts script** | ✅ VERIFIED | POST /jobs, script field parsed | None |
| 2 | **Real MP4 output** | ✅ VERIFIED | Job `c0f6dcfc...`: 42,663 bytes, H.264/AAC | None |
| 3 | **Captions from narration** | ✅ VERIFIED | SRT contains script text, timecoded | None |
| 4 | **Rights tracking** | ✅ VERIFIED | rights.json with provider, licence, commercial_use_eligible | None |
| 5 | **Docker deployment** | ✅ VERIFIED | Full stack runs: API, worker, DB, Redis | None |
| 6 | **Quality assurance** | ✅ VERIFIED | 14 QA checks (11 PASS, 3 SKIP, 0 FAIL in latest job) | None |
| 7 | **Artifact persistence** | ✅ VERIFIED | All 7 artifacts stored in filesystem, retrievable | None |
| 8 | **Job state machine** | ✅ VERIFIED | 6 stages: VALIDATING → PLANNING → RETRIEVING → RENDERING → QA → COMPLETED | None |

---

## Section C: Integration Standard Requirements (IS-XX)

**STATUS: PARTIALLY VERIFIED** — Full spec unknown. Based on code, these are likely requirements:

| ID | Requirement | Status | Evidence | Remaining |
|---|---|---|---|---|
| IS-06 | Batch runner CLI | ✅ IMPLEMENTED | `scripts/batch_runner.py` produces JSON report | Needs integration test |
| IS-08 | Worker restart resilience | ❌ NOT TESTED | No test for HC-22 (interrupted render) | Design + test |
| IS-09 | OpenAPI export | ✅ IMPLEMENTED | `openapi.json` (9 paths, all schemas) | Needs validation |
| IS-10 | Docker smoke test | ✅ PARTIALLY | Services start; no automated smoke test | Write smoke test script |
| ... | (others unknown) | UNKNOWN | Need official brief | — |

---

## Section D: Hard Cases (HC-XX)

**STATUS: UNKNOWN** — Full list not recoverable. Known hard cases from code:

| ID | Case | Status | Notes |
|---|---|---|---|
| HC-01–07 | Rule-based planning | ✅ IMPLEMENTED | Sentence segmentation, concept extraction, visual routing |
| HC-14–17 | Media retrieval | ✅ IMPLEMENTED | Mock providers; real Pexels/Pixabay not integrated |
| HC-22 | Worker restart + retry | ❌ NOT TESTED | Requires deliberate failure injection |
| HC-23 | Interrupted render | ❌ NOT TESTED | Requires mid-render termination |
| HC-24 | Rights rejection | ✅ IMPLEMENTED | Commercial-use check; fallback to card |
| ... | (others unknown) | UNKNOWN | Need official brief | — |

---

## Section E: Implementation Status by Component

### Audio Pipeline (Phase 3A)
- ✅ TTS: Real edge-tts via host_tts adapter, mock fallback
- ✅ STT: Mock adapter (Whisper not integrated)
- ✅ Validation: Audio duration, sample rate, codec checks
- ✅ Tests: 90 tests reported passing

### Scene Planning (Phase 3B)
- ✅ Segmentation: Sentence splitting, timestamp extraction
- ✅ Visual concept extraction: Rule-based heuristics
- ✅ Route assignment: Deterministic source routing
- ✅ Tests: 88 tests reported passing

### Media Retrieval & Rights (Phase 4)
- ✅ Retrieval: Mock Pexels/Pixabay adapters
- ✅ Ranking: Relevance scoring
- ✅ Routing: Stock → generated → card → recorded failure
- ✅ Rights: Licence validation, commercial-use check
- ✅ Tests: 71 tests reported passing
- ❌ Real downloads: Not implemented (Phase 6)

### Rendering & QA (Phase 5)
- ✅ FFmpeg: H.264/AAC, reframing, normalisation
- ✅ Subtitles: SRT generation from timeline
- ✅ Cache: Content-addressed storage
- ✅ QA: 14 automated checks
- ✅ Tests: 71 tests reported passing
- ⚠️ Audio energy validation: File presence checked, RMS not measured

### Docker & Deployment
- ✅ PostgreSQL: Migrations run successfully
- ✅ Redis: RQ worker queue functional
- ✅ API: FastAPI endpoints operational
- ✅ Worker: Background job processing works
- ✅ Filesystem storage: Reliable (MinIO blocked)
- ✅ Docker Compose: All services start, health checks pass

### OpenAPI & Batch
- ✅ OpenAPI: Schema exported, 9 paths, valid JSON
- ✅ Batch runner: CLI tool implemented, JSON report output
- ⚠️ Integration tests: Batch runner not tested against live API

---

## Section F: Test Coverage

| Suite | Count | Status | Notes |
|---|---|---|---|
| Phase 2 (baseline) | 129 | Previously reported passing | Needs rerun to verify |
| Phase 3A (audio) | 90 | Previously reported passing | Needs rerun to verify |
| Phase 3B (planning) | 88 | Previously reported passing | Needs rerun to verify |
| Phase 4 (retrieval) | 71 | Previously reported passing | Needs rerun to verify |
| Phase 5 (rendering) | 71 | Previously reported passing | Needs rerun to verify |
| **Total** | **449** | Previously reported passing | **Needs independent rerun** |
| E2E real jobs | 3 | Reported successful | Job artifacts may no longer exist |

---

## Section G: Known Gaps

### Not Implemented
1. **Real stock-footage download** — Phase 6 task
2. **Pexels/Pixabay API integration** — Requires API keys and download logic
3. **Worker restart/retry resilience** — Not tested
4. **Concurrent job isolation** — Multiple simultaneous jobs not tested
5. **Interrupted render recovery** — No failure injection test
6. **Audio RMS/energy validation** — File presence OK, RMS skipped
7. **Whisper STT** — Only mock STT implemented
8. **Coqui TTS** — Only mock TTS and edge-tts host_tts implemented

### Unverified
1. **MinIO production storage** — Docker Hub blocked; filesystem used
2. **Aspect ratio edge cases** — 1:1 and 9:16 not tested in E2E
3. **Multi-language support** — Only en-US tested
4. **Very long scripts** — Max length not tested
5. **Callback webhooks** — Implemented but not tested

---

## Section H: Evidence Summary

### Latest Verified E2E Job
```
Job ID: c0f6dcfc-0858-4c73-a32a-1a3430d3e452
Status: COMPLETED
Artifacts produced: 7/7
MP4 size: 42,663 bytes
MP4 codec: H.264/AAC
Resolution: 1920×1080
Frame rate: 30 FPS
Duration: ~2.69 seconds
TTS adapter: host_tts
TTS is mock: false
Real narration size: 16,128 bytes
Captions: Real script text with timestamps
QA result: 11 PASS, 3 SKIP, 0 FAIL
```

---

## Section I: Assessment Criteria Checklist

| Criterion | Status | Evidence | Required? |
|---|---|---|---|
| Produces real MP4 (not placeholder) | ✅ | ffprobe output | Yes (mandatory) |
| Includes narration | ✅ | TTS adapter, 16 KB audio | Yes (mandatory) |
| Includes captions | ✅ | SRT file with script text | Yes (mandatory) |
| Docker deployment | ✅ | All services healthy | Yes (mandatory) |
| Rights validation | ✅ | rights.json present | Yes (mandatory) |
| Stock footage | ❌ | Mock only | Unknown (need brief) |
| Batch processing | ✅ | CLI tool implemented | Unknown (need brief) |
| OpenAPI spec | ✅ | JSON exported | Unknown (need brief) |

---

## Section J: Requirements Status Legend

| Symbol | Meaning |
|---|---|
| ✅ | Implemented and verified |
| ⚠️ | Partially implemented or unverified |
| ❌ | Not implemented |
| UNKNOWN | Information not recoverable (need official brief) |

---

## Section K: Next Steps for Antigravity

1. **CRITICAL:** Obtain the official assessment brief and compare against this matrix
2. **HIGH:** Verify all 449 tests pass independently
3. **HIGH:** Verify stock-footage download requirements (mandatory vs. optional)
4. **MEDIUM:** Implement missing hard cases (HC-22, HC-23)
5. **MEDIUM:** Add concurrent-job isolation test
6. **LOW:** Implement real Pexels/Pixabay integration (if required)
7. **LOW:** Add audio RMS validation (if required)

---

**Prepared by:** Kiro AI  
**Date:** 2026-10-20  
**Status:** Ready for Antigravity review  
**Critical Action:** Find and read the official assessment brief
