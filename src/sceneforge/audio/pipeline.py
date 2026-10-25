"""Unified audio pipeline.

Handles three input modes:
  1. Text only   → TTS synthesis → NarrationResult
  2. Audio only  → STT transcription → NarrationResult
  3. Text + Audio → use supplied audio, transcribe, compare with script → NarrationResult

All validation is performed before any TTS/STT work.

Usage:
    pipeline = AudioPipeline()
    result = pipeline.process(
        script="Hello world.",
        audio_bytes=None,
    )

The pipeline is stateless; create a new instance per job.
"""

from __future__ import annotations

import io
import os
from typing import Optional

from sceneforge.audio.adapters.audio_inspector import (
    FfprobeAudioInspector,
    MockAudioInspector,
)
from sceneforge.audio.factory import get_stt_adapter, get_tts_adapter
from sceneforge.audio.interfaces import (
    AudioInspector,
    NarrationResult,
    STTAdapter,
    TTSAdapter,
    WordTimestamp,
)
from sceneforge.audio.validation import (
    check_script_audio_mismatch,
    validate_audio_bytes,
    validate_audio_metadata,
    validate_script,
)
from sceneforge.observability.logging import get_logger
from sceneforge.schemas.exceptions import (
    CorruptedAudioError,
    EmptyScriptError,
    SpeechNotDetectedError,
)

log = get_logger(__name__)

# Whether to use ffprobe for real inspection (disabled in tests via env)
_USE_REAL_INSPECTOR = os.getenv("AUDIO_INSPECTOR", "ffprobe").lower() == "ffprobe"

# Mismatch threshold — fraction of script words that must appear in transcript
_MISMATCH_THRESHOLD = float(os.getenv("SCRIPT_MISMATCH_THRESHOLD", "0.3"))

# Minimum silence ratio to consider audio speech-like (heuristic)
_MIN_SPEECH_SILENCE_RATIO = float(os.getenv("MIN_SPEECH_SILENCE_RATIO", "0.05"))


def _make_inspector(*, force_mock: bool = False) -> AudioInspector:
    """Return the configured AudioInspector."""
    if force_mock or not _USE_REAL_INSPECTOR:
        return MockAudioInspector()
    return FfprobeAudioInspector()


