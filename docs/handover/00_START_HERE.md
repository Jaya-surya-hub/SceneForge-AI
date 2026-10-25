# 🚀 START HERE — SceneForge AI Handover

**Project:** IncuBrix Software Engineer PS3 — SceneForge AI  
**Purpose:** Transform a script into a narrated, captioned, rights-verified B-roll MP4  
**Current Date:** 2026-10-20  
**Status:** **FUNCTIONAL WITH REAL END-TO-END VERIFICATION**

---

## ⚡ What Works RIGHT NOW

✅ **Real MP4 rendering** — FFmpeg produces genuine H.264/AAC video (not placeholder)  
✅ **Real TTS narration** — Edge-TTS pre-generated audio integrated via host_tts adapter  
✅ **Real captions** — SRT files contain actual script text with valid timestamps  
✅ **Docker deployment** — Full stack runs: PostgreSQL, Redis, API, worker  
✅ **API endpoints** — All core routes working (health, jobs, artifacts, files)  
✅ **Job orchestration** — 6 pipeline stages: VALIDATING → PLANNING → RETRIEVING → RENDERING → QA → COMPLETED  
✅ **Artifact storage** — Filesystem backend stores all 7 artifacts reliably  
✅ **Test suite** — 449 unit/integration tests previously reported passing  

**Latest verified E2E job:**
- Job ID: `c0f6dcfc-0858-4c73-a32a-1a3430d3e452`
- MP4: 42,663 bytes, H.264/AAC, 1920×1080, 30 FPS, 2.69s
- TTS: Real edge-tts via host_tts adapter (16,128 bytes)
- Captions: Script text in SRT with accurate timecodes
- Artifacts: 7 files produced and stored

---

## ⚠️ What is Incomplete or Unverified

❌ **Stock footage downloading** — Programmatic cards used as fallback (Phase 6 task)  
❌ **Worker restart resilience** — Not tested with failure scenarios  
❌ **Concurrent job isolation** — Multiple simultaneous jobs not tested  
❌ **Interrupted render recovery** — Not tested  
❌ **Audio energy validation** — File presence checked, but RMS not measured  
❌ **MinIO production storage** — Docker Hub blocked; filesystem used instead  
❌ **Test regression after latest changes** — 449 tests exist; needs independent rerun  

---

## 📋 Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| API Framework | FastAPI |
| Job Queue | RQ (Redis Queue) |
| Database | PostgreSQL 15 |
| Cache / Queue | Redis 7 |
| Object Storage | Filesystem (or MinIO) |
| Video Encoding | FFmpeg 6.x |
| Audio TTS | edge-tts (pre-generated, host_tts adapter) |
| Testing | pytest (449 tests) |
| Deployment | Docker Compose |

---

## 🎯 Your First Commands

### 1. Inspect the project

```bash
cd c:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3

# Check what exists
dir /B

# Read the requirements
type .env.example

# Inspect Python project config
type pyproject.toml

# Look at existing documentation
type README.md
type REPORT.md
```

### 2. Start Docker stack

```bash
# Ensure Docker Desktop is running
docker --version
docker compose version

# Start services
docker compose up -d

# Wait ~15 seconds, then verify
docker compose ps

# Check health
curl http://localhost:8000/health

# View logs (if needed)
docker compose logs -f api
```

### 3. Run the test suite

```bash
# Set environment
$env:PYTHONPATH = "c:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\src"
$env:SKIP_STARTUP_CHECKS = "true"
$env:DATABASE_URL = "sqlite:///C:\Users\Omen\sf_tests.db"

# Run tests
python -m pytest tests/unit tests/integration/test_api_jobs.py --tb=short -q

# Expected: ~449 tests (if unchanged from previous run)
```

### 4. Submit a test job

```bash
# Via PowerShell/curl
$body = @{
    script = "Innovation drives progress. We build the future."
    aspect_ratio = "16:9"
    tts_adapter = "mock"
    stock_provider = "mock"
} | ConvertTo-Json

$resp = Invoke-RestMethod -Uri "http://localhost:8000/jobs" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body

$JOB_ID = $resp.job_id
Write-Host "Job: $JOB_ID"

# Poll status
Invoke-RestMethod -Uri "http://localhost:8000/jobs/$JOB_ID"
```

### 5. Verify the latest E2E job (if artifacts remain)

```bash
# Check if the final test job artifacts are still available
docker exec incubrix-seaps3-worker-1 cat "/app/storage/sceneforge-artifacts/jobs/c0f6dcfc-0858-4c73-a32a-1a3430d3e452/manifest.json"
```

---

## 📚 Handover Documents (Read in Order)

