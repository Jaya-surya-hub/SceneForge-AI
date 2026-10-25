# FOR ANTIGRAVITY: YOUR FIRST TASK

**Read this IMMEDIATELY after `00_START_HERE.md`**

You are Antigravity, an AI coding agent. Kiro has prepared a handover of the SceneForge AI project. Your task is to verify the current state, understand what works, identify what doesn't, and prepare for the next phase of development.

**Do not code yet. Do not rebuild. Just verify and document.**

---

## Phase A: Verification (1–2 hours)

### Step 1: Read all handover documents

Open and read these in order:
1. `00_START_HERE.md` ← You just did this
2. `01_PROJECT_REQUIREMENTS.md`
3. `02_ARCHITECTURE_AND_DATA_FLOW.md`
4. `03_REPOSITORY_MAP.md`
5. `04_IMPLEMENTATION_STATUS.md`
6. `05_END_TO_END_EVIDENCE.md`
7. `06_SETUP_AND_COMMANDS.md`
8. `07_ENVIRONMENT_AND_SECRETS.md`
9. `08_TESTING_AND_DEBUGGING.md`
10. `09_KNOWN_GAPS_AND_NEXT_STEPS.md`
11. `10_DECISION_LOG.md`

Then return to this document.

**Time: ~30 minutes. Do not skip.**

---

### Step 2: Inspect the repository

```bash
cd c:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3

# Verify project structure
dir /B

# Check main files
type README.md | head -50
type REPORT.md | head -50
type .env.example | head -30

# Verify source code exists
dir /B src\sceneforge

# Verify tests exist
dir /B tests\unit | head -20

# Check Docker setup
type Dockerfile | head -30
type docker-compose.yml | head -50
```

**Document:** Does the project structure match what the handover describes?

---

### Step 3: Verify Docker is ready

```bash
# Check Docker is installed and running
docker --version
docker compose version

# List running containers (should be empty or from other projects)
docker compose ps

# Start the stack
docker compose up -d

# Wait 15 seconds
Start-Sleep -Seconds 15

# Verify all services are healthy
docker compose ps

# Expected output: all services show "Up" or "healthy"

# Check API health
curl http://localhost:8000/health

# Expected: {"status":"ok","version":"0.1.0","environment":"development"}
```

**Document:** Are all services running? Is the API responding?

---

### Step 4: Run the test suite independently

```bash
# Set Python environment
$env:PYTHONPATH = "C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\src"
$env:SKIP_STARTUP_CHECKS = "true"
$env:DATABASE_URL = "sqlite:///C:\Users\Omen\antigravity_tests.db"
$env:CALLBACK_HMAC_SECRET = "test-secret"

# Run the full suite (unit + integration)
python -m pytest tests/unit tests/integration/test_api_jobs.py --tb=line -v 2>&1 | Tee-Object -FilePath "C:\Users\Omen\test_results.txt"

# Count results
Select-String "passed|failed|error" "C:\Users\Omen\test_results.txt" | Select-Object -Last 1
```

**Document:**
- How many tests passed?
- How many failed?
- Do failures match the known issues in `08_TESTING_AND_DEBUGGING.md`?
- Is this count similar to the previously reported 449?

---

### Step 5: Attempt to retrieve the latest E2E job artifacts

Kiro reported that job `c0f6dcfc-0858-4c73-a32a-1a3430d3e452` was successfully rendered. Try to access its artifacts:

```bash
# Check if the artifacts directory exists
docker exec incubrix-seaps3-worker-1 ls -la "/app/storage/sceneforge-artifacts/jobs/c0f6dcfc-0858-4c73-a32a-1a3430d3e452/" 2>&1

# If found, inspect the manifest
docker exec incubrix-seaps3-worker-1 cat "/app/storage/sceneforge-artifacts/jobs/c0f6dcfc-0858-4c73-a32a-1a3430d3e452/manifest.json" 2>&1

# If found, check the captions
docker exec incubrix-seaps3-worker-1 cat "/app/storage/sceneforge-artifacts/jobs/c0f6dcfc-0858-4c73-a32a-1a3430d3e452/captions.srt" 2>&1

# If found, verify the MP4 with ffprobe
docker exec incubrix-seaps3-worker-1 ffprobe -v quiet -print_format json -show_format "/app/storage/sceneforge-artifacts/jobs/c0f6dcfc-0858-4c73-a32a-1a3430d3e452/output.mp4" 2>&1
```

**Document:**
- Do the artifacts still exist?
- Does the manifest show `"tts_is_mock": false` and `"real_mp4_rendered": true`?
- Do the captions contain real script text?
- Does ffprobe report H.264/AAC, 1920×1080, 30 FPS?

---

### Step 6: Submit a new test job

Generate your own job to verify the pipeline:

```bash
# Create and submit a job
$script = "The future of technology depends on trust and innovation."
$body = @{
    script = $script
    aspect_ratio = "16:9"
    tts_adapter = "mock"
    stock_provider = "mock"
} | ConvertTo-Json

$resp = Invoke-RestMethod -Uri "http://localhost:8000/jobs" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body `
  -Headers @{"Idempotency-Key" = "antigravity-verify-job"}

$JOB_ID = $resp.job_id
Write-Host "Submitted job: $JOB_ID"

