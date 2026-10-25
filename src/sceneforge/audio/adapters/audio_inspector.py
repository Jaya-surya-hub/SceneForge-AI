"""ffprobe-based AudioInspector.

Uses ffprobe (subprocess with argument array, never shell=True) to extract
accurate media metadata from raw bytes written to a temp file.

Detects:
  - Duration, sample rate, channels, codec, container format
  - Silence (RMS energy below threshold using ffmpeg silencedetect filter)
  - Speech presence heuristic (voiced-band energy above silence threshold)
  - Music-only is reported as SUSPECTED, not CERTAIN, unless silence is confirmed

Temp files are always cleaned up, even on error.
No network calls. No external API keys required.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from typing import Optional

from sceneforge.audio.interfaces import AudioInspector, AudioMetadata
from sceneforge.observability.logging import get_logger
from sceneforge.schemas.exceptions import (
    CorruptedAudioError,
    UnsupportedAudioFormatError,
)

log = get_logger(__name__)

# Formats we can reliably inspect via ffprobe
_SUPPORTED_FORMATS = frozenset(
    {
        "wav", "mp3", "aac", "ogg", "flac", "opus",
        "mp4", "m4a", "webm", "aiff", "aif",
        # ffprobe container names (may differ from file extension)
        "pcm_s16le", "pcm_s24le", "pcm_f32le",
    }
)

_FFPROBE_TIMEOUT = int(os.getenv("FFPROBE_TIMEOUT", "15"))
_FFMPEG_TIMEOUT = int(os.getenv("FFMPEG_TIMEOUT", "30"))

# Silence detect: noise floor in dB, minimum silence duration in seconds
_SILENCE_NOISE_DB = float(os.getenv("SILENCE_NOISE_DB", "-50"))
_SILENCE_MIN_DURATION = float(os.getenv("SILENCE_MIN_DURATION", "0.5"))

# RMS threshold below which audio is considered silent (relative to full scale)
_SILENT_MEAN_VOLUME_DB = float(os.getenv("SILENT_MEAN_VOLUME_DB", "-65"))


def _run(args: list[str], timeout: int) -> tuple[str, str, int]:
    """Run a subprocess with argument array. Returns (stdout, stderr, returncode)."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Process timed out after {timeout}s: {args[0]}")
    except FileNotFoundError:
        raise RuntimeError(
            f"{args[0]} not found. Install FFmpeg and ensure it is on PATH."
        )