| # | Document | Purpose |
|---|---|---|
| **1** | **`00_START_HERE.md`** (this file) | Orientation and quick start |
| **2** | `01_PROJECT_REQUIREMENTS.md` | Official requirements, compliance status |
| **3** | `02_ARCHITECTURE_AND_DATA_FLOW.md` | System design, component interactions |
| **4** | `03_REPOSITORY_MAP.md` | Directory tree, file purposes |
| **5** | `04_IMPLEMENTATION_STATUS.md` | Phase-by-phase progress, test history |
| **6** | `05_END_TO_END_EVIDENCE.md` | Latest job data, artifacts, limitations |
| **7** | `06_SETUP_AND_COMMANDS.md` | All tested commands for setup, tests, debugging |
| **8** | `07_ENVIRONMENT_AND_SECRETS.md` | Config, env vars, secrets management |
| **9** | `08_TESTING_AND_DEBUGGING.md` | Test structure, common failures, troubleshooting |
| **10** | `09_KNOWN_GAPS_AND_NEXT_STEPS.md` | Prioritized incomplete work, acceptance tests |
| **11** | `10_DECISION_LOG.md` | Architecture decisions and rationale |
| **12** | `11_ANTIGRAVITY_FIRST_TASK.md` | **READ THIS FIRST AS AN AI AGENT** |

---

## 🚦 Antigravity: Your Checklist Before Coding

- [ ] Read all 12 handover documents ↑
- [ ] Run the test suite independently (`python -m pytest ...`)
- [ ] Verify Docker services are healthy
- [ ] Attempt to retrieve the latest E2E job artifacts (document what you find)
- [ ] Inspect the MP4 with ffprobe if available
- [ ] Read the official assessment brief (in docs/ or provided separately)
- [ ] Audit all mandatory requirements (document compliance gaps)
- [ ] Do NOT rebuild the application yet
- [ ] Create a **verified gap matrix** before writing new code
- [ ] Distinguish between working components and incomplete/untested ones

---

## 🔑 Key Facts to Retain

1. **Git is NOT initialized** — This is a standalone project directory, not a Git repo
2. **Project root:** `C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3`
3. **Python source:** `src/sceneforge/` (12 modules)
4. **Tests:** `tests/unit/` and `tests/integration/` (~449 tests)
5. **Docker:** Full stack in `docker-compose.yml`; all services required
6. **Storage:** Filesystem backend (MinIO blocked by Docker Hub access)
7. **TTS:** Real edge-tts via pre-generated MP3 files, host_tts adapter
8. **Latest real job:** ID `c0f6dcfc-0858-4c73-a32a-1a3430d3e452` (42.6 KB MP4, real audio, real captions)
9. **No breaking changes:** Previous development reports show working pipeline; preserve it
10. **Assessment brief:** Must be obtained from submission guidelines (not fully recoverable from code)

---

## ⛔ DO NOT

- ❌ Rebuild completed modules without a concrete bug or requirement change
- ❌ Assume previous test reports are the latest (rerun independently)
- ❌ Treat mock adapters as equivalent to real integrations
- ❌ Silence failing tests to reach target count
- ❌ Invent stock footage or licence records
- ❌ Commit secrets to version control
- ❌ Force-reset or rewrite the project structure without documenting why

---

## ✅ DO

- ✅ Verify everything independently first
- ✅ Keep real and mock integrations distinguishable
- ✅ Document what you change and why
- ✅ Preserve the 449-test regression suite
- ✅ Test end-to-end before marking complete
- ✅ Record all blocking issues clearly
- ✅ Maintain audit trail and provenance

---

## 🆘 If Something Breaks

1. **Check `08_TESTING_AND_DEBUGGING.md`** — Common failures and solutions
2. **Inspect Docker logs:** `docker compose logs -f service_name`
3. **Verify environment:** `.env.example` vs `.env`
4. **Restart cleanly:**
   ```bash
   docker compose down
   docker compose up -d
   docker compose ps
   ```
5. **Test in isolation:** Run a single pytest file, not the whole suite
6. **Document the issue** in the gap matrix before fixing

---

## 📞 Questions for the Human (You)

Before Antigravity starts, you should clarify:

1. **Where is the official assessment brief?** ← Critical for compliance checklist
2. **Is MinIO required for production, or is filesystem OK?** ← Impacts deployment plan
3. **What is the submission deadline and format?** ← Determines priority
4. **Are stock footage downloads mandatory or advanced?** ← Changes Phase 6 priority
5. **Is full concurrent-job testing required, or can it be Phase 7?** ← Scope clarification

---

**Next:** Read `11_ANTIGRAVITY_FIRST_TASK.md` (right after this) to understand your first steps as an agent.

Then proceed through documents 1–10 in order.

---

**Last Updated:** 2026-10-20  
**Preserved By:** Kiro AI  
**For:** Antigravity AI  
**Status:** Ready for handover ✅
