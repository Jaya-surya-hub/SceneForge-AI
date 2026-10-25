"""Video and audio normalisation parameters.

Produces the FFmpeg filter strings needed to normalise a clip to
the project's output profile.  All values are configurable via
environment variables.

Video normalisation:
  - Scale to exact output dimensions (with padding if needed).
  - Force pixel format to yuv420p for broad compatibility.
  - Set output frame rate.

Audio normalisation:
  - Resample to 44100 Hz stereo.
  - Loudness normalisation to -16 LUFS (EBU R128 target for online media).
    Applied via the `loudnorm` filter when audio is present.
  - Fallback silence when no audio stream exists.

Original media is never modified; all normalisation produces new output.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

_DEFAULT_WIDTH_16_9 = int(os.getenv("OUTPUT_WIDTH", "1280"))
_DEFAULT_HEIGHT_16_9 = int(os.getenv("OUTPUT_HEIGHT", "720"))
_TARGET_FPS = int(os.getenv("OUTPUT_FPS", "24"))
_TARGET_PIX_FMT = os.getenv("PIXEL_FORMAT", "yuv420p")
_AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "44100"))
_AUDIO_CHANNELS = int(os.getenv("AUDIO_CHANNELS", "2"))
_AUDIO_LUFS = float(os.getenv("AUDIO_LUFS", "-16.0"))
_FFMPEG_PRESET = os.getenv("FFMPEG_PRESET", "ultrafast")
_FFMPEG_THREADS = os.getenv("FFMPEG_THREADS", "1")
_FFMPEG_CRF = int(os.getenv("FFMPEG_CRF", "26"))


@dataclass
class OutputProfile:
    """Target output specification for a render job."""
    width: int
    height: int
    fps: int = _TARGET_FPS
    pix_fmt: str = _TARGET_PIX_FMT
    audio_sample_rate: int = _AUDIO_SAMPLE_RATE
    audio_channels: int = _AUDIO_CHANNELS
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = _FFMPEG_CRF
    preset: str = _FFMPEG_PRESET
    audio_bitrate: str = "128k"


PROFILES: dict[str, OutputProfile] = {
    "16:9": OutputProfile(width=_DEFAULT_WIDTH_16_9, height=_DEFAULT_HEIGHT_16_9),
    "9:16": OutputProfile(width=_DEFAULT_HEIGHT_16_9, height=_DEFAULT_WIDTH_16_9),
    "1:1":  OutputProfile(width=_DEFAULT_HEIGHT_16_9, height=_DEFAULT_HEIGHT_16_9),
}


def get_profile(aspect_ratio: str) -> OutputProfile:
    """Return the OutputProfile for the given aspect ratio string."""
    p = PROFILES.get(aspect_ratio)
    if p is None:
        raise ValueError(
            f"Unknown aspect ratio '{aspect_ratio}'. "
            f"Supported: {list(PROFILES.keys())}"
        )
    return p


def build_video_filter(
    profile: OutputProfile,
    extra_vf: str = "",
) -> str:
    """Build the FFmpeg -vf filter chain for normalisation.

    Args:
        profile:   Target output profile.
        extra_vf:  Additional filter string to prepend (e.g. reframe filters).

    Returns:
        Filter string suitable for -vf argument.
    """
    # Scale to exact dimensions, pad if aspect ratio doesn't match
    scale_pad = (
        f"scale={profile.width}:{profile.height}:force_original_aspect_ratio=decrease,"
        f"pad={profile.width}:{profile.height}:(ow-iw)/2:(oh-ih)/2:black,"
        f"fps={profile.fps},"
        f"format={profile.pix_fmt}"
    )

    if extra_vf:
        return f"{extra_vf},{scale_pad}"
    return scale_pad


def build_audio_filter(*, normalise_loudness: bool = True) -> str:
    """Build the FFmpeg -af filter chain for audio normalisation."""
    filters = [
        f"aresample={_AUDIO_SAMPLE_RATE}",
        f"pan=stereo|c0=c0|c1=c1" if _AUDIO_CHANNELS == 2 else "",
    ]
    if normalise_loudness:
        filters.append(f"loudnorm=I={_AUDIO_LUFS}:TP=-1.5:LRA=11")
    return ",".join(f for f in filters if f)
