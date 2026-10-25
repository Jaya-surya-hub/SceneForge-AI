"""Abstract interfaces for audio adapters.

All TTS, STT, and audio inspection implementations must satisfy these protocols.
Adapters are injected via the provider registry so the pipeline never imports
concrete implementations directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WordTimestamp:
    word: str
    start: float  # seconds
    end: float    # seconds


@dataclass
class NarrationResult:
    """Output of the audio pipeline stage."""

    audio_path: str                          # MinIO object key
    transcript: str
    word_timestamps: list[WordTimestamp]
    duration_seconds: float
    tts_used: bool
    adapter_name: str                        # e.g. "mock", "whisper", "edge_tts"
    warnings: list[str] = field(default_factory=list)
    is_mock: bool = False                    # True when a mock adapter was used
    audio_bytes: Optional[bytes] = None      # Raw audio bytes generated or provided


@dataclass
class AudioMetadata:
    duration_seconds: float
    sample_rate: int
    channels: int
    codec: str
    format_name: str
    has_speech: Optional[bool] = None       # None = not detected
    is_silent: bool = False
    is_music_only: bool = False


class TTSAdapter(ABC):
    """Text-to-speech adapter interface."""

    adapter_name: str = "base"
    is_mock: bool = False

    @abstractmethod
    def synthesise(self, text: str, *, voice: Optional[str] = None) -> bytes:
        """Synthesise *text* and return WAV bytes.

        Args:
            text:  The narration text to synthesise.
            voice: Optional voice identifier (adapter-specific).

        Returns:
            WAV file bytes.
        """

    @abstractmethod
    def estimated_duration(self, text: str) -> float:
        """Return an estimated duration in seconds without full synthesis."""


class STTAdapter(ABC):
    """Speech-to-text adapter interface."""

    adapter_name: str = "base"
    is_mock: bool = False

    @abstractmethod
    def transcribe(self, audio_bytes: bytes) -> tuple[str, list[WordTimestamp]]:
        """Transcribe *audio_bytes* (WAV/MP3/etc.).

        Returns:
            (transcript_text, word_timestamps)
        """


class AudioInspector(ABC):
    """Audio file metadata inspector."""

    @abstractmethod
    def inspect(self, audio_bytes: bytes) -> AudioMetadata:
        """Return metadata for the given audio bytes."""
