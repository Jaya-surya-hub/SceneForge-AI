"""Static file serving for filesystem-backed storage.

When STORAGE_BACKEND=filesystem, artifacts are served directly from the
API container via GET /files/{bucket}/{path}.

This route is only mounted when STORAGE_BACKEND=filesystem.
"""

from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

from sceneforge.schemas.exceptions import NotFoundError

router = APIRouter(prefix="/files", tags=["files"])

_STORAGE_ROOT = os.getenv("STORAGE_ROOT", "/tmp/sceneforge_storage")


@router.get("/{bucket}/{path:path}", summary="Download a stored artifact")
async def get_file(bucket: str, path: str) -> FileResponse:
    """Serve a stored artifact from the filesystem."""
    # Security: prevent path traversal
    safe_path = path.replace("..", "__").lstrip("/")
    full_path = os.path.join(_STORAGE_ROOT, bucket, safe_path)
    if not os.path.isfile(full_path):
        raise NotFoundError("Artifact")
    media_type = None
    if full_path.endswith(".mp4"):
        media_type = "video/mp4"
    elif full_path.endswith(".srt"):
        media_type = "text/plain; charset=utf-8"
    elif full_path.endswith(".json"):
        media_type = "application/json"
    return FileResponse(full_path, media_type=media_type)
