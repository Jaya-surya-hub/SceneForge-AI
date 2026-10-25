"""Programmatic card generator using FFmpeg lavfi + drawtext.

Produces typography cards (for abstract concepts) and data cards
(for numerical claims) as silent video segments using only numbers
and text that appear in the narration.

All cards are programmatic outputs — they have no external licence requirement
and are always commercially cleared.

FFmpeg call strategy:
  - Uses `lavfi` (libavfilter virtual source) for the background.
  - Uses `drawtext` filter for text overlay.
  - Never invents statistics. Only uses text provided by the caller.
  - Safe subprocess: argument arrays, explicit timeout, temp-file cleanup.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional

from sceneforge.observability.logging import get_logger

log = get_logger(__name__)

_FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
_FFMPEG_TIMEOUT = int(os.getenv("FFMPEG_TIMEOUT", "60"))

# Card visual defaults
_BG_COLOR = os.getenv("CARD_BG_COLOR", "0x1a1a2e")
_TEXT_COLOR = os.getenv("CARD_TEXT_COLOR", "white")
_FONT_SIZE = int(os.getenv("CARD_FONT_SIZE", "56"))
_DATA_FONT_SIZE = int(os.getenv("CARD_DATA_FONT_SIZE", "72"))
_FPS = int(os.getenv("OUTPUT_FPS", os.getenv("CARD_FPS", "24")))
_FONT_FILE = os.getenv("CARD_FONT_FILE", "/usr/local/share/fonts/Roboto-Regular.ttf")


@dataclass
class CardSpec:
    card_type: str          # "typography_card" | "data_card"
    text: str               # text to display (from narration only)
    duration_seconds: float
    width: int
    height: int
    font_size: int


def generate_card(
    card_type: str,
    text: str,
    duration_seconds: float,
    *,
    width: int = 1280,
    height: int = 720,
    output_path: Optional[str] = None,
) -> str:
    """Generate a card video segment and write to *output_path*.

    Args:
        card_type:        "typography_card" or "data_card".
        text:             Display text — must come from narration, never invented.
        duration_seconds: Duration of the card segment.
        width, height:    Output dimensions.
        output_path:      Where to write the MP4. If None, a temp file is created
                          and the caller is responsible for cleanup.

    Returns:
        Path to the generated MP4 file.

    Raises:
        RuntimeError: If ffmpeg is unavailable or the command fails.
    """
    font_size = _DATA_FONT_SIZE if card_type == "data_card" else _FONT_SIZE
    spec = CardSpec(
        card_type=card_type,
        text=text,
        duration_seconds=max(1.0, duration_seconds),
        width=width,
        height=height,
        font_size=font_size,
    )

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)

    _run_ffmpeg_card(spec, output_path)
    return output_path


def _run_ffmpeg_card(spec: CardSpec, output_path: str) -> None:
    """Build and execute the FFmpeg command for a card."""
    # Escape text: backslash and colon are special in drawtext
    safe_text = _escape_drawtext(spec.text)

    # Build drawtext filter — include fontfile only if the file exists
    font_clause = ""
    if os.path.isfile(_FONT_FILE):
        safe_font = _FONT_FILE.replace("\\", "/").replace(":", "\\:")
        font_clause = f":fontfile={safe_font}"

    vf = (
        f"drawtext="
        f"text='{safe_text}'"
        f":fontcolor={_TEXT_COLOR}"
        f":fontsize={spec.font_size}"
        f":x=(w-text_w)/2"
        f":y=(h-text_h)/2"
        f":line_spacing=8"
        f"{font_clause}"
    )

    _threads = os.getenv("FFMPEG_THREADS", "1")
    _preset = os.getenv("FFMPEG_PRESET", "ultrafast")
    _crf = os.getenv("FFMPEG_CRF", "26")
    args = [
        _FFMPEG_BIN,
        "-y",                              # overwrite without prompt
        "-threads", _threads,
        "-f", "lavfi",
        "-i", f"color=c={_BG_COLOR}:s={spec.width}x{spec.height}:r={_FPS}",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo",  # silent audio track
        "-vf", vf,
        "-t", str(spec.duration_seconds),
        "-c:v", "libx264",
        "-preset", _preset,
        "-crf", _crf,
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path,
    ]

    log.info(
        "card_generator_start",
        card_type=spec.card_type,
        duration=spec.duration_seconds,
        dimensions=f"{spec.width}x{spec.height}",
    )

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=_FFMPEG_TIMEOUT,
        )
    except FileNotFoundError:
        if os.path.exists(output_path):
            try:
                os.unlink(output_path)
            except OSError:
                pass
        raise RuntimeError(
            f"ffmpeg not found at '{_FFMPEG_BIN}'. "
            "FFmpeg must be installed for card generation."
        )
    except subprocess.TimeoutExpired as exc:
        if os.path.exists(output_path):
            try:
                os.unlink(output_path)
            except OSError:
                pass
        stderr_snippet = (getattr(exc, "stderr", None) or "")[-500:]
        raise RuntimeError(
            f"FFmpeg timed out generating card after {_FFMPEG_TIMEOUT}s. {stderr_snippet}".strip()
        )

    if result.returncode != 0:
        if os.path.exists(output_path):
            try:
                os.unlink(output_path)
            except OSError:
                pass
        raise RuntimeError(
            f"FFmpeg card generation failed (exit {result.returncode}): "
            f"{result.stderr[-500:]}"
        )

    log.info("card_generator_done", output_path=output_path)


def _escape_drawtext(text: str) -> str:
    """Escape text for FFmpeg drawtext filter value."""
    # In drawtext, these characters need escaping: : \ ' ( )
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    text = text.replace("(", "\\(")
    text = text.replace(")", "\\)")
    # Newlines → space (drawtext doesn't support them cleanly without font metrics)
    text = text.replace("\n", " ")
    # Truncate to prevent overflow
    if len(text) > 120:
        text = text[:117] + "..."
    return text
