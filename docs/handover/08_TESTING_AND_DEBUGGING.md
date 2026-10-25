# Testing & Debugging Guide

---

## Test Suite Structure

### Unit Tests (`tests/unit/`)

- `test_state_machine.py` — Job state transitions
- `test_audio_*.py` — TTS/STT adapters
- `test_planner_*.py` — Scene planning
- `test_retrieval_*.py` — Media retrieval
- `test_rendering_*.py` — FFmpeg rendering
- `test_quality_*.py` — QA checks
- `test_storage_*.py` — Storage backends

**Command:**
```bash
python -m pytest tests/unit -v
```

### Integration Tests (`tests/integration/`)

- `test_api_jobs.py` — Full API workflow

**Command:**
```bash
python -m pytest tests/integration/test_api_jobs.py -v
```

**Requires:** Docker services running

---

## Running Tests

### All Tests

```bash
python -m pytest tests/ -v --tb=short
# Expected: ~449 pass + some skip
```

### Single Test File

```bash
python -m pytest tests/unit/test_audio_factory.py -v
```

### Single Test

```bash
python -m pytest tests/unit/test_audio_factory.py::test_mock_tts_silent -v
```

### With Specific Markers

```bash
python -m pytest -m hard_case -v        # Hard case tests
python -m pytest -m slow -v             # Slow tests (>5s)
python -m pytest -m "not requires_api_key" -v  # Skip tests needing keys
```

### With Coverage

```bash
python -m pytest tests/ --cov=src/sceneforge --cov-report=html
# Opens htmlcov/index.html in browser
```

---

## Common Test Failures

### "SQLAlchemy session error: Instance not bound"

**Cause:** ORM object used after session closed  
**Fix in code:** Snapshot ORM attributes to dicts before session exit  
**Example:**
```python
# ❌ WRONG
with get_session() as session:
    job = session.query(Job).first()
# job is now detached!
return job.created_at  # FAILS

# ✅ CORRECT
with get_session() as session:
    job = session.query(Job).first()
    created_at = job.created_at  # Snapshot attribute
# Use created_at outside session
return created_at
```

### "FileNotFoundError: Roboto font not found"

**Cause:** Font missing in container  
**Fix:** Verify Dockerfile includes font installation  
**Command:**
```bash
docker exec incubrix-seaps3-worker-1 ls -la /usr/local/share/fonts/
```
**Expected:** `Roboto-Regular.ttf` present

### "FFmpeg: Cannot find valid font family Sans"

**Cause:** Font path wrong or not in docker exec environment  
**Fix:** Update card_generator.py to use `_FONT_FILE` env var  
**Verify:**
```bash
docker exec incubrix-seaps3-worker-1 ffmpeg -filters | grep drawtext
```

### "Edge-TTS 403: Invalid response status"

**Cause:** Docker NAT blocks `wss://speech.platform.bing.com`  
**Fix:** Use `TTS_ADAPTER=host_tts` (pre-generated audio)  
**Workaround:** Set `TTS_PRE_GENERATED_PATH=/app/storage/tts_narration_e2e.mp3`

### "MinIO connection refused"

**Cause:** S3Mock Docker image not available (403 on Docker Hub)  
**Fix:** Use filesystem backend (current default)  
**Verify:**
```bash
echo $env:STORAGE_BACKEND  # Should be "filesystem"
```

---

## Debugging Techniques

### View Docker Logs

```bash
# All services
docker compose logs --tail=50

# Specific service
docker compose logs -f api
docker compose logs -f worker

# With grep
docker compose logs | Select-String "error|ERROR|FAIL"
```

### Enter Container Shell

```bash
# API container
docker exec -it incubrix-seaps3-api-1 /bin/bash

# Worker container
docker exec -it incubrix-seaps3-worker-1 /bin/bash

# Run command in container
docker exec incubrix-seaps3-worker-1 python3 -c "import sceneforge; print('OK')"
```

### Test Database Connection

```bash
# From host
psql postgresql://sceneforge:password@localhost:5432/sceneforge

# From container
docker exec incubrix-seaps3-db-1 psql -U sceneforge -c "SELECT COUNT(*) FROM job;"
```

### Test Redis Connection

```bash
docker exec incubrix-seaps3-redis-1 redis-cli PING
# Expected: PONG
```

### View Job Queue

```bash
# See RQ queue status
docker exec incubrix-seaps3-redis-1 redis-cli KEYS "rq:*"

# Get job details
docker exec incubrix-seaps3-redis-1 redis-cli GET "rq:job:JOBID"
```

---

## Reproducing E2E Issues

### Step 1: Submit a Job

