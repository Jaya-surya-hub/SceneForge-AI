
"""Media downloader and validator for stock and external video assets."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from sceneforge.observability.logging import get_logger
from sceneforge.rendering.ffprobe import (
    is_ffmpeg_available,
    is_ffprobe_available,
    probe_file,
)
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
_MOCK_VIDEO_TIMEOUT = int(os.getenv("MOCK_VIDEO_TIMEOUT", "60"))
_MIN_VIDEO_FILE_SIZE = int(os.getenv("MEDIA_MIN_FILE_SIZE", "1024"))


@dataclass
class DownloadedMedia:
    """A validated media asset ready for timeline rendering."""

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
    ) -> None:
        self.storage = storage_client or get_storage_client()
        self._work_dir = work_dir
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    def download_and_validate(
        self,
        asset: MediaAsset,
        *,
        target_duration: Optional[float] = None,
        job_id: str = "unknown",
    ) -> DownloadedMedia:
        """Download or synthesize a video, validate it, and store it."""
        dest_dir = self._work_dir or tempfile.gettempdir()
        os.makedirs(dest_dir, exist_ok=True)

        safe_asset_id = asset.asset_id.replace("/", "_").replace("\\", "_")
        local_target = os.path.join(dest_dir, f"asset_{safe_asset_id}.mp4")

        if (
            asset.is_mock
            or not asset.provider_asset_url
            or "mock.example" in asset.provider_asset_url
        ):
            self._generate_mock_motion_video(
                asset, local_target, target_duration or 10.0, job_id
            )
        else:
            self._download_http(asset.provider_asset_url, local_target, job_id)

        try:
            size_bytes = os.path.getsize(local_target)
        except OSError as exc:
            raise MediaDownloadError(
                f"Cannot read downloaded file {local_target}: {exc}",
                provider=asset.provider_name,
            ) from exc

        if size_bytes < _MIN_VIDEO_FILE_SIZE:
            try:
                os.unlink(local_target)
            except OSError:
                pass
            raise MediaValidationError(
                f"Downloaded file for asset {asset.asset_id} is too small "
                f"({size_bytes} bytes).",
                provider=asset.provider_name,
            )

        sha256_hash = self._compute_file_sha256(local_target)

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

                stream = probe.video_stream
                video_codec = stream.codec_name or "unknown"
                width = stream.width or width
                height = stream.height or height
                duration = probe.duration or duration
                format_name = probe.format.format_name or "mp4"

                if duration <= 0:
                    raise MediaValidationError(
                        f"Media asset {asset.asset_id} has invalid duration "
                        f"({duration}s).",
                        provider=asset.provider_name,
                    )

            except RuntimeError as exc:
                try:
                    os.unlink(local_target)
                except OSError:
                    pass
                raise MediaValidationError(
                    f"FFprobe failed to inspect asset {asset.asset_id}: {exc}",
                    provider=asset.provider_name,
                ) from exc

        asset.sha256_hash = sha256_hash
        asset.duration_seconds = duration
        asset.width = width
        asset.height = height
        asset.content_type = "video/mp4"

        storage_key = f"raw_assets/{safe_asset_id}.mp4"

        try:
            with open(local_target, "rb") as file:
                content = file.read()
            self.storage.upload_bytes(
                BUCKET_UPLOADS, storage_key, content, "video/mp4"
            )
        except Exception as exc:
            log.warning(
                "storage_upload_raw_asset_failed",
                asset_id=asset.asset_id,
                job_id=job_id,
                error=str(exc),
            )

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
        """Download a remote video with retries and atomic replacement."""
        tmp_path = target_path + ".tmp"
        last_error = None

        for attempt in range(self._max_retries + 1):
            try:
                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "SceneForgeAI/0.1 (IncuBrix-Assessment)",
                        "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
                    },
                )

                with urllib.request.urlopen(
                    request, timeout=self._timeout
                ) as response:
                    if response.status != 200:
                        raise MediaDownloadError(
                            f"HTTP {response.status} downloading media."
                        )

                    with open(tmp_path, "wb") as output:
                        while True:
                            chunk = response.read(65536)
                            if not chunk:
                                break
                            output.write(chunk)

                os.replace(tmp_path, target_path)
                return

            except MediaDownloadError:
                raise
            except (
                urllib.error.HTTPError,
                urllib.error.URLError,
                TimeoutError,
                OSError,
            ) as exc:
                last_error = exc

                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

                if attempt < self._max_retries:
                    time.sleep(1.0 * (attempt + 1))

        raise MediaDownloadError(
            f"Failed to download media from {url}: {last_error}"
        )

    def _generate_mock_motion_video(
        self,
        asset: MediaAsset,
        target_path: str,
        duration: float,
        job_id: str,
    ) -> None:
        """Generate a lightweight, genuine moving MP4 for mock assets."""
        ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")

        # Lower resolution and frame rate reduce CPU use on Render Free.
        patterns = [
            "testsrc2=size=640x360:rate=24",
            "testsrc=size=640x360:rate=24",
            (
                "gradients=size=640x360:rate=24:"
                "c0=0x1E3A8A:c1=0x3B82F6:speed=0.05"
            ),
        ]

        seed = int(hashlib.md5(asset.asset_id.encode()).hexdigest(), 16)
        pattern = patterns[seed % len(patterns)]

        if not is_ffmpeg_available():
            raise MediaDownloadError(
                "FFmpeg is unavailable; cannot generate mock video.",
                provider=asset.provider_name,
            )

        # Bound duration so a mock asset cannot consume excessive CPU.
        clip_duration = min(max(float(duration), 3.0), 10.0)

        command = [
            ffmpeg_bin,
            "-y",
            "-f", "lavfi",
            "-i", pattern,
            "-t", str(clip_duration),
            "-an",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-crf", "30",
            "-threads", "1",
            "-movflags", "+faststart",
            target_path,
        ]

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=_MOCK_VIDEO_TIMEOUT,
            )

            if (
                not os.path.isfile(target_path)
                or os.path.getsize(target_path) < _MIN_VIDEO_FILE_SIZE
            ):
                raise MediaDownloadError(
                    "FFmpeg completed but produced an invalid mock video.",
                    provider=asset.provider_name,
                )

        except subprocess.TimeoutExpired as exc:
            log.error(
                "mock_motion_ffmpeg_timeout",
                asset_id=asset.asset_id,
                job_id=job_id,
                timeout_seconds=_MOCK_VIDEO_TIMEOUT,
            )
            raise MediaDownloadError(
                "FFmpeg timed out generating mock video.",
                provider=asset.provider_name,
            ) from exc

        except subprocess.CalledProcessError as exc:
            log.error(
                "mock_motion_ffmpeg_failed",
                asset_id=asset.asset_id,
                job_id=job_id,
                returncode=exc.returncode,
                stderr=(exc.stderr or "")[-2000:],
            )
            raise MediaDownloadError(
                "FFmpeg failed to generate mock video.",
                provider=asset.provider_name,
            ) from exc

    @staticmethod
    def _compute_file_sha256(path: str) -> str:
        """Compute the SHA-256 hash of a file."""
        hasher = hashlib.sha256()

        with open(path, "rb") as file:
            while chunk := file.read(65536):
                hasher.update(chunk)

        return hasher.hexdigest()
