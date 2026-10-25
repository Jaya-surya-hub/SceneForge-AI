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

_TARGET_FPS = int(os.getenv("OUTPUT_FPS", "30"))
_TARGET_PIX_FMT = os.getenv("PIXEL_FORMAT", "yuv420p")
_AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "44100"))
_AUDIO_CHANNELS = int(os.getenv("AUDIO_CHANNELS", "2"))
_AUDIO_LUFS = float(os.getenv("AUDIO_LUFS", "-16.0"))


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
    crf: int = 23
    preset: str = "fast"
    audio_bitrate: str = "128k"


PROFILES: dict[str, OutputProfile] = {
    "16:9": OutputProfile(width=1920, height=1080),
    "9:16": OutputProfile(width=1080, height=1920),
    "1:1":  OutputProfile(width=1080, height=1080),
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