```bash
$body = @{
    script = "Test script."
    aspect_ratio = "16:9"
    tts_adapter = "mock"
} | ConvertTo-Json

$resp = Invoke-RestMethod -Uri http://localhost:8000/jobs -Method POST -Body $body
$JOB_ID = $resp.job_id
Write-Host "Job: $JOB_ID"
```

### Step 2: Monitor Logs

```bash
# Watch worker logs in real-time
docker compose logs -f worker | Select-String $JOB_ID
```

### Step 3: Check Status

```bash
Invoke-RestMethod -Uri "http://localhost:8000/jobs/$JOB_ID"
```

### Step 4: Inspect Artifacts

```bash
docker exec incubrix-seaps3-worker-1 ls "/app/storage/sceneforge-artifacts/jobs/$JOB_ID/"
```

### Step 5: Verify MP4

```bash
docker exec incubrix-seaps3-worker-1 ffprobe -v quiet -print_format json -show_format \
  "/app/storage/sceneforge-artifacts/jobs/$JOB_ID/output.mp4"
```

---

## Detecting Placeholder MP4

**Placeholder:** File size ~1 KB, not playable  
**Real MP4:** File size > 10 KB, H.264/AAC codecs

**Check:**
```bash
# Get file size
docker exec incubrix-seaps3-worker-1 ls -lh "/app/storage/sceneforge-artifacts/jobs/$JOB_ID/output.mp4"

# Use ffprobe
docker exec incubrix-seaps3-worker-1 ffprobe -v error -select_streams v:0 \
  -show_entries stream=codec_name,width,height \
  "/app/storage/sceneforge-artifacts/jobs/$JOB_ID/output.mp4"

# Expected: codec_name=h264, width=1920, height=1080
```

---

## Investigating Subtitle Issues

### Check if Captions are Real

```bash
# View SRT file
docker exec incubrix-seaps3-worker-1 cat "/app/storage/sceneforge-artifacts/jobs/$JOB_ID/captions.srt"

# Should contain actual script text, not "[Placeholder caption]"
```

### Check SRT Validity

```bash
# Verify timecode format
docker exec incubrix-seaps3-worker-1 grep -E "^[0-9]{2}:[0-9]{2}" "/app/storage/sceneforge-artifacts/jobs/$JOB_ID/captions.srt"

# Expected: 00:00:00,000 --> 00:00:02,400
```

---

## Isolating a Failure

### Test TTS Alone

```bash
python -c "
import os
os.environ['TTS_ADAPTER'] = 'mock'
from sceneforge.audio.factory import get_tts_adapter
adapter = get_tts_adapter()
audio = adapter.synthesise('Hello world.')
print(f'Audio bytes: {len(audio)}')
"
```

### Test Rendering Alone

```bash
# Run the render stage directly with mock timeline
from sceneforge.timeline.builder import Timeline, TimelineEntry
from sceneforge.rendering.renderer import render

timeline = Timeline(entries=[...])  # Mock timeline
output_bytes = render(timeline)
print(f'Output bytes: {len(output_bytes)}')
```

### Test Storage Alone

```bash
python -c "
from sceneforge.storage.client import get_storage_client
client = get_storage_client()
client.upload_bytes('test', 'hello.txt', b'world')
content = client.download_bytes('test', 'hello.txt')
assert content == b'world'
print('Storage OK')
"
```

---

## Clean Restart

If tests hang or leave artifacts:

```bash
# Full restart
docker compose down -v
docker compose up -d
Start-Sleep -Seconds 15
docker compose ps

# Clean test database
$env:DATABASE_URL = "sqlite:///C:\test_clean.db"
python -m pytest tests/unit -v
```

---

## Performance Profiling

### Measure Job Duration

```bash
# Add timing to orchestrator logs
# Check metrics.json in artifacts

docker exec incubrix-seaps3-worker-1 cat "/app/storage/sceneforge-artifacts/jobs/$JOB_ID/metrics.json"

# Shows: validate, plan, retrieve, render, qa stage timings
```

### Benchmark FFmpeg

```bash
# Time a rendering operation
time docker exec incubrix-seaps3-worker-1 ffmpeg -i input.mp4 -c:v h264 -c:a aac output.mp4
```

---

## Known Issues & Workarounds

| Issue | Workaround |
|---|---|
| TTS 403 in Docker | Use host_tts + TTS_PRE_GENERATED_PATH |
| MinIO 403 | Use filesystem backend |
| Slow tests | Use SQLite + SKIP_STARTUP_CHECKS=true |
| Stale Docker volumes | `docker compose down -v` |
| Port 8000 already in use | `docker compose ps` then kill conflicting process |

---

**Prepared by:** Kiro AI  
**Last Updated:** 2026-10-20
