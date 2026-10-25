"""Whisper STT adapter — local inference, MIT licence, no API key required.

Uses openai-whisper for local speech-to-text transcription with word-level
timestamps via the verbose_json output format.

Feature-flagged: only loaded when STT_ADAPTER=whisper.
Mock adapter is the default for all tests.

Model sizes and approx. disk usage:
  tiny   (~39 MB)  — fastest, lowest accuracy
  base   (~74 MB)  — good balance (default)
  small  (~244 MB) — higher accuracy
  medium (~769 MB) — high accuracy
  large  (~1.5 GB) — best accuracy

Set WHISPER_MODEL=<size> to override.

Install: pip install openai-whisper
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from sceneforge.audio.interfaces import STTAdapter, WordTimestamp
from sceneforge.observability.logging import get_logger
from sceneforge.schemas.exceptions import STTProviderError

log = get_logger(__name__)

_WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
_WHISPER_TIMEOUT = int(os.getenv("WHISPER_TIMEOUT", "120"))

# Cached loaded model (lazy, loaded on first transcribe call)
_loaded_model: Optional[object] = None


def _get_model():
    """Load and cache the Whisper model (lazy)."""
    global _loaded_model
    if _loaded_model is None:
        try:
            import whisper  # type: ignore[import]
        except ImportError:
            raise STTProviderError(
                "openai-whisper is not installed. Run: pip install openai-whisper"
            )
        log.info("whisper_loading_model", model=_WHISPER_MODEL_SIZE)
        _loaded_model = whisper.load_model(_WHISPER_MODEL_SIZE)
        log.info("whisper_model_loaded", model=_WHISPER_MODEL_SIZE)
    return _loaded_model


class WhisperSTTAdapter(STTAdapter):
    """STT adapter using OpenAI Whisper (local, MIT licence).

    Feature-flagged: STT_ADAPTER=whisper activates this adapter.
    Model is loaded lazily on first call.
    """

    adapter_name: str = "whisper"
    is_mock: bool = False

    def transcribe(
        self, audio_bytes: bytes
    ) -> tuple[str, list[WordTimestamp]]:
        """Transcribe audio bytes and return (transcript, word_timestamps).

        Writes bytes to a temp file (Whisper requires a file path),
        transcribes with word-level timestamps, and cleans up.

        Args:
            audio_bytes: Raw audio bytes (WAV, MP3, etc.).

        Returns:
            (transcript_text, word_timestamps)

        Raises:
            STTProviderError: If Whisper is unavailable or transcription fails.
        """
        import tempfile

        suffix = ".wav"  # default; Whisper handles most formats
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name

            return self._transcribe_file(tmp_path)

        except STTProviderError:
            # Fall back to speech_recognition if Whisper is not installed/loaded
            try:
                from sceneforge.audio.adapters.speech_rec_stt import SpeechRecognitionSTTAdapter
                log.info("whisper_fallback_to_speech_recognition")
                return SpeechRecognitionSTTAdapter().transcribe(audio_bytes)
            except Exception:
                raise
        except Exception as exc:
            raise STTProviderError(f"Whisper transcription failed: {exc}") from exc
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def _transcribe_file(
        self, path: str
    ) -> tuple[str, list[WordTimestamp]]:
        """Run Whisper on a file path and extract word timestamps."""
        model = _get_model()

        result = model.transcribe(
            path,
            word_timestamps=True,
            verbose=False,
        )

        transcript = result.get("text", "").strip()
        word_timestamps: list[WordTimestamp] = []

        for segment in result.get("segments", []):
            for word_info in segment.get("words", []):
                word = word_info.get("word", "").strip()
                start = float(word_info.get("start", 0.0))
                end = float(word_info.get("end", 0.0))
                if word:
                    word_timestamps.append(WordTimestamp(word=word, start=start, end=end))

        # Fallback: if no word timestamps, distribute evenly across segments
        if not word_timestamps and transcript:
            word_timestamps = _distribute_timestamps(transcript, result)

        log.info(
            "whisper_transcribed",
            model=_WHISPER_MODEL_SIZE,
            transcript_length=len(transcript),
            word_count=len(word_timestamps),
        )
        return transcript, word_timestamps


def _distribute_timestamps(
    transcript: str, result: dict
) -> list[WordTimestamp]:
    """Distribute word timestamps evenly across segments when word-level
    timestamps are unavailable."""
    words = transcript.split()
    if not words:
        return []

    # Get total duration from segments
    segments = result.get("segments", [])
    if segments:
        total_duration = float(segments[-1].get("end", len(words) * 0.4))
    else:
        total_duration = len(words) * 0.4  # 0.4s per word estimate

    interval = total_duration / len(words) if words else 0.4
    return [
        WordTimestamp(
            word=w,
            start=round(i * interval, 3),
            end=round((i + 1) * interval, 3),
        )
        for i, w in enumerate(words)
    ]
