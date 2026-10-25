# Environment & Secrets Management

---

## Environment Variables (Complete Reference)

### Required for Docker Compose

These are already set in `.env.example`:

```bash
POSTGRES_PASSWORD=change_me_in_production
POSTGRES_USER=sceneforge
POSTGRES_DB=sceneforge

REDIS_PASSWORD=

MINIO_ROOT_USER=test
MINIO_ROOT_PASSWORD=test
```

### Optional: Adapter Selection

```bash
# TTS Adapter (default: mock)
TTS_ADAPTER=mock          # Silent WAV
TTS_ADAPTER=edge_tts      # Azure TTS (network required, blocked in Docker)
TTS_ADAPTER=host_tts      # Pre-generated MP3 (Docker-friendly)
TTS_PRE_GENERATED_PATH=/app/storage/tts_narration_e2e.mp3  # For host_tts

# STT Adapter (default: mock)
STT_ADAPTER=mock          # Silent
STT_ADAPTER=whisper       # Not implemented yet

# Stock Provider (default: mock)
STOCK_PROVIDER=mock       # Programmatic cards
STOCK_PROVIDER=pexels     # Requires PEXELS_API_KEY
STOCK_PROVIDER=pixabay    # Requires PIXABAY_API_KEY

PEXELS_API_KEY=(your key, optional)
PIXABAY_API_KEY=(your key, optional)
```

### Storage Configuration

```bash
STORAGE_BACKEND=filesystem         # Current default
STORAGE_BACKEND=s3                 # Alternative (blocked)
STORAGE_ROOT=/app/storage          # Filesystem path

MINIO_ENDPOINT=http://minio:9090
MINIO_USE_SSL=false
```

### API Configuration

```bash
API_EXTERNAL_URL=http://localhost:8000
CALLBACK_HMAC_SECRET=change-in-production    # For webhook signing
LOG_FORMAT=console                            # or json
```

### Database

```bash
DATABASE_URL=postgresql://sceneforge:password@db:5432/sceneforge
SKIP_STARTUP_CHECKS=true          # For offline testing
```

### Testing

```bash
DATABASE_URL=sqlite:///C:\path\to\test.db    # For local tests
SKIP_STARTUP_CHECKS=true
CALLBACK_HMAC_SECRET=test
STORAGE_BACKEND=filesystem
STORAGE_ROOT=C:\path\to\test_storage
LOG_FORMAT=console
```

---

## How to Set Environment Variables

### On Windows (PowerShell)

```powershell
# Set for current session
$env:TTS_ADAPTER = "mock"
$env:STORAGE_BACKEND = "filesystem"

# Verify
Write-Host $env:TTS_ADAPTER

# For persistent use, add to .env file or system environment
```

### In Docker Compose

```yaml
environment:
  TTS_ADAPTER: host_tts
  STORAGE_BACKEND: filesystem
  STORAGE_ROOT: /app/storage
  TTS_PRE_GENERATED_PATH: /app/storage/tts_narration_e2e.mp3
```

Restart containers after changing:
```bash
docker compose down
docker compose up -d
```

---

## Secrets Management

### DO NOT COMMIT

Never add to Git:
- `.env` (contains secrets)
- AWS credentials
- API keys
- Passwords

Use `.gitignore`:
```
.env
.env.local
*.key
secrets/
__pycache__/
.venv/
```

### REFERENCE `.env.example`

Always keep `.env.example` with defaults:
```bash
# This file is safe to commit — it has dummy values
POSTGRES_PASSWORD=change_me_in_production
PEXELS_API_KEY=
PIXABAY_API_KEY=
```

### FOR PRODUCTION

1. Copy `.env.example` to `.env`
2. Fill in real values
3. Keep `.env` in secure location (never Git)
4. Pass via Docker secrets or environment on startup:

```bash
docker run \
  -e DATABASE_URL="postgresql://user:real_pass@host/db" \
  -e PEXELS_API_KEY="your_real_key" \
  sceneforge:latest
```

