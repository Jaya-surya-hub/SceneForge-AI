# ANTIGRAVITY WORK PLAN
**Agent:** Antigravity  
**Date:** 2026-10-20  
**Deadline:** 2026-10-25 23:59 IST (5 days)

---

## Baseline Confirmed

✅ 449 tests pass (Python 3.14.2, no API keys needed)  
✅ Docker stack healthy (4 services)  
✅ E2E job artifacts exist and are real (H.264/AAC, 1920×1080, 30fps)  
✅ Real TTS audio confirmed (host_tts, tts_is_mock: false)  
✅ Real captions confirmed (script text, valid SRT format)  
✅ 7 artifacts produced and stored  
⚠️ QA overall = FAIL (root cause: scene_id=None bug in _stage_qa, fixable)

---

## Priority Matrix

| Priority | Item | Effort | Mandatory | Status |
|---|---|---|---|---|
| P0 | Fix QA FAIL (scene_id bug) | 30 min | YES | READY |
| P0 | Submit new verification job & confirm QA PASS | 15 min | YES | READY |
| P1 | Implement HC-22 (worker restart test) | 2 hr | YES | NOT_STARTED |
| P1 | Implement HC-23 (interrupted render test) | 2 hr | YES | NOT_STARTED |
| P1 | IS-08 concurrency isolation test | 2 hr | YES | NOT_STARTED |
| P2 | Update REPORT.md with phase status = PASS | 30 min | YES | READY |
| P2 | Update requirements_traceability.md DoD gates | 1 hr | YES | READY |
| P2 | Batch runner live API integration test | 1 hr | YES | READY |
| P2 | OpenAPI validation test | 30 min | YES | READY |
| P3 | Test 1:1 and 9:16 aspect ratios E2E | 30 min | UNKNOWN | READY |
| P3 | Audio-only job input test | 30 min | UNKNOWN | READY |
| P3 | Combined script+audio job test | 30 min | UNKNOWN | READY |
| P4 | Real stock footage integration (Pexels) | 4-6 hr | UNKNOWN | BLOCKED (needs key) |
| P4 | Audio RMS/energy validation | 30 min | UNKNOWN | PARTIAL |
| P4 | MinIO/S3 storage (IS-04) | 2-4 hr | DEPENDS | BLOCKED (Docker Hub) |
| P5 | Update all docs for submission | 2 hr | YES | PARTIAL |

---

## Detailed Task List

### TASK 1 (P0): Fix QA FAIL — scene_id=None bug

**Problem:** In `orchestrator.py` `_stage_qa()`, when reconstructing RightsRecord objects
from DB snapshots, `scene_id` is hardcoded to `None` (line ~622). The QAChecker's
`_check_rights_coverage` checks `r.scene_id` for each record, and since all are None,
the `covered` set is empty, causing the check to FAIL even though all assets have rights.

**Fix:** Persist scene_id in the rights_records_data dict during `_stage_retrieve()`, and
restore it during `_stage_qa()` reconstruction.

**Files:**
- `src/sceneforge/jobs/orchestrator.py`
- Add `scene_id` to `rights_records_data` dict (lines ~317-348)
- Add `scene_id` to `rights_data_snapshot` (lines ~557-574)
- Restore `scene_id` when building RightsRecord in _stage_qa (line ~622)

**Also:** Store `scene_id` in the DB rights_records table if not already.

**Acceptance:** New E2E job → QA rights_coverage check = PASS → qa_overall = PASS

---

### TASK 2 (P1): HC-22 — Worker Restart During Job

**Test:** Submit job → wait for RENDERING state → kill worker → start worker → verify recovery

**Implementation approach:**
- Test file: `tests/hard_cases/test_hc_worker_restart.py`
- Submit job via API (with httpx or Invoke-RestMethod)
- Poll until RENDERING state
- Kill worker container or process
- Restart worker
- Poll until COMPLETED or verify clean FAILED state
- Assert: no data corruption, job state consistent

**Note:** True Docker-level suspend may not be feasible from pytest. Use Docker exec kill
approach or simulate by stopping the RQ worker process and letting it recover.

---

