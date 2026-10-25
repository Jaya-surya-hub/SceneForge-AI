"""Thin wrapper around ffprobe JSON output.

All calls use subprocess argument arrays (never shell=True).
Every call has an explicit timeout and returns structured data.

When ffprobe is unavailable a clear RuntimeError is raised rather than
silently producing incorrect results.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Optional

_FFPROBE_TIMEOUT = int(os.getenv("FFPROBE_TIMEOUT", "15"))
_FFPROBE_BIN = os.getenv("FFPROBE_BIN", "ffprobe")


@dataclass
class StreamInfo:
    codec_type: str          # "video" | "audio" | "subtitle" | "data"
    codec_name: str
    width: Optional[int] = None
    height: Optional[int] = None
    r_frame_rate: Optional[str] = None   # e.g. "30/1"
    avg_frame_rate: Optional[str] = None
    duration: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bit_rate: Optional[int] = None
    pix_fmt: Optional[str] = None
    raw: dict = field(default_factory=dict)


@dataclass
class FormatInfo:
    filename: str
    format_name: str
    duration: Optional[float]
    size: Optional[int]
    bit_rate: Optional[int]
    nb_streams: int
    raw: dict = field(default_factory=dict)


@dataclass
class ProbeResult:
    format: FormatInfo
    streams: list[StreamInfo]

    @property
    def video_stream(self) -> Optional[StreamInfo]:
        return next((s for s in self.streams if s.codec_type == "video"), None)

    @property
    def audio_stream(self) -> Optional[StreamInfo]:
        return next((s for s in self.streams if s.codec_type == "audio"), None)

    @property
    def duration(self) -> Optional[float]:
        v = self.video_stream
        if v and v.duration:
            return v.duration
        return self.format.duration

    def frame_rate_float(self) -> Optional[float]:
        """Parse r_frame_rate fraction to float, e.g. '30/1' → 30.0."""
        vs = self.video_stream
        if not vs:
            return None
        for attr in (vs.r_frame_rate, vs.avg_frame_rate):
            if attr and "/" in attr:
                try:
                    num, den = attr.split("/")
                    d = int(den)
                    return int(num) / d if d else None
                except (ValueError, ZeroDivisionError):
                    pass
        return None


def probe_file(path: str) -> ProbeResult:
    """Run ffprobe on *path* and return structured ProbeResult.

    Args:
        path: Filesystem path to the media file.

    Returns:
        ProbeResult with format and stream information.

    Raises:
        RuntimeError: If ffprobe is not found or returns non-zero.
        ValueError:   If the output cannot be parsed as JSON.
    """
    args = [
        _FFPROBE_BIN,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=_FFPROBE_TIMEOUT,
        )
    except FileNotFoundError:
        raise RuntimeError(
            f"ffprobe not found at '{_FFPROBE_BIN}'. "
            "Install FFmpeg and ensure ffprobe is on PATH, "
            "or set FFPROBE_BIN to the full path."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"ffprobe timed out after {_FFPROBE_TIMEOUT}s on '{path}'."
        )

    if result.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed (exit {result.returncode}) for '{path}': "
            f"{result.stderr[:200]}"
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"ffprobe output is not valid JSON: {exc}") from exc

    return _parse_probe(data, path)


def probe_bytes(data: bytes, suffix: str = ".mp4") -> ProbeResult:
    """Write *data* to a temp file and probe it.

    Cleans up the temp file unconditionally.
    """
    import tempfile
    import os as _os

    fd, tmp = tempfile.mkstemp(suffix=suffix)
    try:
        with _os.fdopen(fd, "wb") as f:
            f.write(data)
        return probe_file(tmp)
    finally:
        try:
            _os.unlink(tmp)
        except OSError:
            pass


def is_ffprobe_available() -> bool:
    """Return True if ffprobe can be executed successfully."""
    try:
        result = subprocess.run(
            [_FFPROBE_BIN, "-version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def is_ffmpeg_available() -> bool:
    """Return True if ffmpeg can be executed successfully."""
    ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")
    try:
        result = subprocess.run(
            [ffmpeg_bin, "-version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


# ---------------------------------------------------------------------------
# Internal parsing
# ---------------------------------------------------------------------------

def _parse_probe(data: dict, path: str) -> ProbeResult:
    fmt_raw = data.get("format", {})
    fmt = FormatInfo(
        filename=fmt_raw.get("filename", path),
        format_name=fmt_raw.get("format_name", ""),
        duration=_safe_float(fmt_raw.get("duration")),
        size=_safe_int(fmt_raw.get("size")),
        bit_rate=_safe_int(fmt_raw.get("bit_rate")),
        nb_streams=int(fmt_raw.get("nb_streams", 0)),
        raw=fmt_raw,
    )

    streams = []
    for s in data.get("streams", []):
        stream = StreamInfo(
            codec_type=s.get("codec_type", "unknown"),
            codec_name=s.get("codec_name", "unknown"),
            width=_safe_int(s.get("width")),
            height=_safe_int(s.get("height")),
            r_frame_rate=s.get("r_frame_rate"),
            avg_frame_rate=s.get("avg_frame_rate"),
            duration=_safe_float(s.get("duration")),
            sample_rate=_safe_int(s.get("sample_rate")),
            channels=_safe_int(s.get("channels")),
            bit_rate=_safe_int(s.get("bit_rate")),
            pix_fmt=s.get("pix_fmt"),
            raw=s,
        )
        streams.append(stream)

    return ProbeResult(format=fmt, streams=streams)


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None