---

## Configuration by Deployment Context

### Local Development

```bash
TTS_ADAPTER=mock
STOCK_PROVIDER=mock
STORAGE_BACKEND=filesystem
DATABASE_URL=sqlite:///./test.db
SKIP_STARTUP_CHECKS=false
LOG_FORMAT=console
```

### Docker Compose (Dev)

```bash
TTS_ADAPTER=host_tts
TTS_PRE_GENERATED_PATH=/app/storage/tts_narration_e2e.mp3
STOCK_PROVIDER=mock
STORAGE_BACKEND=filesystem
DATABASE_URL=postgresql://sceneforge:password@db:5432/sceneforge
REDIS_URL=redis://redis:6379/0
LOG_FORMAT=json
```

### Docker Compose (With APIs)

```bash
TTS_ADAPTER=edge_tts            # If network access available
STOCK_PROVIDER=pexels            # Requires PEXELS_API_KEY
PEXELS_API_KEY=your_key_here
DATABASE_URL=postgresql://sceneforge:prod_pass@db:5432/sceneforge
```

### Production (Kubernetes / Cloud)

```bash
TTS_ADAPTER=edge_tts            # Or managed TTS service
STOCK_PROVIDER=pexels
STORAGE_BACKEND=s3              # AWS S3 or similar
STORAGE_ROOT=s3://bucket-name/
MINIO_ENDPOINT=https://minio.prod.example.com
CALLBACK_HMAC_SECRET=secure_production_secret
LOG_FORMAT=json
```

---

## Verifying Configuration

### Test TTS

```bash
python -c "
import os
os.environ['TTS_ADAPTER'] = 'mock'
from sceneforge.audio.factory import get_tts_adapter
adapter = get_tts_adapter()
print(f'TTS: {adapter.adapter_name}')
print(f'Is mock: {adapter.is_mock}')
"
```

### Test Storage

```bash
python -c "
import os
os.environ['STORAGE_BACKEND'] = 'filesystem'
os.environ['STORAGE_ROOT'] = '/tmp/test_storage'
from sceneforge.storage.client import get_storage_client
client = get_storage_client()
client.upload_bytes('test-bucket', 'test.txt', b'hello')
print('Storage OK')
"
```

### Test Database

```bash
python -c "
from sceneforge.schemas.database import get_session
with get_session() as session:
    from sceneforge.jobs.repository import JobRepository
    repo = JobRepository(session)
    jobs = repo.list_jobs()
    print(f'Database OK: {len(jobs)} jobs')
"
```

---

## Troubleshooting Configuration

### API doesn't start

1. Check `.env` is copied from `.env.example`
2. Verify DATABASE_URL format
3. Check Docker network connectivity
4. View logs: `docker compose logs api`

### TTS silent

- `TTS_ADAPTER=mock` always produces silent WAV (correct)
- `TTS_ADAPTER=host_tts` requires `TTS_PRE_GENERATED_PATH` set and file present
- If `host_tts` and path missing, falls back to mock gracefully

### Storage not persisting

- Verify `STORAGE_BACKEND=filesystem`
- Verify `STORAGE_ROOT` is writable
- Verify Docker volume mounted: `docker compose ps` shows volume

### Slow tests

- Set `SKIP_STARTUP_CHECKS=true` for unit tests
- Use SQLite (not PostgreSQL) for local testing
- Tests access I/O; disk speed affects runtime

---

## Advanced: Custom Adapters

To add a new TTS adapter:

1. Create `src/sceneforge/audio/adapters/my_tts.py`
2. Implement `TTSAdapter` interface
3. Update `audio/factory.py`:
   ```python
   if name == "my_tts":
       from sceneforge.audio.adapters.my_tts import MyTTSAdapter
       return MyTTSAdapter()
   ```
4. Set `TTS_ADAPTER=my_tts`

Same pattern for storage backends, stock providers, etc.

---

**Prepared by:** Kiro AI  
**Last Updated:** 2026-10-20
