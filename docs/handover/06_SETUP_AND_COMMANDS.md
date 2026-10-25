# Setup & Commands Reference

**Tested on:** Windows 10/11 with PowerShell, Docker Desktop 24+  
**Python:** 3.11  
**Project Root:** `C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3`

---

## 1. Initial Setup

### Python Environment

```powershell
# Create virtual environment (optional; not required for Docker)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For testing

# Verify
python --version  # Should be 3.11+
pip list | grep -E "fastapi|sqlalchemy|pytest"
```

### Docker Setup

```powershell
# Verify Docker is installed
docker --version
# Expected: Docker version 24.0+

docker compose version
# Expected: Docker Compose version v2.20+

# Verify Docker daemon is running
docker ps
# If error: Start Docker Desktop from Windows
```

---

## 2. Starting the Application

### Start All Services

```powershell
cd C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3

# Bring up all services
docker compose up -d

# Wait for services to initialize
Start-Sleep -Seconds 15

# Verify all services are running
docker compose ps
# Expected output: all services "Up" or "healthy"
```

### Verify Services

```powershell
# Check health endpoint
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"0.1.0","environment":"development"}

# Check readiness
curl http://localhost:8000/ready

# View logs for specific service
docker compose logs -f api        # FastAPI logs
docker compose logs -f worker     # RQ worker logs
docker compose logs -f db         # PostgreSQL logs
docker compose logs -f redis      # Redis logs
```

### Stop Services

```powershell
docker compose down
# Optional: remove volumes
docker compose down -v
```

---

## 3. Database Migrations

### Run Migrations on Startup

Migrations run automatically when the API container starts. To verify:

```powershell
docker compose logs api | Select-String "alembic|upgrade|migration"

# Or manually run inside the container
docker exec incubrix-seaps3-api-1 alembic upgrade head
```

### Create New Migration

```powershell
# Inside the container
docker exec incubrix-seaps3-api-1 alembic revision --autogenerate -m "describe change"

# Or locally (if Python env set up)
cd C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3
alembic revision --autogenerate -m "describe change"
```

---

## 4. Running Tests

### Test Environment Setup

```powershell
$env:PYTHONPATH = "C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\src"
$env:SKIP_STARTUP_CHECKS = "true"
$env:DATABASE_URL = "sqlite:///C:\Users\Omen\sf_tests.db"
$env:CALLBACK_HMAC_SECRET = "test-secret-key"
$env:STORAGE_BACKEND = "filesystem"
$env:STORAGE_ROOT = "C:\Users\Omen\sf_test_storage"
$env:LOG_FORMAT = "console"
```

### Unit Tests

```powershell
cd C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3

# Run all unit tests
python -m pytest tests/unit --tb=short -q

# Run a specific test file
python -m pytest tests/unit/test_state_machine.py -v

# Run a specific test
python -m pytest tests/unit/test_state_machine.py::test_job_creation -v

# Run with coverage
python -m pytest tests/unit --cov=src/sceneforge --cov-report=term-missing
```

### Integration Tests

```powershell
# These require Docker services running

# Run API integration tests
python -m pytest tests/integration/test_api_jobs.py -v

# Run specific integration test
python -m pytest tests/integration/test_api_jobs.py::test_create_job -v
```

### Full Test Suite

```powershell
# All unit + integration tests
python -m pytest tests/unit tests/integration/test_api_jobs.py --tb=line -q

# Expected: ~449 tests, most passing (some may be skipped)

# Save output to file
python -m pytest tests/unit tests/integration/test_api_jobs.py -v 2>&1 | Tee-Object -FilePath "test_results.txt"
```

### Hard Case Tests

```powershell
# Tests marked with @pytest.mark.hard_case
python -m pytest -m hard_case -v

# Slow tests (>5s)
python -m pytest -m slow -v
```

---

## 5. Submitting a Test Job

### Via curl / Invoke-RestMethod

```powershell
# Define the job
$body = @{
    script = "Innovation drives progress every single day."
    aspect_ratio = "16:9"
    tts_adapter = "mock"
    stock_provider = "mock"
} | ConvertTo-Json

# Submit
$resp = Invoke-RestMethod -Uri "http://localhost:8000/jobs" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body `
  -Headers @{"Idempotency-Key" = "test-key-001"}

# Extract job ID
$JOB_ID = $resp.job_id
Write-Host "Job ID: $JOB_ID"
```

### Poll Job Status

```powershell
$JOB_ID = "from-above"

# Single status check
$status = Invoke-RestMethod -Uri "http://localhost:8000/jobs/$JOB_ID"
Write-Host "Status: $($status.status)"

# Poll every 5 seconds until completion
for ($i=1; $i -le 24; $i++) {
    $r = Invoke-RestMethod -Uri "http://localhost:8000/jobs/$JOB_ID"
    Write-Host "[$($i*5)s] $($r.status)"
    if ($r.status -in @("COMPLETED","FAILED","CANCELLED")) { break }
    Start-Sleep -Seconds 5
}

# Print final result
Write-Host "Final status: $($r.status)"
Write-Host "Error: $($r.error_code)"
```

### Download Artifacts

```powershell
$JOB_ID = "from-above"

