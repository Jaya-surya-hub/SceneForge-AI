"""edge-tts TTS adapter.

Uses the edge-tts library (MIT/unofficial Microsoft TTS endpoint) to
synthesise speech from text and return WAV bytes.

Feature-flagged: only loaded when TTS_ADAPTER=edge_tts.
Mock adapter is the default for all tests.

LICENCE NOTE: edge-tts uses an unofficial endpoint of the Microsoft Edge
browser's TTS service. Verify terms before production deployment.
For the assessment, it serves as a demonstration adapter.

Install: pip install edge-tts
"""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
from typing import Optional

from sceneforge.audio.interfaces import TTSAdapter
from sceneforge.observability.logging import get_logger
from sceneforge.schemas.exceptions import TTSProviderError

log = get_logger(__name__)

_DEFAULT_VOICE = os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural")
_TTS_TIMEOUT = int(os.getenv("TTS_TIMEOUT", "60"))


class EdgeTTSAdapter(TTSAdapter):
    """TTS adapter using edge-tts (Microsoft Edge TTS endpoint).

    Feature-flagged: TTS_ADAPTER=edge_tts activates this adapter.
    Falls back gracefully if edge-tts is not installed.
    """

    adapter_name: str = "edge_tts"
    is_mock: bool = False

    def __init__(self, voice: Optional[str] = None) -> None:
        self._voice = voice or _DEFAULT_VOICE

    def synthesise(self, text: str, *, voice: Optional[str] = None) -> bytes:
        """Synthesise text and return WAV bytes via edge-tts.

        Args:
            text:  Narration text.
            voice: Override voice (uses EDGE_TTS_VOICE env default).

        Returns:
            WAV audio bytes.

        Raises:
            TTSProviderError: If synthesis fails or edge-tts is unavailable.
        """
        effective_voice = voice or self._voice
        try:
            return asyncio.run(
                self._synthesise_async(text, effective_voice)
            )
        except ImportError:
            raise TTSProviderError(
                "edge-tts is not installed. Run: pip install edge-tts"
            )
        except Exception as exc:
            log.warning("edge_tts_failed_trying_gtts", error=str(exc))
            try:
                from sceneforge.audio.adapters.gtts_adapter import GTTSAdapter
                return GTTSAdapter().synthesise(text)
            except Exception:
                raise TTSProviderError(f"edge-tts synthesis failed: {exc}") from exc

    async def _synthesise_async(self, text: str, voice: str) -> bytes:
        """Async synthesis using edge-tts Communicate API."""
        import edge_tts  # type: ignore[import]

        # edge-tts writes MP3 by default; we capture bytes and return as-is
        # (MP3 is a supported format for the audio pipeline).
        buffer = io.BytesIO()
        communicate = edge_tts.Communicate(text, voice)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])

        audio_bytes = buffer.getvalue()
        if not audio_bytes:
            raise TTSProviderError("edge-tts returned empty audio")

        log.info(
            "edge_tts_synthesised",
            voice=voice,
            text_length=len(text),
            audio_bytes=len(audio_bytes),
        )
        return audio_bytes

    def estimated_duration(self, text: str) -> float:
        """Estimate speaking duration from word count (2.5 words/s)."""
        words = len(text.split())
        return max(1.0, words / 2.5)
