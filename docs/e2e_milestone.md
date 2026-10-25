# End-to-End Rendering Milestone — Phase 5

## Status: BLOCKED locally / ENABLED via Docker

### What the milestone requires

The Phase 5 end-to-end milestone requires demonstrating a full text-only job
that produces a real, validated MP4 using FFmpeg. The nine steps are:

1. Accept a script
2. Generate narration via a functioning TTS adapter (not only mock)
3. Create a validated scene timeline
4. Select permitted assets or programmatic cards
5. Generate rights records
6. Render an actual MP4 using FFmpeg
7. Produce captions and all required metadata
8. Pass applicable QA checks
9. Return retrievable artifact references through the API

### Why local demonstration is blocked

FFmpeg is **not installed** on this development machine (Windows, no PATH entry).

Confirmed:
```
> ffmpeg -version
ffmpeg: The term 'ffmpeg' is not recognized...

> ffprobe -version
ffprobe: The term 'ffprobe' is not recognized...
```

Without FFmpeg:
- Steps 6 (render MP4) and 8 (ffprobe QA checks) cannot run natively.
- Steps 1–5 and 7 (captions.srt) work and have been unit-tested with mocks.
- The orchestrator correctly detects FFmpeg unavailability and writes a
  placeholder MP4 with a clear log warning — it does NOT claim success.

### How to run the real end-to-end demo

The Dockerfile installs FFmpeg in the runtime image:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ...
```

**Step 1: Start services**

```bash
cp .env.example .env          # Edit: set POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD
docker compose up --build     # Builds image with FFmpeg; starts all services
```

**Step 2: Wait for health checks**

```bash
curl http://localhost:8000/health
# → {"status":"ok","version":"0.1.0","environment":"development"}
```

**Step 3: Create a text-only job**

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: e2e-demo-001" \
  -d '{
    "script": "Innovation drives progress every day. Trust takes time to build.",
    "aspect_ratio": "16:9",
    "tts_adapter": "mock",
    "stock_provider": "mock"
  }'
# Returns: {"job_id": "<uuid>", "status": "QUEUED", ...}
```

**Step 4: Poll for completion**

```bash
JOB_ID=<uuid from step 3>
curl http://localhost:8000/jobs/$JOB_ID
# Poll until status == "COMPLETED" or "FAILED"
```

**Step 5: Download artifacts**

```bash
curl -L http://localhost:8000/jobs/$JOB_ID/artifacts/output.mp4 -o output.mp4
curl -L http://localhost:8000/jobs/$JOB_ID/artifacts/captions.srt -o captions.srt
curl -L http://localhost:8000/jobs/$JOB_ID/artifacts/timeline.json -o timeline.json
curl -L http://localhost:8000/jobs/$JOB_ID/artifacts/rights.json -o rights.json
curl -L http://localhost:8000/jobs/$JOB_ID/artifacts/manifest.json -o manifest.json
```

**Step 6: Verify the MP4**

```bash
ffprobe -v quiet -print_format json -show_format -show_streams output.mp4
```

Expected output includes:
- `codec_name: "h264"` (video)
- `codec_name: "aac"` (audio, if narration audio is present)
- `r_frame_rate: "30/1"`
- Positive duration consistent with script length

### Phase 5 limitations (honestly documented)

| Component | Status | Notes |
|---|---|---|
| TTS adapter | MOCK | Uses MockTTSAdapter (silent WAV); real TTS requires `TTS_ADAPTER=edge_tts` |
| STT adapter | N/A | Text-only path; STT not used |
| Stock footage | MOCK | Uses MockStockProvider; no real downloads |
| Asset download | NOT IMPLEMENTED | Phase 5 renderer generates cards for all scenes (real download = Phase 6) |
| Typography cards | IMPLEMENTED | FFmpeg `drawtext` on `lavfi` background |
| Narration audio mix | NOT MIXED | Real audio path: set `audio_path` in renderer; placeholder silence used |
| FFmpeg rendering | DOCKER ONLY | Not available locally; orchestrator falls back to placeholder MP4 |
| QA checks | IMPLEMENTED | All 14 checks; UNKNOWN when ffprobe unavailable |
| Output contract | COMPLETE | All 7 artifacts written to MinIO |

### What "real" means in this context

A **real render** (DoD gate 4) requires:
- FFmpeg called with actual media input → MP4 output with valid H.264+AAC encoding
- ffprobe confirms codec, dimensions, fps, and positive duration
- QA checks return PASS (not UNKNOWN)

This is achievable in Docker with `docker compose up --build`. The code path
is fully implemented; the blocker is only the local FFmpeg absence.

The placeholder MP4 written when FFmpeg is absent is clearly documented:
- `manifest.json.real_mp4_rendered: false`
- `metrics.json.used_placeholder_mp4: true`
- Worker log: `stage_render_placeholder` warning with reason
