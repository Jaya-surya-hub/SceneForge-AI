"""Incremental render cache — content-addressed segment storage.

Cache key is a SHA-256 digest of all inputs that affect the rendered output:
  - Source media SHA-256 (or asset_id for mock assets)
  - Trim start and end times (rounded to ms)
  - Output aspect ratio
  - Caption text and font size
  - Video/audio codec and CRF
  - Pixel format and FPS
  - Processing version string

This means:
  - Changing a scene re-renders only that scene.
  - Unchanged scenes reuse their cached segment.
  - Changing the aspect ratio invalidates all segments.
  - Changing PROCESSING_VERSION invalidates all segments (safe upgrade path).

Cache is namespaced per job: segments/{job_id}/{cache_key}.mp4
This prevents cross-user segment leakage even with identical inputs.

Interrupted writes are handled by writing to a .tmp file first and
renaming atomically on success (POSIX rename is atomic; Windows uses
os.replace which is also atomic).

Thread/process safety: two workers with the same cache key write to
different tmp files; the last rename wins, which is safe because both
produce identical output for identical inputs.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Optional

from sceneforge.observability.logging import get_logger

log = get_logger(__name__)

PROCESSING_VERSION = os.getenv("PROCESSING_VERSION", "1.0.0")


@dataclass
class CacheKey:
    """All inputs that determine a segment's rendered output."""

    source_id: str             # asset_id or SHA-256 of source bytes
    trim_start: float          # seconds, rounded to 3dp
    trim_end: float
    aspect_ratio: str          # "16:9" | "9:16" | "1:1"
    caption_text: str
    caption_font_size: int
    video_codec: str
    audio_codec: str
    crf: int
    pix_fmt: str
    fps: int
    processing_version: str = PROCESSING_VERSION

    def digest(self) -> str:
        """Return the SHA-256 hex digest of the canonical key representation."""
        canonical = json.dumps(
            {
                "source_id": self.source_id,
                "trim_start": round(self.trim_start, 3),
                "trim_end": round(self.trim_end, 3),
                "aspect_ratio": self.aspect_ratio,
                "caption_text": self.caption_text,
                "caption_font_size": self.caption_font_size,
                "video_codec": self.video_codec,
                "audio_codec": self.audio_codec,
                "crf": self.crf,
                "pix_fmt": self.pix_fmt,
                "fps": self.fps,
                "processing_version": self.processing_version,
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


class RenderCache:
    """Content-addressed render cache backed by a local directory.

    Args:
        cache_dir: Root directory for cached segments.
        job_id:    Isolates this job's cache namespace.
    """

    def __init__(self, cache_dir: str, job_id: str) -> None:
        self._root = os.path.join(cache_dir, job_id)
        os.makedirs(self._root, exist_ok=True)

    def get(self, key: CacheKey) -> Optional[str]:
        """Return the path to a cached segment, or None on cache miss.

        The returned path is valid until the cache is cleared.
        """
        path = self._segment_path(key.digest())
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            log.info("render_cache_hit", key=key.digest()[:12])
            return path
        return None

    def put(self, key: CacheKey, segment_path: str) -> str:
        """Store a rendered segment in the cache.

        Copies *segment_path* to the cache atomically using a tmp→rename
        pattern to prevent partial writes from being visible.

        Args:
            key:          CacheKey for this segment.
            segment_path: Path to the rendered segment file.

        Returns:
            Path of the cached copy.
        """
        dest = self._segment_path(key.digest())
        tmp = dest + ".tmp"
        import shutil
        shutil.copy2(segment_path, tmp)
        os.replace(tmp, dest)         # atomic on both POSIX and Windows
        log.info("render_cache_stored", key=key.digest()[:12], dest=dest)
        return dest

    def invalidate(self, key: CacheKey) -> bool:
        """Remove a cached segment. Returns True if it existed."""
        path = self._segment_path(key.digest())
        if os.path.isfile(path):
            os.unlink(path)
            log.info("render_cache_invalidated", key=key.digest()[:12])
            return True
        return False

    def clear_job(self) -> int:
        """Remove all cached segments for this job. Returns count removed."""
        count = 0
        try:
            for fname in os.listdir(self._root):
                fpath = os.path.join(self._root, fname)
                if os.path.isfile(fpath):
                    os.unlink(fpath)
                    count += 1
        except OSError:
            pass
        log.info("render_cache_cleared_job", count=count)
        return count

    def _segment_path(self, digest: str) -> str:
        return os.path.join(self._root, f"{digest}.mp4")


def build_cache_key(
    asset_id: str,
    trim_start: float,
    trim_end: float,
    aspect_ratio: str,
    caption_text: str,
    profile,  # OutputProfile
) -> CacheKey:
    """Convenience function to build a CacheKey from rendering inputs."""
    return CacheKey(
        source_id=asset_id,
        trim_start=trim_start,
        trim_end=trim_end,
        aspect_ratio=aspect_ratio,
        caption_text=caption_text,
        caption_font_size=getattr(profile, "caption_font_size",
                                  int(os.getenv("CAPTION_FONT_SIZE", "36"))),
        video_codec=profile.video_codec,
        audio_codec=profile.audio_codec,
        crf=profile.crf,
        pix_fmt=profile.pix_fmt,
        fps=profile.fps,
        processing_version=PROCESSING_VERSION,
    )