class AudioPipeline:
    """Orchestrates audio validation, TTS, and STT for a single job.

    Args:
        tts_adapter:  TTS adapter (defaults to env-configured adapter).
        stt_adapter:  STT adapter (defaults to env-configured adapter).
        inspector:    AudioInspector (defaults to env-configured inspector).
        storage_path: MinIO prefix for storing generated audio.
    """

    def __init__(
        self,
        *,
        tts_adapter: Optional[TTSAdapter] = None,
        stt_adapter: Optional[STTAdapter] = None,
        inspector: Optional[AudioInspector] = None,
        storage_path: str = "",
    ) -> None:
        self._tts = tts_adapter or get_tts_adapter()
        self._stt = stt_adapter or get_stt_adapter()
        self._inspector = inspector or _make_inspector()
        self._storage_path = storage_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        *,
        script: Optional[str] = None,
        audio_bytes: Optional[bytes] = None,
        filename: str = "upload.wav",
        job_id: str = "unknown",
    ) -> NarrationResult:
        """Process inputs and return a NarrationResult.

        Args:
            script:      Narration text (may be None if audio_bytes provided).
            audio_bytes: Raw audio file bytes (may be None for text-only).
            filename:    Original filename (for format detection).
            job_id:      Job ID for logging.

        Returns:
            NarrationResult with audio_path, transcript, timestamps, duration,
            provenance, and any warnings.

        Raises:
            EmptyScriptError:            Script is blank and no audio supplied.
            CorruptedAudioError:         Audio bytes are empty or unreadable.
            UnsupportedAudioFormatError: Audio format is not supported.
            SpeechNotDetectedError:      Audio is silent or zero-length.
        """
        has_script = script is not None and script.strip()
        has_audio = audio_bytes is not None and len(audio_bytes) > 0
        # script_provided: True when script was explicitly passed (even if blank)
        script_provided = script is not None

        # Explicit check: empty bytes is a corrupted upload, not a missing-script error
        if audio_bytes is not None and len(audio_bytes) == 0:
            raise CorruptedAudioError()

        log.info(
            "audio_pipeline_start",
            job_id=job_id,
            has_script=bool(has_script),
            has_audio=has_audio,
            tts_adapter=self._tts.adapter_name,
            stt_adapter=self._stt.adapter_name,
        )

        if not has_script and not has_audio:
            raise EmptyScriptError()

        if has_script and not has_audio:
            return self._text_only(script, job_id)
        elif has_audio and not script_provided:
            # Pure audio-only: no script parameter passed at all
            return self._audio_only(audio_bytes, filename, job_id)
        elif has_audio and script_provided and not has_script:
            # Script was passed but is blank + audio provided → combined path validates script
            return self._combined(script, audio_bytes, filename, job_id)
        else:
            # Both script and audio present and valid
            return self._combined(script, audio_bytes, filename, job_id)

    # ------------------------------------------------------------------
    # Private routing methods
    # ------------------------------------------------------------------

    def _text_only(self, script: str, job_id: str) -> NarrationResult:
        """Script only → TTS synthesis."""
        validate_script(script)

        log.info("audio_pipeline_tts", job_id=job_id, text_len=len(script))
        audio_bytes = self._tts.synthesise(script)
        duration = self._tts.estimated_duration(script)

        # Generate evenly-spaced word timestamps from TTS
        word_timestamps = _even_timestamps(script, duration)

        storage_key = f"{self._storage_path}/narration.wav" if self._storage_path else ""

        return NarrationResult(
            audio_path=storage_key,
            transcript=script.strip(),
            word_timestamps=word_timestamps,
            duration_seconds=duration,
            tts_used=True,
            adapter_name=self._tts.adapter_name,
            warnings=[],
            is_mock=self._tts.is_mock,
            audio_bytes=audio_bytes,
        )

    def _audio_only(
        self, audio_bytes: bytes, filename: str, job_id: str
    ) -> NarrationResult:
        """Audio only → inspection → STT transcription."""
        # Magic byte check always runs (independent of inspector type)
        mime = validate_audio_bytes(audio_bytes, filename=filename)
        metadata = self._inspector.inspect(audio_bytes)
        warnings = validate_audio_metadata(metadata)

        log.info(
            "audio_pipeline_stt",
            job_id=job_id,
            duration=metadata.duration_seconds,
            codec=metadata.codec,
        )

        transcript, word_timestamps = self._stt.transcribe(audio_bytes)

        if not transcript.strip():
            warnings.append(
                "TRANSCRIPT_EMPTY: STT returned an empty transcript. "
                "The audio may be silent, music-only, or unintelligible."
            )

        storage_key = f"{self._storage_path}/voiceover{_ext_from_mime(mime)}"

        return NarrationResult(
            audio_path=storage_key,
            transcript=transcript.strip(),
            word_timestamps=word_timestamps,
            duration_seconds=metadata.duration_seconds,
            tts_used=False,
            adapter_name=self._stt.adapter_name,
            warnings=warnings,
            is_mock=self._stt.is_mock,
            audio_bytes=audio_bytes,
        )

    def _combined(
        self,
        script: str,
        audio_bytes: bytes,
        filename: str,
        job_id: str,
    ) -> NarrationResult:
        """Script + audio → use audio, transcribe, compare with script."""
        # Always validate script in combined mode — even if audio is present
        validate_script(script)
        # Magic byte check always runs
        mime = validate_audio_bytes(audio_bytes, filename=filename)
        metadata = self._inspector.inspect(audio_bytes)
        warnings = validate_audio_metadata(metadata)

        log.info(
            "audio_pipeline_combined",
            job_id=job_id,
            duration=metadata.duration_seconds,
        )

        transcript, word_timestamps = self._stt.transcribe(audio_bytes)

        # Compare transcript with script and warn on significant mismatch
        mismatch_warnings = check_script_audio_mismatch(
            script,
            transcript,
            min_word_overlap=_MISMATCH_THRESHOLD,
        )
        warnings.extend(mismatch_warnings)

        # Use audio transcript for timing; prefer script text for caption quality
        effective_transcript = transcript.strip() or script.strip()

        storage_key = f"{self._storage_path}/voiceover{_ext_from_mime(mime)}"

        return NarrationResult(
            audio_path=storage_key,
            transcript=effective_transcript,
            word_timestamps=word_timestamps,
            duration_seconds=metadata.duration_seconds,
            tts_used=False,
            adapter_name=self._stt.adapter_name,
            warnings=warnings,
            is_mock=self._stt.is_mock,
            audio_bytes=audio_bytes,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _even_timestamps(text: str, total_duration: float) -> list[WordTimestamp]:
    """Distribute word timestamps evenly across total_duration."""
    words = text.split()
    if not words or total_duration <= 0:
        return []
    interval = total_duration / len(words)
    return [
        WordTimestamp(
            word=w,
            start=round(i * interval, 3),
            end=round((i + 1) * interval, 3),
        )
        for i, w in enumerate(words)
    ]


def _ext_from_mime(mime: str) -> str:
    _MAP = {
        "audio/wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/ogg": ".ogg",
        "audio/flac": ".flac",
        "audio/mp4": ".m4a",
        "audio/m4a": ".m4a",
        "audio/webm": ".webm",
    }
    return _MAP.get(mime, ".audio")


def _is_mock_inspector(inspector: AudioInspector) -> bool:
    """Return True if inspector is the MockAudioInspector (skip magic check)."""
    return isinstance(inspector, MockAudioInspector)
