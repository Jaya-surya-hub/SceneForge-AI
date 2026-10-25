# Known Gaps & Next Steps (Prioritized)

---

## PRIORITY 1: CRITICAL BLOCKERS

### 1.1 Verify Test Suite (BLOCKER)
**Status:** ❌ UNKNOWN  
**Impact:** Cannot claim compliance without knowing if 449 tests still pass  
**Action:**
```bash
# Run independently and document results
python -m pytest tests/unit tests/integration/test_api_jobs.py -v --tb=short
# Expected: ~449 PASS + some SKIP
# If <440 pass: investigate failures before proceeding
```
**Acceptance:** 440+ tests pass, failure list documented  
**Timeline:** 1 hour

---

### 1.2 Obtain Official Assessment Brief (BLOCKER)
**Status:** ❌ MISSING  
**Impact:** Cannot determine if implementation meets requirements  
**Requirement IDs:** Must-haves (8?), Integration Standard (IS-01..IS-10?), Hard Cases (HC-01..HC-24?)  
**Action:** Get from submission guidelines or project documentation  
**Acceptance:** Brief document with explicit requirement IDs + acceptance criteria  
**Timeline:** Outside agent control; ask human

---

### 1.3 Verify E2E Job Artifacts
**Status:** ⚠️ REPORTED (needs verification)  
**Impact:** Latest job may have been cleaned up; need fresh verification  
**Action:**
```bash
# Try to access job c0f6dcfc-0858-4c73-a32a-1a3430d3e452
docker exec incubrix-seaps3-worker-1 cat "/app/storage/sceneforge-artifacts/jobs/c0f6dcfc-0858-4c73-a32a-1a3430d3e452/manifest.json"
```
**Acceptance:** Either artifacts exist and match claims OR job expired (document either)  
**Timeline:** 10 minutes

---

## PRIORITY 2: HIGH-IMPACT GAPS

### 2.1 Real Stock-Footage Downloading
**Status:** ❌ NOT IMPLEMENTED  
**Impact:** Mandatory if assessment requires real media (unknown)  
**Current fallback:** Programmatic cards (correct, documented)  
**Scope:**
- Integrate Pexels API (requires key)
- Implement video download logic
- Validate licence compliance
- Store in filesystem/MinIO
- Create tests

**Acceptance:**
```bash
# Submit job, verify at least 1 scene uses real video
Invoke-RestMethod POST /jobs | Wait | Check manifest for real_video_downloaded: true
```
**Timeline:** 4-6 hours  
**Dependencies:** PEXELS_API_KEY, assessment brief

---

### 2.2 Worker Restart & Retry Resilience (HC-22, HC-23)
**Status:** ❌ NOT TESTED  
**Impact:** Production reliability unknown  
**Scope:**
- Test killing worker mid-render
- Verify job state recovery
- Test automatic retry
- Test timeout handling

**Acceptance:**
```bash
# Kill worker while job in progress
docker kill incubrix-seaps3-worker-1
# Verify job recovers or is retried
# Verify no data corruption
```
**Timeline:** 2-3 hours  
**Risk:** High; could expose data consistency issues

---

### 2.3 Concurrent Job Isolation (IS-08)
**Status:** ❌ NOT TESTED  
**Impact:** Multi-user deployment untested  
**Scope:**
- Submit 5 simultaneous jobs
- Verify correct artifact separation
- Verify no cross-job data leaks
- Test queue ordering

**Acceptance:** All jobs complete independently with correct artifacts  
**Timeline:** 1-2 hours

---

## PRIORITY 3: MEDIUM-IMPACT GAPS

### 3.1 Audio Energy Validation
**Status:** ⚠️ PARTIAL (file presence OK, RMS not measured)  
**Impact:** Cannot detect silent/corrupted audio  
**Scope:**
- Install librosa or scipy
- Add RMS energy calculation to QA
- Set threshold (e.g., require > 0.01 RMS)
- Fail check if too quiet

**Acceptance:** QA check reports RMS value, fails if below threshold  
**Timeline:** 30 minutes

---

### 3.2 MinIO Production Storage
**Status:** ❌ BLOCKED (Docker Hub access)  
**Impact:** Filesystem works; production may require S3  
**Scope:**
- Either: Get Docker Hub access restored
- Or: Document filesystem as production storage
- Or: Implement S3 (AWS) alternative

**Acceptance:** Either MinIO running OR documented why filesystem is acceptable  
**Timeline:** 1-2 hours (depends on network access)

---

