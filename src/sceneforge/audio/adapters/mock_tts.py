"""Mock TTS adapter — deterministic, no network calls, clearly labelled.

Returns a minimal valid WAV file (44-byte header + silence) for any input.
The adapter identifies itself as "mock" in all logs and output fields.

This adapter MUST NOT be used to claim that real speech was generated.
It exists solely for the no-key test suite (IS-07, MH-08).
"""

from __future__ import annotations

import struct
from typing import Optional

from sceneforge.audio.interfaces import TTSAdapter

# Minimal WAV: 44-byte header, 0 audio frames, 16-bit PCM, 22050 Hz, mono
_WORDS_PER_SECOND = 2.5   # approximate speaking rate for duration estimation


def _build_minimal_wav(sample_rate: int = 22050) -> bytes:
    """Build a valid near-silent WAV file header with 1 second of audio.
    
    Includes a 1-LSB dither pattern so FFmpeg filters (such as loudnorm) do
    not divide by zero or emit NaN floating-point samples on pure 0x00 silence.
    """
    num_samples = sample_rate  # 1 second
    data_size = num_samples * 2  # 16-bit mono = 2 bytes per sample
    # 1-LSB alternating dither (amplitude 1 out of 32767)
    dither = bytes([1 if i % 4 == 0 else 0 for i in range(data_size)])
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,           # chunk size
        1,            # PCM format
        1,            # mono
        sample_rate,
        sample_rate * 2,   # byte rate
        2,            # block align
        16,           # bits per sample
        b"data",
        data_size,
    )
    return header + dither


# Pre-built WAV bytes — same every time (deterministic)
_MOCK_WAV_BYTES: bytes = _build_minimal_wav()


class MockTTSAdapter(TTSAdapter):
    """[MOCK] Deterministic TTS adapter for the no-key test suite.

    Returns silent WAV bytes. Does NOT generate real speech.
    """

    adapter_name: str = "mock"
    is_mock: bool = True

    def synthesise(self, text: str, *, voice: Optional[str] = None) -> bytes:
        """Return silent WAV bytes. Input text is ignored.

        NOTE: This is a MOCK adapter. No speech is generated.
        """
        return _MOCK_WAV_BYTES

    def estimated_duration(self, text: str) -> float:
        """Estimate duration by word count at a fixed speaking rate."""
        words = len(text.split())
        return max(1.0, words / _WORDS_PER_SECOND)
