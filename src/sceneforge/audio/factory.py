"""Adapter factory — select TTS and STT adapters from environment configuration.

TTS_ADAPTER env var:   mock (default) | edge_tts
STT_ADAPTER env var:   mock (default) | whisper

The factory is the only place that imports concrete adapter classes.
All other code depends on the interfaces only.
"""

from __future__ import annotations

import os
from typing import Optional

from sceneforge.audio.interfaces import STTAdapter, TTSAdapter


def get_tts_adapter(override: Optional[str] = None) -> TTSAdapter:
    """Return the configured TTS adapter.

    Args:
        override: If provided, use this adapter name instead of the env var.

    Returns:
        A TTSAdapter instance.
    """
    name = (override or os.getenv("TTS_ADAPTER", "mock")).lower().strip()

    if name in ("gtts", "google"):
        from sceneforge.audio.adapters.gtts_adapter import GTTSAdapter
        return GTTSAdapter()

    if name == "edge_tts":
        from sceneforge.audio.adapters.edge_tts_adapter import EdgeTTSAdapter
        return EdgeTTSAdapter()

    if name == "host_tts":
        from sceneforge.audio.adapters.host_tts import HostTTSAdapter
        return HostTTSAdapter()

    # Default: mock
    from sceneforge.audio.adapters.mock_tts import MockTTSAdapter
    return MockTTSAdapter()


def get_stt_adapter(override: Optional[str] = None) -> STTAdapter:
    """Return the configured STT adapter.

    Args:
        override: If provided, use this adapter name instead of the env var.

    Returns:
        An STTAdapter instance.
    """
    name = (override or os.getenv("STT_ADAPTER", "mock")).lower().strip()

    if name in ("speech_recognition", "google", "sr"):
        from sceneforge.audio.adapters.speech_rec_stt import SpeechRecognitionSTTAdapter
        return SpeechRecognitionSTTAdapter()

    if name == "whisper":
        from sceneforge.audio.adapters.whisper_stt import WhisperSTTAdapter
        return WhisperSTTAdapter()

    # Default: mock
    from sceneforge.audio.adapters.mock_stt import MockSTTAdapter
    return MockSTTAdapter()