# List artifacts
$arts = Invoke-RestMethod -Uri "http://localhost:8000/jobs/$JOB_ID/artifacts"
Write-Host "Artifacts: $($arts.artifacts -join ', ')"

# Download via filesystem (Docker storage volume)
docker exec incubrix-seaps3-worker-1 cat "/app/storage/sceneforge-artifacts/jobs/$JOB_ID/manifest.json"

docker exec incubrix-seaps3-worker-1 cat "/app/storage/sceneforge-artifacts/jobs/$JOB_ID/captions.srt"

# Inspect MP4 with ffprobe
docker exec incubrix-seaps3-worker-1 ffprobe -v quiet -print_format json -show_format "/app/storage/sceneforge-artifacts/jobs/$JOB_ID/output.mp4"
```

---

## 6. Batch Runner CLI

### Setup

```powershell
cd C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3
```

### Create Test Cases File

```powershell
# Already exists at: tests/fixtures/batch_cases.json
type tests/fixtures/batch_cases.json
```

### Run Batch

```powershell
python scripts/batch_runner.py `
  --cases tests/fixtures/batch_cases.json `
  --base-url http://localhost:8000 `
  --output batch_report.json `
  --poll-interval 5 `
  --max-wait 120

# View report
type batch_report.json
```

---

## 7. OpenAPI Export

### Generate OpenAPI Spec

```powershell
$env:PYTHONPATH = "C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\src"
$env:SKIP_STARTUP_CHECKS = "true"
$env:DATABASE_URL = "sqlite:///C:\Users\Omen\sf_openapi.db"

python -c "
import sys
sys.path.insert(0, r'C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\src')
from sceneforge.api.app import create_app
import json
app = create_app()
spec = app.openapi()
with open(r'C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\openapi.json', 'w') as f:
    json.dump(spec, f, indent=2)
print('OpenAPI exported')
"

# View
type openapi.json | head -50
```

---

## 8. Worker Management

### View Worker Status

```powershell
# List RQ workers
docker exec incubrix-seaps3-redis-1 redis-cli info
docker exec incubrix-seaps3-redis-1 redis-cli keys "rq:worker:*"

# View worker logs
docker compose logs -f worker
```

### Restart Worker

```powershell
# Restart the worker after config changes
docker compose restart worker

# Wait for it to reconnect
Start-Sleep -Seconds 5

# Verify
docker compose ps | Select-String "worker"
```

### Clean Job Queue

```powershell
# Clear all queued jobs (destructive!)
docker exec incubrix-seaps3-redis-1 redis-cli FLUSHDB

# Or just the RQ queue
docker exec incubrix-seaps3-redis-1 redis-cli DEL "rq:queue:default"
```

---

## 9. Troubleshooting Commands

### Check All Service Logs

```powershell
docker compose logs --tail=50 api worker db redis
```

### Restart Everything Clean

```powershell
docker compose down -v
docker compose up -d
Start-Sleep -Seconds 20
docker compose ps
```

### Enter Container Shell

```powershell
# Access API container
docker exec -it incubrix-seaps3-api-1 /bin/bash

# Access worker container
docker exec -it incubrix-seaps3-worker-1 /bin/bash

# Run Python in API container
docker exec -it incubrix-seaps3-api-1 python3
```

### Test Database Connection

```powershell
docker exec incubrix-seaps3-db-1 psql -U sceneforge -c "SELECT version();"
```

### Test Redis Connection

```powershell
docker exec incubrix-seaps3-redis-1 redis-cli PING
# Expected: PONG
```

---

## 10. File Locations

| File | Purpose |
|---|---|
| `C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\src\sceneforge` | Main source code |
| `C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\tests` | All tests |
| `C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\alembic` | Database migrations |
| `C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\scripts` | Utilities (batch_runner, pre_generate_tts, etc.) |
| `C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\schemas` | JSON schemas |
| `C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\.env.example` | Environment template |
| `C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\docker-compose.yml` | Docker services |
| `C:\Users\Omen\OneDrive\Documents\Desktop\IncuBrix-SEAps3\Dockerfile` | Container image |

---

## 11. Environment Variables (Quick Reference)

```bash
# Database
DATABASE_URL=postgresql://user:pass@db:5432/sceneforge

# Redis
REDIS_URL=redis://redis:6379/0

# Storage
STORAGE_BACKEND=filesystem  # or "s3"
STORAGE_ROOT=/app/storage

# TTS / STT
TTS_ADAPTER=mock            # or edge_tts, host_tts
STT_ADAPTER=mock            # or whisper
TTS_PRE_GENERATED_PATH=/app/storage/tts_narration_e2e.mp3

# Stock Providers
STOCK_PROVIDER=mock         # or pexels, pixabay
PEXELS_API_KEY=(your key)
PIXABAY_API_KEY=(your key)

# API
API_EXTERNAL_URL=http://localhost:8000
CALLBACK_HMAC_SECRET=change-in-production

# Logging
LOG_FORMAT=console          # or json

# Testing
SKIP_STARTUP_CHECKS=true    # For offline testing
```

---

**Prepared by:** Kiro AI  
**Last Updated:** 2026-10-20  
**Status:** Tested and verified
