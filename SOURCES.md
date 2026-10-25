# Sources and Attributions
## SceneForge AI — IncuBrix SEA PS3

All external libraries, models, media providers, media assets, and datasets used in this
project are listed below with version, source, and licence information.

> **Last Updated**: Phase 1
> **Status**: DRAFT — to be updated as each phase introduces new dependencies.

---

## 1. Python Libraries (Backend)

| Library | Version | Source | Licence | Use |
|---|---|---|---|---|
| fastapi | ≥0.111.0 | https://github.com/tiangolo/fastapi | MIT | HTTP API framework |
| pydantic | ≥2.0 | https://github.com/pydantic/pydantic | MIT | Request/response validation |
| sqlalchemy | ≥2.0 | https://github.com/sqlalchemy/sqlalchemy | MIT | ORM |
| alembic | latest | https://github.com/sqlalchemy/alembic | MIT | DB migrations |
| redis | ≥5.0 | https://github.com/redis/redis-py | MIT | Queue + idempotency |
| rq | ≥1.16 | https://github.com/rq/rq | BSD-2-Clause | Background job processing |
| boto3 | latest | https://github.com/boto/boto3 | Apache 2.0 | MinIO/S3 object storage |
| structlog | latest | https://github.com/hynek/structlog | Apache 2.0 / MIT | Structured JSON logging |
| pytest | latest | https://github.com/pytest-dev/pytest | MIT | Test framework |
| pytest-asyncio | latest | https://github.com/pytest-dev/pytest-asyncio | Apache 2.0 | Async test support |
| httpx | latest | https://github.com/encode/httpx | BSD-3-Clause | Test HTTP client |
| uvicorn | latest | https://github.com/encode/uvicorn | BSD-3-Clause | ASGI server |
| python-multipart | latest | https://github.com/andrew-d/python-multipart | Apache 2.0 | File upload handling |
| psycopg2-binary | latest | https://github.com/psycopg/psycopg2 | LGPL-3.0 | PostgreSQL driver |

---

## 2. AI/ML Libraries and Models

| Component | Version | Source | Licence | Use |
|---|---|---|---|---|
| openai-whisper | latest | https://github.com/openai/whisper | MIT | Local speech-to-text (STT) |
| Whisper `base` model weights | — | Downloaded by openai-whisper | MIT | STT model (74 MB) |
| sentence-transformers | latest | https://github.com/UKPLab/sentence-transformers | Apache 2.0 | Text/caption embeddings |
| `all-MiniLM-L6-v2` model | — | https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 | Apache 2.0 | Embedding model (80 MB) |
| torch | ≥2.0 | https://github.com/pytorch/pytorch | BSD-3-Clause | Whisper + sentence-transformers runtime |
| edge-tts | latest | https://github.com/rany2/edge-tts | GPL-3.0 | TTS via Edge browser endpoint |
| transformers | latest | https://github.com/huggingface/transformers | Apache 2.0 | Optional model utilities |

> **Notes on edge-tts**: Uses Microsoft Edge's online TTS service via an unofficial API.
> Licence of the Python package is GPL-3.0. Terms of use of the underlying Microsoft service
> should be verified before deployment outside of assessment/demo context.
> Alternative: Coqui TTS (Mozilla Public Licence / Apache 2.0 depending on model).

---

## 3. Media Processing

| Component | Version | Source | Licence | Use |
|---|---|---|---|---|
| FFmpeg | 6.x | https://ffmpeg.org | LGPL-2.1 + GPL components | Video rendering, card generation, inspection |
| libx264 | — | https://www.videolan.org/developers/x264.html | GPL-2.0 | H.264 video encoding |
| ffprobe | 6.x (bundled with FFmpeg) | https://ffmpeg.org | LGPL-2.1 | Media inspection, QA checks |

> **FFmpeg licence note**: The Dockerfile uses the Debian system package (`apt-get install ffmpeg`)
> which includes libx264 (GPL-2.0). The combined binary is subject to GPL-2.0.
> This is acceptable for the assessment submission; review before commercial deployment.

**Rendering modules implemented in Phase 5:**
- `rendering/ffprobe.py` — subprocess wrapper, argument arrays, timeout
- `rendering/subtitle_writer.py` — SRT generation and validation
- `rendering/card_generator.py` — FFmpeg lavfi + drawtext for typography/data cards
- `rendering/reframer.py` — portrait reframing (center-crop, blurred-pad)
- `rendering/normaliser.py` — pixel format, audio loudness (EBU R128 loudnorm)
- `rendering/cache.py` — content-addressed incremental render cache
- `rendering/renderer.py` — H.264/AAC MP4 assembly via FFmpeg concat demuxer
- `quality/checker.py` — 14-check QA runner (PASS/FAIL/UNKNOWN outcomes)

---

## 4. Frontend Libraries

