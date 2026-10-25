"""Google Text-to-Speech (gTTS) adapter.

Free, reliable, no API key required. Synthesises genuine spoken narration
into MP3 audio bytes.
"""

from __future__ import annotations

import io
import re
from typing import Optional

from sceneforge.audio.interfaces import TTSAdapter
from sceneforge.observability.logging import get_logger
from sceneforge.schemas.exceptions import TTSProviderError

log = get_logger(__name__)

_WORDS_PER_SECOND = 2.4


class GTTSAdapter(TTSAdapter):
    """TTS adapter using Google Text-to-Speech (gTTS)."""

    adapter_name: str = "gtts"
    is_mock: bool = False

    def __init__(self, lang: str = "en") -> None:
        self._lang = lang

    def synthesise(self, text: str, *, voice: Optional[str] = None) -> bytes:
        """Synthesise text into MP3 audio bytes using gTTS."""
        if not text or not text.strip():
            raise TTSProviderError("Cannot synthesise empty text.")

        try:
            from gtts import gTTS
        except ImportError:
            raise TTSProviderError("gTTS is not installed. Run: pip install gTTS")

        lang = voice or self._lang
        last_exc: Optional[Exception] = None
        for tld in ["com", "co.uk", "ca", "co.in"]:
            try:
                tts = gTTS(text=text.strip(), lang=lang, tld=tld)
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                buf.seek(0)
                audio_bytes = buf.read()
                if audio_bytes:
                    log.info(
                        "gtts_synthesised",
                        text_len=len(text),
                        size_bytes=len(audio_bytes),
                        lang=lang,
                        tld=tld,
                    )
                    return audio_bytes
            except Exception as exc:
                last_exc = exc
                import time
                time.sleep(0.5)
                continue

        raise TTSProviderError(f"gTTS synthesis failed across endpoints: {last_exc}") from last_exc

    def estimated_duration(self, text: str) -> float:
        """Estimate spoken duration based on word count."""
        words = len(re.findall(r"\b\w+\b", text))
        return max(1.0, round(words / _WORDS_PER_SECOND, 2))
