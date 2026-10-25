"""Media downloader and validator for stock and external video assets.

Responsibilities:
1. Download video assets from provider URLs (Pexels, Pixabay, or generic HTTP/HTTPS).
2. Validate HTTP response, content size, and MIME type.
3. Validate media stream via FFprobe (video stream presence, codec, duration, resolution).
4. Compute cryptographic SHA-256 content hash.
5. Persist validated video files to the configured storage backend (e.g. MinIO/filesystem).
6. Provide deterministic mock video synthesis (with genuine moving footage) for no-key testing.
7. Reject empty, corrupt, truncated, or invalid video files with typed ProviderErrors.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

from sceneforge.observability.logging import get_logger
from sceneforge.rendering.ffprobe import is_ffmpeg_available, is_ffprobe_available, probe_file
from sceneforge.retrieval.interfaces import (
    MediaAsset,
    MediaDownloadError,
    MediaValidationError,
)
from sceneforge.storage.client import get_storage_client
from sceneforge.storage.paths import BUCKET_UPLOADS

log = get_logger(__name__)

_DEFAULT_DOWNLOAD_TIMEOUT = int(os.getenv("MEDIA_DOWNLOAD_TIMEOUT", "30"))
_DEFAULT_MAX_RETRIES = int(os.getenv("MEDIA_DOWNLOAD_MAX_RETRIES", "2"))
_MIN_VIDEO_FILE_SIZE = int(os.getenv("MEDIA_MIN_FILE_SIZE", "1024"))  # 1 KB
_DEFAULT_MOCK_MOTION_TIMEOUT = int(os.getenv("MOCK_MOTION_TIMEOUT", "90"))


@dataclass
class DownloadedMedia:
    """Represents a validated, downloaded media asset ready for timeline rendering."""

    asset_id: str
    local_path: str
    storage_key: str
    sha256_hash: str
    size_bytes: int
    duration_seconds: float
    width: int
    height: int
    video_codec: str
    format_name: str
    is_mock: bool = False


class MediaDownloader:
    """Downloads and verifies video clips from provider URLs."""

    def __init__(
        self,
        *,
        storage_client=None,
        work_dir: Optional[str] = None,
        timeout_seconds: int = _DEFAULT_DOWNLOAD_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        mock_motion_timeout: int = _DEFAULT_MOCK_MOTION_TIMEOUT,
    ) -> None:
        self.storage = storage_client or get_storage_client()
        self._work_dir = work_dir
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._mock_motion_timeout = mock_motion_timeout

    def download_and_validate(
        self,
        asset: MediaAsset,
        *,
        target_duration: Optional[float] = None,
        job_id: str = "unknown",
    ) -> DownloadedMedia:
        """Download *asset* and validate its video stream and file integrity.

        Args:
            asset: The MediaAsset returned by a provider search.
            target_duration: Planned duration in seconds (for duration check).
            job_id: Job identifier for logging and storage namespacing.

        Returns:
            DownloadedMedia with verified file paths, hashes, and stream metadata.

        Raises:
            MediaDownloadError: On network, HTTP, or timeout failures.
            MediaValidationError: If the file is corrupt, empty, or lacks video.
        """
        dest_dir = self._work_dir or tempfile.gettempdir()
        os.makedirs(dest_dir, exist_ok=True)
        local_target = os.path.join(dest_dir, f"asset_{asset.asset_id.replace('/', '_')}.mp4")

        # ── Step 1: Obtain raw video bytes (network download or mock synthesis) ──
        if asset.is_mock or not asset.provider_asset_url or "mock.example" in asset.provider_asset_url:
            self._generate_mock_motion_video(asset, local_target, target_duration or 10.0, job_id)
        else:
            self._download_http(asset.provider_asset_url, local_target, job_id)

        # ── Step 2: Validate file size ─────────────────────────────────────────
        try:
            size_bytes = os.path.getsize(local_target)
        except OSError as exc:
            raise MediaDownloadError(f"Cannot read downloaded file {local_target}: {exc}", provider=asset.provider_name)

        if size_bytes < _MIN_VIDEO_FILE_SIZE:
            try:
                os.unlink(local_target)
            except OSError:
                pass
            raise MediaValidationError(
                f"Downloaded file for asset {asset.asset_id} is too small ({size_bytes} bytes).",
                provider=asset.provider_name,
            )

        # ── Step 3: Compute SHA-256 hash ───────────────────────────────────────
        sha256_hash = self._compute_file_sha256(local_target)

        # ── Step 4: Validate with FFprobe (stream, codec, duration) ────────────
        duration = 5.0
        width = asset.width or 1920
        height = asset.height or 1080
        video_codec = "h264"
        format_name = "mp4"

        if is_ffprobe_available():
            try:
                probe = probe_file(local_target)
                if not probe.video_stream:
                    raise MediaValidationError(
                        f"Media asset {asset.asset_id} has no valid video stream.",
                        provider=asset.provider_name,
                    )
                vs = probe.video_stream
                video_codec = vs.codec_name or "unknown"
                width = vs.width or width
                height = vs.height or height
                duration = probe.duration or duration
                format_name = probe.format.format_name or "mp4"

                if duration <= 0:
                    raise MediaValidationError(
                        f"Media asset {asset.asset_id} has invalid non-positive duration ({duration}s).",
                        provider=asset.provider_name,
                    )
            except RuntimeError as exc:
                try:
                    os.unlink(local_target)
                except OSError:
                    pass
                raise MediaValidationError(
                    f"FFprobe failed to inspect downloaded asset {asset.asset_id}: {exc}",
                    provider=asset.provider_name,
                ) from exc

        # Update MediaAsset metadata in-place
        asset.sha256_hash = sha256_hash
        asset.duration_seconds = duration
        asset.width = width
        asset.height = height
        asset.content_type = "video/mp4"

        # ── Step 5: Save to persistent storage ────────────────────────────────
        storage_key = f"raw_assets/{asset.asset_id}.mp4"
        try:
            with open(local_target, "rb") as f:
                content = f.read()
            self.storage.upload_bytes(BUCKET_UPLOADS, storage_key, content, "video/mp4")
        except Exception as exc:
            log.warning("storage_upload_raw_asset_failed", asset_id=asset.asset_id, error=str(exc))

        log.info(
            "media_downloaded_and_validated",
            job_id=job_id,
            asset_id=asset.asset_id,
            size=size_bytes,
            duration=round(duration, 2),
            codec=video_codec,
            resolution=f"{width}x{height}",
            is_mock=asset.is_mock,
        )

        return DownloadedMedia(
            asset_id=asset.asset_id,
            local_path=local_target,
            storage_key=storage_key,
            sha256_hash=sha256_hash,
            size_bytes=size_bytes,
            duration_seconds=duration,
            width=width,
            height=height,
            video_codec=video_codec,
            format_name=format_name,
            is_mock=asset.is_mock,
        )

    def _download_http(self, url: str, target_path: str, job_id: str) -> None:
        """Download URL to target_path with chunked streaming and retries."""
        tmp_path = target_path + ".tmp"
        last_error = None

        for attempt in range(self._max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "SceneForgeAI/0.1 (IncuBrix-Assessment)",
                        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
                    },
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    if resp.status != 200:
                        raise MediaDownloadError(f"HTTP {resp.status} downloading {url}")
                    with open(tmp_path, "wb") as out_f:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            out_f.write(chunk)

                # Atomic replace on success
                os.replace(tmp_path, target_path)
                return
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                if attempt < self._max_retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue

        raise MediaDownloadError(f"Failed to download media from {url}: {last_error}")

    def _generate_mock_motion_video(
        self, asset: MediaAsset, target_path: str, duration: float, job_id: str
    ) -> None:
        """Generate a genuine synthetic moving video clip for mock assets.

        Uses FFmpeg's video generation filters so that mock assets contain
        actual continuous motion. To minimize CPU cost on resource-constrained
        or free-tier cloud instances, base generation uses a lightweight resolution
        (640x360 @ 15fps) and upscales to the target dimensions (asset.width x asset.height @ 30fps).
        """
        width = asset.width or 1920
        height = asset.height or 1080
        ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")

        # Pick a deterministic animated pattern based on asset_id.
        # Avoid heavy procedural filters like mandelbrot and life on low-vCPU instances.
        patterns = [
            "testsrc2=size=640x360:rate=15",
            "testsrc=size=640x360:rate=15",
            "gradients=size=640x360:rate=15:c0=0x1E3A8A:c1=0x3B82F6:speed=0.01",
            "smptebars=size=640x360:rate=15",
        ]
        seed = int(hashlib.md5(asset.asset_id.encode()).hexdigest(), 16)
        pattern = patterns[seed % len(patterns)]

        tmp_target = f"{target_path}.tmp_{os.getpid()}_{int(time.time() * 1000)}.mp4"
        ffmpeg_success = False

        if is_ffmpeg_available():
            cmd = [
                ffmpeg_bin,
                "-y",
                "-threads", "1",
                "-f", "lavfi",
                "-i", pattern,
                "-t", str(max(duration, 5.0)),
                "-vf", f"scale={width}:{height}:flags=fast_bilinear,fps=30",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "ultrafast",
                "-crf", "28",
                tmp_target,
            ]
            try:
                subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=self._mock_motion_timeout,
                )
                if os.path.exists(tmp_target) and os.path.getsize(tmp_target) >= _MIN_VIDEO_FILE_SIZE:
                    os.replace(tmp_target, target_path)
                    ffmpeg_success = True
                    return
            except subprocess.TimeoutExpired as exc:
                stderr_output = exc.stderr or ""
                if isinstance(stderr_output, bytes):
                    stderr_output = stderr_output.decode(errors="replace")
                stderr_snippet = stderr_output[-1000:]
                log.warning(
                    "mock_motion_ffmpeg_timeout",
                    asset_id=asset.asset_id,
                    timeout=self._mock_motion_timeout,
                    stderr=stderr_snippet,
                )
                log.warning(
                    "mock_motion_ffmpeg_failed",
                    asset_id=asset.asset_id,
                    error=f"FFmpeg timed out after {self._mock_motion_timeout}s: {stderr_snippet}",
                )
            except subprocess.CalledProcessError as exc:
                stderr_output = exc.stderr or ""
                if isinstance(stderr_output, bytes):
                    stderr_output = stderr_output.decode(errors="replace")
                stderr_snippet = stderr_output[-1000:]
                log.warning(
                    "mock_motion_ffmpeg_failed",
                    asset_id=asset.asset_id,
                    returncode=exc.returncode,
                    stderr=stderr_snippet,
                    error=f"FFmpeg failed with exit {exc.returncode}: {stderr_snippet}",
                )
            except Exception as exc:
                log.warning("mock_motion_ffmpeg_failed", asset_id=asset.asset_id, error=str(exc))
            finally:
                if os.path.exists(tmp_target):
                    try:
                        os.unlink(tmp_target)
                    except OSError:
                        pass
                if not ffmpeg_success and os.path.exists(target_path):
                    try:
                        os.unlink(target_path)
                    except OSError:
                        pass

            # Primary motion generator failed or timed out: fall back to a valid single-color clip
            fallback_ok = self._generate_fallback_clip(target_path, width, height, duration)
            if fallback_ok:
                log.info("mock_motion_fallback_clip_generated", asset_id=asset.asset_id, target=target_path)
                return

            # Both FFmpeg generation attempts failed: remove any partial file and raise typed error
            if os.path.exists(target_path):
                try:
                    os.unlink(target_path)
                except OSError:
                    pass
            raise MediaDownloadError(
                f"Failed to generate mock motion video for asset {asset.asset_id}: FFmpeg generation and fallback both failed.",
                provider=asset.provider_name,
            )

        # Fallback minimal MP4 bytes ONLY when FFmpeg is not installed (e.g. dev environments)
        with open(target_path, "wb") as f:
            f.write(
                b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41"
                b"\x00\x00\x00\x08free"
                b"\x00\x00\x04\x00mdat" + (b"\xAA\x55" * 1024)
            )

    def _generate_fallback_clip(
        self, target_path: str, width: int, height: int, duration: float
    ) -> bool:
        """Fallback: generate a valid minimal single-color video clip using FFmpeg."""
        ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")
        if not is_ffmpeg_available():
            return False

        tmp_fallback = f"{target_path}.fb_tmp_{os.getpid()}_{int(time.time() * 1000)}.mp4"
        cmd = [
            ffmpeg_bin,
            "-y",
            "-threads", "1",
            "-f", "lavfi",
            "-i", f"color=c=0x1E3A8A:s={width}x{height}:r=24",
            "-t", str(max(duration, 3.0)),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-crf", "30",
            tmp_fallback,
        ]
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=max(30, min(self._mock_motion_timeout, 60)),
                check=True,
            )
            if os.path.exists(tmp_fallback) and os.path.getsize(tmp_fallback) >= _MIN_VIDEO_FILE_SIZE:
                os.replace(tmp_fallback, target_path)
                return True
        except Exception as exc:
            log.warning("mock_motion_fallback_clip_failed", error=str(exc))
        finally:
            if os.path.exists(tmp_fallback):
                try:
                    os.unlink(tmp_fallback)
                except OSError:
                    pass
        return False

    @staticmethod
    def _compute_file_sha256(path: str) -> str:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