### TASK 3 (P1): HC-23 — Interrupted Rendering

**Test:** Similar to HC-22 but specifically during FFmpeg render stage

**Implementation approach:**
- Test file: `tests/hard_cases/test_hc_interrupted_render.py`
- Submit job, monitor worker logs for stage_render_ok log event
- Kill FFmpeg process mid-render (or kill worker)
- Verify job is either re-queued or marked FAILED with appropriate error
- Verify no partial/corrupt artifacts persist

---

### TASK 4 (P1): IS-08 — Concurrent Job Isolation

**Test:** Submit 3+ simultaneous jobs and verify no artifact cross-contamination

**Implementation approach:**
- `tests/integration/test_job_resilience.py`
- Submit N jobs with unique idempotency keys
- Poll all to completion
- Verify each job's artifacts are isolated (different job IDs in folders)
- Verify no cross-contamination (manifest.job_id matches the job)

---

### TASK 5 (P2): Documentation Updates

1. Update `REPORT.md` — fill in phase status table (all to PASS)
2. Update `docs/requirements_traceability.md` — update DoD gates to PASS
3. Update `README.md` — add quick start and status
4. Update `AI_USE.md` — document Kiro and Antigravity AI usage

---

### TASK 6 (P2): Batch Runner Live Test

**Action:** Run `scripts/batch_runner.py` against local Docker API:
```powershell
python scripts/batch_runner.py \
  --cases tests/fixtures/batch_cases.json \
  --base-url http://localhost:8000 \
  --output batch_report.json
```
Document results. If batch runner fails, fix it.

---

### TASK 7 (P3): Additional E2E Tests

1. Aspect ratio 1:1 job — verify 1080×1080 output
2. Aspect ratio 9:16 job — verify 1080×1920 output  
3. Combined script+empty audio — verify graceful handling
4. Audio-only job (if API supports it)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| QA fix breaks existing tests | LOW | HIGH | Run 449 tests after each change |
| Worker restart test flaky | MEDIUM | MEDIUM | Use generous timeouts, document limitations |
| MinIO remains blocked | HIGH | LOW | Filesystem IS acceptable; document it clearly |
| Official brief has unmet requirements | MEDIUM | HIGH | Ask user for brief ASAP |
| Stock footage required as mandatory | LOW | HIGH | Implement if confirmed; note API key needed |

---

## Work Order (Day by Day)

### Day 1 (2026-10-20 — TODAY)
- [x] Read all handover documents
- [x] Verify 449 tests pass
- [x] Verify Docker health
- [x] Verify E2E job artifacts
- [x] Identify QA FAIL root cause
- [ ] Fix QA FAIL (scene_id bug)
- [ ] Submit verification job, confirm QA PASS
- [ ] Run full test suite after fix

### Day 2 (2026-10-21)
- [ ] Implement HC-22 (worker restart hard case)
- [ ] Implement HC-23 (interrupted render hard case)
- [ ] Run batch runner live test
- [ ] Test 1:1 and 9:16 aspect ratios

### Day 3 (2026-10-22)
- [ ] Implement IS-08 (concurrent job isolation)
- [ ] Fix any remaining test failures
- [ ] Update REPORT.md and traceability matrix
- [ ] OpenAPI validation test

### Day 4 (2026-10-23)
- [ ] Update all documentation
- [ ] Run complete E2E acceptance flow
- [ ] Prepare submission artifacts
- [ ] Demo video capture (if required)

### Day 5 (2026-10-24-25)
- [ ] Final review and submission
- [ ] Address any last-minute issues

---

## Questions for the Human (Blocking)

1. **Is there an official IncuBrix PS3 PDF brief?** — needed to confirm exact requirements
2. **Is real stock footage downloading mandatory or optional?**
3. **Is IS-04 MinIO specifically required or is filesystem storage acceptable?**
4. **What is the submission mechanism?** (GitHub repo, zip, form link)
5. **Is a demo video required?** If yes, screen recording or automated?
6. **Are there specific performance/timing requirements?** (e.g., <60s per job)

---

**Status:** Ready to execute. Starting with P0 tasks immediately.