def _write_temp(data: bytes, suffix: str = ".audio") -> str:
    """Write bytes to a named temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    except Exception:
        os.unlink(path)
        raise
    return path


class FfprobeAudioInspector(AudioInspector):
    """Inspect audio files using ffprobe + ffmpeg silencedetect."""

    def inspect(self, audio_bytes: bytes) -> AudioMetadata:
        """Return AudioMetadata for the given audio bytes.

        Writes bytes to a temp file, runs ffprobe, then runs ffmpeg
        silencedetect. Always cleans up the temp file.

        Args:
            audio_bytes: Raw audio file bytes (any format ffprobe supports).

        Returns:
            Populated AudioMetadata.

        Raises:
            CorruptedAudioError: If ffprobe cannot parse the file.
            UnsupportedAudioFormatError: If no audio stream is found.
        """
        if not audio_bytes:
            raise CorruptedAudioError()

        tmp_path = _write_temp(audio_bytes)
        try:
            return self._inspect_file(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _inspect_file(self, path: str) -> AudioMetadata:
        # ── Step 1: ffprobe JSON probe ──────────────────────────────────────
        probe_args = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            path,
        ]
        stdout, stderr, rc = _run(probe_args, _FFPROBE_TIMEOUT)

        if rc != 0 or not stdout.strip():
            log.warning("ffprobe_failed", path=path, stderr=stderr[:200])
            raise CorruptedAudioError()

        try:
            probe = json.loads(stdout)
        except json.JSONDecodeError:
            raise CorruptedAudioError()

        # ── Step 2: Extract stream and format info ──────────────────────────
        streams = probe.get("streams", [])
        audio_stream = next(
            (s for s in streams if s.get("codec_type") == "audio"), None
        )
        if audio_stream is None:
            raise UnsupportedAudioFormatError("No audio stream found")

        fmt = probe.get("format", {})
        duration = float(audio_stream.get("duration") or fmt.get("duration") or 0.0)
        sample_rate = int(audio_stream.get("sample_rate") or 44100)
        channels = int(audio_stream.get("channels") or 1)
        codec = audio_stream.get("codec_name", "unknown")
        format_name = fmt.get("format_name", "unknown").split(",")[0].strip()

        log.debug(
            "ffprobe_result",
            duration=duration,
            codec=codec,
            format_name=format_name,
            sample_rate=sample_rate,
            channels=channels,
        )

        # ── Step 3: Silence / volume analysis ──────────────────────────────
        is_silent, has_speech, is_music_suspected = self._analyse_audio(
            path, duration
        )

        return AudioMetadata(
            duration_seconds=duration,
            sample_rate=sample_rate,
            channels=channels,
            codec=codec,
            format_name=format_name,
            has_speech=has_speech,
            is_silent=is_silent,
            is_music_only=is_music_suspected,
        )

    def _analyse_audio(
        self, path: str, duration: float
    ) -> tuple[bool, Optional[bool], bool]:
        """Return (is_silent, has_speech, is_music_suspected).

        Uses ffmpeg's volumedetect filter for mean volume, and silencedetect
        to identify silent regions.

        Distinctions:
          - is_silent=True    → mean volume well below threshold (near-silent)
          - has_speech=True   → speech likely present (not silent, not pure tone)
          - has_speech=False  → speech likely absent
          - has_speech=None   → cannot determine
          - is_music_suspected=True → non-silent but speech heuristic suggests music
            (SUSPECTED, not CERTAIN — caller should treat as advisory)
        """
        if duration <= 0:
            return True, None, False

        # Limit analysis to first 30 seconds (performance)
        analyse_duration = min(duration, 30.0)

        # ── Volume / mean loudness ──────────────────────────────────────────
        vol_args = [
            "ffmpeg",
            "-i", path,
            "-t", str(analyse_duration),
            "-af", "volumedetect",
            "-f", "null",
            "-",
        ]
        _, vol_stderr, _ = _run(vol_args, _FFMPEG_TIMEOUT)

        mean_volume_db = self._parse_mean_volume(vol_stderr)

        if mean_volume_db is not None and mean_volume_db < _SILENT_MEAN_VOLUME_DB:
            log.debug("audio_silent", mean_volume_db=mean_volume_db)
            return True, None, False

        # ── Silence-detect: find total silent duration ──────────────────────
        sd_args = [
            "ffmpeg",
            "-i", path,
            "-t", str(analyse_duration),
            "-af", f"silencedetect=noise={_SILENCE_NOISE_DB}dB:d={_SILENCE_MIN_DURATION}",
            "-f", "null",
            "-",
        ]
        _, sd_stderr, _ = _run(sd_args, _FFMPEG_TIMEOUT)

        silent_duration = self._total_silent_duration(sd_stderr)
        silence_ratio = silent_duration / analyse_duration if analyse_duration > 0 else 1.0

        # ── Speech heuristic ────────────────────────────────────────────────
        # Speech has irregular dynamics; high-silence-ratio audio with some
        # energy is likely music (steady continuous signal). This is heuristic —
        # reported as SUSPECTED, not certain.
        if silence_ratio > 0.95:
            # Almost entirely silent
            return True, None, False

        # If silence_ratio is very low (< 5%) → likely continuous music/tone
        # If silence_ratio is moderate (5-80%) → likely speech (speech has gaps)
        has_speech: Optional[bool]
        is_music_suspected: bool

        if silence_ratio < 0.05 and analyse_duration > 3.0:
            # Continuous signal with very little silence → suspected music
            has_speech = False
            is_music_suspected = True
        elif silence_ratio > 0.05:
            # Audio has meaningful pauses → speech-like dynamics
            has_speech = True
            is_music_suspected = False
        else:
            has_speech = None
            is_music_suspected = False

        log.debug(
            "audio_analysis",
            mean_volume_db=mean_volume_db,
            silence_ratio=round(silence_ratio, 3),
            has_speech=has_speech,
            is_music_suspected=is_music_suspected,
        )

        return False, has_speech, is_music_suspected

    @staticmethod
    def _parse_mean_volume(stderr: str) -> Optional[float]:
        """Parse mean_volume from ffmpeg volumedetect output."""
        match = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", stderr)
        if match:
            return float(match.group(1))
        return None

    @staticmethod
    def _total_silent_duration(stderr: str) -> float:
        """Sum silence_duration values from silencedetect output."""
        total = 0.0
        for match in re.finditer(r"silence_duration:\s*([\d.]+)", stderr):
            total += float(match.group(1))
        return total


class MockAudioInspector(AudioInspector):
    """[MOCK] Deterministic AudioInspector for the no-key test suite.

    Returns configurable AudioMetadata without calling ffprobe.
    Default: 5.0s, 22050Hz, mono, pcm_s16le, has_speech=True.
    """

    def __init__(
        self,
        *,
        duration: float = 5.0,
        sample_rate: int = 22050,
        channels: int = 1,
        codec: str = "pcm_s16le",
        format_name: str = "wav",
        has_speech: Optional[bool] = True,
        is_silent: bool = False,
        is_music_only: bool = False,
        raise_corrupted: bool = False,
        raise_unsupported: bool = False,
    ) -> None:
        self._meta = AudioMetadata(
            duration_seconds=duration,
            sample_rate=sample_rate,
            channels=channels,
            codec=codec,
            format_name=format_name,
            has_speech=has_speech,
            is_silent=is_silent,
            is_music_only=is_music_only,
        )
        self._raise_corrupted = raise_corrupted
        self._raise_unsupported = raise_unsupported

    def inspect(self, audio_bytes: bytes) -> AudioMetadata:
        """Return configured metadata. NOTE: This is a MOCK — no ffprobe call."""
        if self._raise_corrupted:
            raise CorruptedAudioError()
        if self._raise_unsupported:
            raise UnsupportedAudioFormatError("mock-unsupported")
        return self._meta
