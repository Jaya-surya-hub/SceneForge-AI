"""Canonical MinIO object-key naming conventions.

All keys are constructed from job UUIDs only — no user-supplied path components.
This prevents path traversal and ensures per-job isolation.

Bucket layout:
    sceneforge-uploads/
        jobs/{job_id}/input/script.txt
        jobs/{job_id}/input/voiceover.{ext}

    sceneforge-artifacts/
        jobs/{job_id}/output.mp4
        jobs/{job_id}/timeline.json
        jobs/{job_id}/manifest.json
        jobs/{job_id}/rights.json
        jobs/{job_id}/captions.srt
        jobs/{job_id}/metrics.json
        jobs/{job_id}/job.log

    sceneforge-cache/
        segments/{cache_key}.mp4
"""

from __future__ import annotations

import os

# Bucket names (configurable via environment)
BUCKET_UPLOADS = os.getenv("MINIO_BUCKET_UPLOADS", "sceneforge-uploads")
BUCKET_ARTIFACTS = os.getenv("MINIO_BUCKET_ARTIFACTS", "sceneforge-artifacts")
BUCKET_CACHE = os.getenv("MINIO_BUCKET_CACHE", "sceneforge-cache")

# Required artifact filenames (matches §5 output contract)
ARTIFACT_NAMES = [
    "output.mp4",
    "timeline.json",
    "manifest.json",
    "rights.json",
    "captions.srt",
    "metrics.json",
    "job.log",
]


def upload_key(job_id: str, filename: str) -> str:
    """Object key for a user upload."""
    return f"jobs/{job_id}/input/{filename}"


def artifact_key(job_id: str, filename: str) -> str:
    """Object key for a generated artifact."""
    return f"jobs/{job_id}/{filename}"


def cache_segment_key(cache_key: str) -> str:
    """Object key for a cached rendered segment."""
    return f"segments/{cache_key}.mp4"


def all_artifact_keys(job_id: str) -> list[str]:
    """Return all expected artifact keys for a completed job."""
    return [artifact_key(job_id, name) for name in ARTIFACT_NAMES]