# Poll until completion (up to 2 minutes)
for ($i=1; $i -le 24; $i++) {
    Start-Sleep -Seconds 5
    $r = Invoke-RestMethod -Uri "http://localhost:8000/jobs/$JOB_ID"
    Write-Host "[$($i*5)s] $($r.status)"
    if ($r.status -in @("COMPLETED","FAILED")) { break }
}

# Inspect final status
$final = Invoke-RestMethod -Uri "http://localhost:8000/jobs/$JOB_ID"
Write-Host "Final status: $($final.status)"
Write-Host "Error (if any): $($final.error_code)"

# Get artifacts
$arts = Invoke-RestMethod -Uri "http://localhost:8000/jobs/$JOB_ID/artifacts"
Write-Host "Artifacts: $($arts.artifacts -join ', ')"
```

**Document:**
- Did the job complete successfully?
- Were all 7 artifacts produced?
- If it failed, what was the error?

---

### Step 7: Inspect the official assessment brief

You need to find the official IncuBrix assessment requirements. Kiro could not recover them fully from code.

**Sources to check:**
1. Is there a `docs/ASSESSMENT_BRIEF.md` or similar in the project?
2. Is there a `REQUIREMENTS.md` or `SPECIFICATION.md`?
3. Check the root `docs/` folder for any requirement files
4. Check the human's instructions (your prompt context)
5. If none found, document as **UNKNOWN** and ask the human

**When you find it, extract:**
- The 8 must-haves (or whatever count is specified)
- The Integration Standard requirements (IS-01, IS-02, etc.)
- The hard cases (HC-XX)
- Acceptance criteria
- Submission deadline and format

---

## Phase B: Create a Verified Gap Matrix (30 minutes)

Create a spreadsheet or markdown table documenting:

| Requirement | Status | Evidence | Notes |
|---|---|---|---|
| Real MP4 rendering | ✅ VERIFIED | Job `c0f6dcfc...` produced 42.6 KB MP4, ffprobe confirmed H.264/AAC, 1920×1080, 30 FPS | OK |
| Real TTS narration | ✅ VERIFIED | Manifest shows `tts_adapter: host_tts`, `tts_is_mock: false`, 16.1 KB audio | OK |
| Real captions | ✅ VERIFIED | SRT contains script text with valid timestamps | OK |
| Docker deployment | ✅ VERIFIED | All services healthy, health check passing | OK |
| API endpoints | ✅ VERIFIED | POST /jobs, GET /jobs/{id}, GET /jobs/{id}/artifacts working | OK |
| Stock footage download | ❌ NOT IMPLEMENTED | Code uses programmatic card fallback | Phase 6 task |
| Worker restart resilience | ❌ NOT TESTED | No test coverage for HC-22, HC-23 | Phase 6 task |
| Concurrent job isolation | ❌ NOT TESTED | No multi-job load test | Phase 6 task |
| ... (continue for all requirements) |

---

## Phase C: Report Back (Required)

When you've completed Phase A and B, create a file named:

```
docs/handover/ANTIGRAVITY_FIRST_FINDINGS.md
```

In that file, document:

1. **Test suite results:** How many tests passed? Failed? Any unexpected failures?
2. **Docker health:** All services running? Any startup issues?
3. **Latest job verification:** Do the reported artifacts exist and match the claims?
4. **Assessment brief status:** Did you find it? What are the requirements?
5. **Gap matrix:** What is implemented and verified? What is missing?
6. **Blockers:** Are there any show-stoppers preventing you from continuing?
7. **Questions:** What do you need clarified from the human before proceeding?

---

## Phase D: Plan Your Next Work (1 hour)

Do NOT code yet.

1. **Prioritize:** Which incomplete requirements are mandatory vs. optional?
2. **Estimate:** How much work for each?
3. **Plan:** What is the most important thing to finish first?
4. **Test strategy:** How will you verify it?
5. **Risk assessment:** What could break existing functionality?

Create a file:

```
docs/handover/ANTIGRAVITY_WORK_PLAN.md
```

Include your prioritized task list with acceptance tests.

---

## ✅ Success Criteria

- [ ] All 11 handover documents read
- [ ] Repository structure verified
- [ ] Docker services verified healthy
- [ ] Test suite run independently (results documented)
- [ ] Latest E2E job artifacts inspected (results documented)
- [ ] New test job submitted and completed
- [ ] Official assessment brief located (or marked UNKNOWN)
- [ ] Gap matrix created
- [ ] `ANTIGRAVITY_FIRST_FINDINGS.md` written
- [ ] `ANTIGRAVITY_WORK_PLAN.md` written

---

## 🚫 If You Get Stuck

- **Docker won't start?** Check `08_TESTING_AND_DEBUGGING.md` → Docker Issues section
- **Tests fail?** Check `08_TESTING_AND_DEBUGGING.md` → Common Failures section
- **Job doesn't complete?** Check worker logs: `docker logs incubrix-seaps3-worker-1`
- **Can't find assessment brief?** Mark as UNKNOWN and ask the human for clarification

---

## ⏱️ Timeline

- **Phase A (Verification):** 1–2 hours
- **Phase B (Gap Matrix):** 30 minutes
- **Phase C (Report):** 30 minutes
- **Phase D (Work Plan):** 1 hour

**Total before coding: 3–4 hours**

This is worth it. You will enter the coding phase with complete context and confidence.

---

**Now go!** Start with the handover documents. Return here when done.

---

**Status:** Awaiting Antigravity execution  
**Last Updated:** 2026-10-20  
**Next Step:** Read `01_PROJECT_REQUIREMENTS.md`