| Library | Version | Source | Licence | Use |
|---|---|---|---|---|
| react | 18.x | https://github.com/facebook/react | MIT | UI framework |
| react-dom | 18.x | https://github.com/facebook/react | MIT | DOM rendering |
| vite | 5.x | https://github.com/vitejs/vite | MIT | Build tool |
| typescript | 5.x | https://github.com/microsoft/TypeScript | Apache 2.0 | Type safety |
| tailwindcss | 3.x | https://github.com/tailwindlabs/tailwindcss | MIT | Utility CSS |
| @tanstack/react-query | latest | https://github.com/TanStack/query | MIT | API state management |
| axios | latest | https://github.com/axios/axios | MIT | HTTP client |

---

## 5. Infrastructure

| Component | Version | Source | Licence | Use |
|---|---|---|---|---|
| PostgreSQL | 15 | https://www.postgresql.org | PostgreSQL | Relational database |
| Redis | 7 | https://redis.io | BSD-3-Clause | Queue + cache |
| MinIO | latest | https://min.io | AGPL-3.0 | Object storage |
| Docker | ≥24.0 | https://www.docker.com | Apache 2.0 | Containerisation |
| Docker Compose | v2 | https://github.com/docker/compose | Apache 2.0 | Multi-service orchestration |
| Nginx | alpine | https://nginx.org | BSD-2-Clause | Frontend static server |

> **MinIO licence note**: MinIO is AGPL-3.0. In this project it is used as a service within
> Docker Compose (not linked or distributed with the application code). This is within the
> terms of AGPL for the assessment context. Production deployment using MinIO as a service
> must be reviewed against AGPL requirements.

---

## 6. Media Providers

| Provider | Type | Licence | Registration | Use |
|---|---|---|---|---|
| Pexels | Stock video/image | Pexels Licence (free commercial use, no attribution required) | Free account + API key at https://www.pexels.com/api/ | Primary stock footage provider (feature-flagged) |
| Pixabay | Stock video footage | Pixabay Content Licence (free commercial use) | Free account + API key at https://pixabay.com/api/docs/ (uses `https://pixabay.com/api/videos/`) | Primary genuine stock video provider (SHA-256 verified) |

> **Generated-visual provider**: No production generative video provider is integrated.
> The `MockGeneratedProvider` is the only available implementation (clearly labelled as mock).
> An end-to-end test with real generated output does not exist. This is documented honestly.
> If a generative provider is added in a future phase, it will require API key configuration
> and a passing end-to-end test before any compliance claim is made.

> **Media asset rights**: Individual assets retrieved from Pexels and Pixabay are subject
> to their respective content licences. The Pexels Licence and Pixabay Content Licence both
> permit commercial use. Attribution is not required but is encouraged. Rights records for
> every selected asset are stored in `rights.json` with the licence name, source URL, and
> retrieval timestamp.

---

## 7. Test Fixtures

| Fixture | Description | Source | Licence |
|---|---|---|---|
| `tests/fixtures/silence_5s.wav` | 5-second silent WAV | Generated with FFmpeg `anullsrc` | Public domain (generated) |
| `tests/fixtures/tone_440hz_5s.wav` | 5-second 440 Hz tone (music-only) | Generated with FFmpeg `sine` | Public domain (generated) |
| `tests/fixtures/corrupted.mp4` | Truncated/invalid MP4 bytes | Generated synthetically | Public domain (generated) |
| `tests/fixtures/sample_narration.txt` | Short English narration scripts | Original (written for this project) | Original work |
| `tests/fixtures/batch_cases.yaml` | Batch runner test case definitions | Original (written for this project) | Original work |

All audio and video test fixtures are synthetically generated using FFmpeg or Python.
No copyrighted media files are included in the repository.

---

## 8. Development Tools

| Tool | Source | Use |
|---|---|---|
| VS Code / Kiro IDE | https://kiro.dev | Development environment |
| git | https://git-scm.com | Version control |
| pre-commit | https://pre-commit.com | Git hook management |
| ruff | https://github.com/astral-sh/ruff | Python linter |
| black | https://github.com/psf/black | Python formatter |

---

## 9. Reference Documentation

| Source | URL | Purpose |
|---|---|---|
| FastAPI docs | https://fastapi.tiangolo.com | API framework reference |
| Pydantic v2 docs | https://docs.pydantic.dev/latest | Validation reference |
| Alembic docs | https://alembic.sqlalchemy.org | Migration reference |
| FFmpeg docs | https://ffmpeg.org/documentation.html | Filter graph and codec reference |
| OpenAI Whisper README | https://github.com/openai/whisper | STT model reference |
| sentence-transformers docs | https://www.sbert.net | Embedding model reference |
| Pexels API docs | https://www.pexels.com/api/documentation | Stock provider API reference |
| Pixabay API docs | https://pixabay.com/api/docs | Stock provider API reference |
| OpenAPI 3.1 spec | https://spec.openapis.org/oas/v3.1.0 | API documentation standard |
| SRT subtitle format | https://en.wikipedia.org/wiki/SubRip | Caption format reference |
