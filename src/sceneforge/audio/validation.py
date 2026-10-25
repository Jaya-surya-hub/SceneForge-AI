"""Audio and input validation for the audio pipeline.

Validates inputs before any TTS/STT work begins.  All rejections raise
typed domain exceptions from sceneforge.schemas.exceptions so that the
API error handler can map them to the correct HTTP status and IS-03 shape.

Validation order (called by AudioPipeline):
  1. Script presence check (if text path):  EmptyScriptError
  2. Audio bytes presence (if audio path):  CorruptedAudioError
  3. File-type guard (magic bytes):         UnsupportedAudioFormatError
  4. ffprobe inspection:                    CorruptedAudioError (if ffprobe fails)
  5. Duration check:                        SpeechNotDetectedError (zero-length)
  6. Silence check:                         SpeechNotDetectedError
  7. Music-only advisory (warning, not error; caller decides)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from sceneforge.audio.interfaces import AudioMetadata
from sceneforge.observability.logging import get_logger
from sceneforge.schemas.exceptions import (
    AudioDurationExceededError,
    CorruptedAudioError,
    EmptyScriptError,
    SpeechNotDetectedError,
    UnsupportedAudioFormatError,
)

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Supported MIME/magic-byte map
# We inspect the first few bytes rather than trusting the file extension.
# ---------------------------------------------------------------------------
_MAGIC_MAP: list[tuple[bytes, str]] = [
    (b"RIFF", "audio/wav"),
    (b"ID3", "audio/mpeg"),
    (b"\xff\xfb", "audio/mpeg"),
    (b"\xff\xf3", "audio/mpeg"),
    (b"\xff\xf2", "audio/mpeg"),
    (b"OggS", "audio/ogg"),
    (b"fLaC", "audio/flac"),
    (b"\x1aE\xdf\xa3", "audio/webm"),
    # MP4/M4A: check bytes 4-7 for 'ftyp'
]

_ALLOWED_MIME_TYPES = frozenset(
    {
        "audio/wav",
        "audio/mpeg",
        "audio/ogg",
        "audio/flac",
        "audio/webm",
        "audio/mp4",
        "audio/m4a",
        "audio/aiff",
        "audio/x-aiff",
    }
)

# Max upload size enforced here as a safety net (also enforced in middleware)
_MAX_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))
_MAX_AUDIO_DURATION_SECONDS = float(os.getenv("MAX_AUDIO_DURATION_SECONDS", "600.0"))


@dataclass
class ValidationResult:
    """Result of audio validation.  Warnings are informational; errors are raised."""

    is_valid: bool
    warnings: list[str]
    detected_mime: Optional[str] = None
    metadata: Optional[AudioMetadata] = None


def detect_mime_type(data: bytes) -> Optional[str]:
    """Return a MIME type string from magic bytes, or None if unrecognised."""
    if not data:
        return None
    # MP4/M4A: bytes 4-7 == b'ftyp'
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return "audio/mp4"
    for magic, mime in _MAGIC_MAP:
        if data[: len(magic)] == magic:
            return mime
    return None


def validate_script(script: Optional[str]) -> None:
    """Raise EmptyScriptError if script is None or blank.

    Args:
        script: The script string or None.

    Raises:
        EmptyScriptError: If script is None, empty, or whitespace-only.
    """
    if not script or not script.strip():
        raise EmptyScriptError()


def validate_audio_bytes(
    audio_bytes: bytes,
    *,
    filename: str = "upload",
    skip_magic_check: bool = False,
) -> str:
    """Validate raw audio bytes before inspection.

    Args:
        audio_bytes:      Raw bytes of the uploaded file.
        filename:         Original filename (used in error messages only).
        skip_magic_check: If True, skip magic-byte detection (for tests).

    Returns:
        Detected MIME type string.

    Raises:
        CorruptedAudioError:        If bytes are empty or too short to be valid.
        UnsupportedAudioFormatError: If magic bytes don't match a known audio type.
        FileTooLargeError:           If bytes exceed MAX_UPLOAD_BYTES.
    """
    from sceneforge.schemas.exceptions import FileTooLargeError

    if not audio_bytes:
        raise CorruptedAudioError()

    if len(audio_bytes) > _MAX_BYTES:
        raise FileTooLargeError(_MAX_BYTES)

    if len(audio_bytes) < 8:
        raise CorruptedAudioError()

    if skip_magic_check:
        return "audio/wav"

    mime = detect_mime_type(audio_bytes)
    if mime is None or mime not in _ALLOWED_MIME_TYPES:
        detected = mime or "unknown"
        raise UnsupportedAudioFormatError(detected)

    return mime


def validate_audio_metadata(metadata: AudioMetadata) -> list[str]:
    """Validate AudioMetadata and return a list of non-fatal warnings.

    Args:
        metadata: Populated AudioMetadata from the inspector.

    Returns:
        List of warning strings (may be empty).

    Raises:
        SpeechNotDetectedError: If audio is silent or zero-length.
    """
    warnings: list[str] = []

    if metadata.duration_seconds <= 0:
        raise SpeechNotDetectedError()

    if metadata.duration_seconds > _MAX_AUDIO_DURATION_SECONDS:
        raise AudioDurationExceededError(metadata.duration_seconds, _MAX_AUDIO_DURATION_SECONDS)

    if metadata.is_silent:
        raise SpeechNotDetectedError()

    if metadata.is_music_only:
        # Music-only is a WARNING, not an error — the pipeline decides how to proceed.
        # We report SUSPECTED because our heuristic is not certain.
        warnings.append(
            "MUSIC_ONLY_SUSPECTED: The audio appears to contain music rather than "
            "speech. Transcription quality may be poor. This is a heuristic assessment, "
            "not a definitive classification."
        )
        log.warning(
            "music_only_suspected",
            duration=metadata.duration_seconds,
        )

    if metadata.has_speech is False and not metadata.is_music_only:
        warnings.append(
            "SPEECH_NOT_DETECTED: Speech was not detected in the audio. "
            "The recording may be silent, music-only, or in an unusual format."
        )

    return warnings


def check_script_audio_mismatch(
    script: str,
    transcript: str,
    *,
    min_word_overlap: float = 0.3,
) -> list[str]:
    """Compare script and transcript and return mismatch warnings.

    This is an advisory check; it does NOT raise exceptions.
    Mismatches are reported in the NarrationResult warnings list.

    Args:
        script:           The original script text.
        transcript:       The STT-derived transcript.
        min_word_overlap: Fraction of script words that must appear in transcript.

    Returns:
        List of mismatch warning strings (empty if no issues found).
    """
    warnings: list[str] = []

    script_words = set(_normalise_words(script))
    transcript_words = set(_normalise_words(transcript))

    if not script_words:
        return warnings

    overlap = len(script_words & transcript_words) / len(script_words)

    if overlap < min_word_overlap:
        warnings.append(
            f"SCRIPT_AUDIO_MISMATCH: Only {overlap:.0%} of script words appear in "
            f"the transcript. The supplied audio may not match the script. "
            f"Check that the correct audio file was uploaded."
        )
        log.warning(
            "script_audio_mismatch",
            overlap=round(overlap, 3),
            script_word_count=len(script_words),
            transcript_word_count=len(transcript_words),
        )

    return warnings


def _normalise_words(text: str) -> list[str]:
    """Lower-case, strip punctuation, return word tokens."""
    import re
    return re.findall(r"\b[a-z]+\b", text.lower())
