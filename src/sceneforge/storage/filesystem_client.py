"""Filesystem-backed storage client — S3-compatible interface using local disk.

Used when STORAGE_BACKEND=filesystem (the default in Docker Compose when S3
services are unavailable or unreliable). Implements the same interface as the
MinIO/boto3 client so the rest of the application is unchanged.

Files are stored under STORAGE_ROOT (env var, default /tmp/sceneforge_storage).
Presigned URLs are generated as local file:// references; in Docker Compose
they are served by the API's /files/ endpoint.

This is a self-contained implementation with no external dependencies.
"""

from __future__ import annotations

import io
import os
import shutil
from typing import BinaryIO, Optional

from sceneforge.observability.logging import get_logger

log = get_logger(__name__)

_STORAGE_ROOT = os.getenv("STORAGE_ROOT", "/tmp/sceneforge_storage")


class FilesystemStorageClient:
    """Local filesystem implementation of the storage interface."""

    def __init__(self, root: Optional[str] = None) -> None:
        self._root = root or _STORAGE_ROOT
        os.makedirs(self._root, exist_ok=True)

    def _path(self, bucket: str, key: str) -> str:
        # Sanitise to prevent path traversal
        safe_key = key.replace("..", "__").lstrip("/")
        return os.path.join(self._root, bucket, safe_key)

    def ensure_buckets(self) -> None:
        """Create bucket directories."""
        from sceneforge.storage.paths import BUCKET_UPLOADS, BUCKET_ARTIFACTS, BUCKET_CACHE
        for bucket in (BUCKET_UPLOADS, BUCKET_ARTIFACTS, BUCKET_CACHE):
            os.makedirs(os.path.join(self._root, bucket), exist_ok=True)
        log.info("filesystem_storage_buckets_ready", root=self._root)

    def upload_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        path = self._path(bucket, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        log.debug("fs_upload_bytes", bucket=bucket, key=key, size=len(data))

    def upload_fileobj(
        self,
        bucket: str,
        key: str,
        fileobj: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> None:
        path = self._path(bucket, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            shutil.copyfileobj(fileobj, f)

    def upload_file(
        self,
        bucket: str,
        key: str,
        local_path: str,
        content_type: str = "application/octet-stream",
    ) -> None:
        path = self._path(bucket, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copy2(local_path, path)

    def download_bytes(self, bucket: str, key: str) -> bytes:
        path = self._path(bucket, key)
        with open(path, "rb") as f:
            return f.read()

    def download_fileobj(self, bucket: str, key: str, fileobj: BinaryIO) -> None:
        path = self._path(bucket, key)
        with open(path, "rb") as f:
            shutil.copyfileobj(f, fileobj)

    def object_exists(self, bucket: str, key: str) -> bool:
        return os.path.isfile(self._path(bucket, key))

    def presigned_get_url(
        self,
        bucket: str,
        key: str,
        ttl_seconds: int = 3600,
    ) -> str:
        """Return an API-relative URL for artifact download."""
        # The API serves files via /files/{bucket}/{key}
        api_host = os.getenv("API_EXTERNAL_URL", "http://localhost:8000")
        safe_key = key.replace("..", "__")
        return f"{api_host}/files/{bucket}/{safe_key}"

    def delete_object(self, bucket: str, key: str) -> None:
        path = self._path(bucket, key)
        if os.path.isfile(path):
            os.unlink(path)

    def list_keys(self, bucket: str, prefix: str = "") -> list[str]:
        base = os.path.join(self._root, bucket)
        if not os.path.isdir(base):
            return []
        results = []
        for dirpath, _, filenames in os.walk(base):
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, base).replace("\\", "/")
                if rel.startswith(prefix.lstrip("/")):
                    results.append(rel)
        return results