### 3.3 Aspect Ratio Edge Cases (1:1, 9:16)
**Status:** ⚠️ CODE EXISTS (not tested E2E)  
**Impact:** Non-16:9 videos untested  
**Scope:**
- Submit job with aspect_ratio: "1:1"
- Submit job with aspect_ratio: "9:16"
- Verify output dimensions correct
- Verify rendering doesn't fail

**Acceptance:** Both aspect ratios produce correct output  
**Timeline:** 30 minutes

---

## PRIORITY 4: OPTIONAL ENHANCEMENTS

### 4.1 Multi-Language Support
**Status:** ❌ NOT IMPLEMENTED  
**Impact:** Nice-to-have; English only currently  
**Scope:** Add language parameter, test with multiple TTS voices  
**Timeline:** 2-3 hours (if needed)

---

### 4.2 Webhook Callbacks
**Status:** ✅ CODE EXISTS (not tested)  
**Impact:** Optional; can be added later  
**Scope:** Write integration test for callback webhooks  
**Timeline:** 1 hour (if needed)

---

### 4.3 Whisper STT Integration
**Status:** ❌ NOT IMPLEMENTED  
**Impact:** Nice-to-have; mock STT works  
**Scope:** Implement Whisper adapter for speech-to-text  
**Timeline:** 2-3 hours (if needed)

---

## PRIORITY 5: VERIFICATION TASKS

### 5.1 Regression Matrix
**Status:** ⚠️ PARTIAL (449 tests exist, not all independently verified)  
**Action:** Run test suite and document any failures  
**Timeline:** 1 hour

---

### 5.2 Compliance Gap Matrix
**Status:** ❌ UNKNOWN (need official brief)  
**Action:** Cross-reference requirements against implementation  
**Timeline:** 2 hours (with brief)

---

### 5.3 Docker Smoke Test
**Status:** ⚠️ MANUAL (no automated script)  
**Action:** Create CI-style script that:
- Starts services
- Runs health check
- Submits test job
- Verifies completion
- Cleans up
**Timeline:** 1-2 hours

---

## RECOMMENDED WORK ORDER

1. **Immediately:**
   - Rerun test suite (verify 449 still pass)
   - Get official assessment brief
   - Verify E2E job artifacts

2. **High Priority (Week 1):**
   - Implement real stock-footage download (if mandatory)
   - Test worker restart resilience
   - Test concurrent jobs

3. **Medium Priority (Week 2):**
   - Add audio energy validation
   - Resolve MinIO/S3 storage
   - Test all aspect ratios

4. **If Time Permits:**
   - Add webhook test
   - Multi-language support
   - Whisper STT

---

## Acceptance Tests

### Stock Footage (if mandatory)
```bash
submit_job(tts="mock", stock="pexels")
wait_for_completion()
assert job.manifest.real_video_downloaded == true
assert job.rights.count > 0  # Has licence records
ffprobe(output.mp4) -> confirm video content
```

### Worker Resilience
```bash
submit_job()
while not rendering:
  sleep(1)
docker kill worker
sleep(5)
docker restart worker
wait_for_job_completion()
assert job.status == "COMPLETED"  # Recovered successfully
```

### Concurrent Jobs
```bash
for i in 1..5:
  submit_job(idempotency_key=f"job-{i}")
wait_all()
for i in 1..5:
  assert get_job(id_i).artifacts.count == 7
  assert_no_cross_job_data_leaks()
```

---

## Known Technical Debt

| Item | Severity | Notes |
|---|---|---|
| Host_tts workaround | LOW | Docker TTS network block; pre-generated audio works |
| Filesystem vs S3 | MEDIUM | Works; production may prefer S3 |
| Placeholder captions fixed | FIXED | Was using mock; now uses real timeline |
| SQLAlchemy detached instances | FIXED | Was causing session errors; fixed in orchestrator |
| Font download at runtime | LOW | Works; could be baked into Dockerfile |

---

## Assessment Checklist (For Antigravity)

Before declaring complete:

- [ ] Rerun test suite → document results
- [ ] Obtain + audit assessment brief
- [ ] Create verified requirements matrix
- [ ] Verify latest E2E job artifacts (or note they expired)
- [ ] Test stock-footage requirement (if mandatory)
- [ ] Test worker restart (if mandatory)
- [ ] Test concurrent jobs (if mandatory)
- [ ] Document all remaining gaps
- [ ] Identify any show-stoppers
- [ ] Propose Phase 7 plan (if needed)

---

**Prepared by:** Kiro AI  
**Last Updated:** 2026-10-20  
**For:** Antigravity AI  
**Status:** Ready for execution
