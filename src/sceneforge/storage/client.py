"""MinIO-compatible S3 object storage client wrapper.

All file operations go through this module. The API and worker never write
to the local filesystem for user data — everything goes to MinIO/S3.
"""

from __future__ import annotations

import io
import os
from typing import BinaryIO, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from sceneforge.storage.paths import BUCKET_ARTIFACTS, BUCKET_CACHE, BUCKET_UPLOADS


def _build_client() -> "boto3.client":
    endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    # Ensure endpoint has a scheme
    if not endpoint.startswith("http"):
        use_ssl = os.getenv("MINIO_USE_SSL", "false").lower() == "true"
        endpoint = ("https://" if use_ssl else "http://") + endpoint

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("MINIO_ROOT_USER", "test"),
        aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "test"),
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
            s3={
                "addressing_style": "path",       # S3Mock requires path-style
                "payload_signing_enabled": False,  # disable chunked transfer
            },
        ),
        region_name="us-east-1",
    )


class StorageClient:
    """Thin wrapper around boto3 S3 client targeting a MinIO instance."""

    def __init__(self, client: Optional["boto3.client"] = None) -> None:
        self._client = client or _build_client()

    # ------------------------------------------------------------------
    # Bucket management
    # ------------------------------------------------------------------

    def ensure_buckets(self) -> None:
        """Create required buckets if they do not already exist."""
        for bucket in (BUCKET_UPLOADS, BUCKET_ARTIFACTS, BUCKET_CACHE):
            try:
                self._client.head_bucket(Bucket=bucket)
            except ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code in ("404", "NoSuchBucket"):
                    self._client.create_bucket(Bucket=bucket)
                else:
                    raise

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Upload raw bytes to *bucket/key*."""
        self._client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def upload_fileobj(
        self,
        bucket: str,
        key: str,
        fileobj: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Stream a file-like object to *bucket/key*."""
        self._client.upload_fileobj(
            fileobj,
            bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    def upload_file(
        self,
        bucket: str,
        key: str,
        local_path: str,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Upload a local file to *bucket/key*."""
        self._client.upload_file(
            local_path,
            bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download_bytes(self, bucket: str, key: str) -> bytes:
        """Download an object and return its bytes."""
        response = self._client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def download_fileobj(self, bucket: str, key: str, fileobj: BinaryIO) -> None:
        """Stream an object into a file-like object."""
        self._client.download_fileobj(bucket, key, fileobj)

    def object_exists(self, bucket: str, key: str) -> bool:
        """Return True if the object exists."""
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise

    # ------------------------------------------------------------------
    # Presigned URLs
    # ------------------------------------------------------------------

    def presigned_get_url(
        self,
        bucket: str,
        key: str,
        ttl_seconds: int = 3600,
    ) -> str:
        """Generate a time-limited presigned GET URL."""
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=ttl_seconds,
        )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_object(self, bucket: str, key: str) -> None:
        self._client.delete_object(Bucket=bucket, Key=key)

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_keys(self, bucket: str, prefix: str = "") -> list[str]:
        """Return all object keys under a prefix."""
        paginator = self._client.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys


# ---------------------------------------------------------------------------
# Module-level singleton (lazy-initialised)
# ---------------------------------------------------------------------------

_default_client: Optional["StorageClient"] = None


def get_storage_client():
    """Return the module-level storage client (created on first call).

    When STORAGE_BACKEND=filesystem, returns a FilesystemStorageClient.
    Otherwise returns the S3/MinIO client.
    """
    global _default_client
    if _default_client is None:
        backend = os.getenv("STORAGE_BACKEND", "s3").lower()
        if backend == "filesystem":
            from sceneforge.storage.filesystem_client import FilesystemStorageClient
            _default_client = FilesystemStorageClient()
        else:
            _default_client = StorageClient()
    return _default_client


def reset_storage_client(client=None) -> None:
    """Replace the module-level client (used in tests)."""
    global _default_client
    _default_client = client
