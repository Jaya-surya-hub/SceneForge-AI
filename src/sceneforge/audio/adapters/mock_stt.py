"""Mock STT adapter — deterministic, no network calls, clearly labelled.

Returns a fixed transcript with synthetic word timestamps for any input.
The adapter identifies itself as "mock" in all logs and output fields.

This adapter MUST NOT be used to claim that real transcription was performed.
It exists solely for the no-key test suite (IS-07, MH-08).
"""

from __future__ import annotations

from sceneforge.audio.interfaces import STTAdapter, WordTimestamp

# Fixed transcript returned for all inputs.
# Word timestamps are evenly spaced at 0.4 s per word starting at t=0.
_MOCK_TRANSCRIPT = (
    "Innovation drives progress. "
    "Every great idea starts with a single step. "
    "The future belongs to those who build it."
)

_MOCK_WORDS = _MOCK_TRANSCRIPT.replace(".", "").replace(",", "").split()
_WORD_INTERVAL = 0.4  # seconds per word


def _build_mock_timestamps() -> list[WordTimestamp]:
    return [
        WordTimestamp(
            word=word,
            start=round(i * _WORD_INTERVAL, 3),
            end=round((i + 1) * _WORD_INTERVAL, 3),
        )
        for i, word in enumerate(_MOCK_WORDS)
    ]


_MOCK_TIMESTAMPS: list[WordTimestamp] = _build_mock_timestamps()
_MOCK_DURATION: float = len(_MOCK_WORDS) * _WORD_INTERVAL


class MockSTTAdapter(STTAdapter):
    """[MOCK] Deterministic STT adapter for the no-key test suite.

    Returns a fixed transcript. Does NOT perform real transcription.
    """

    adapter_name: str = "mock"
    is_mock: bool = True

    def transcribe(self, audio_bytes: bytes) -> tuple[str, list[WordTimestamp]]:
        """Return fixed transcript and word timestamps. Input bytes are ignored.

        NOTE: This is a MOCK adapter. No transcription is performed.
        """
        return _MOCK_TRANSCRIPT, list(_MOCK_TIMESTAMPS)
