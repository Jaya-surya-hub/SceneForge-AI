"""Unit tests for AudioInspector — uses MockAudioInspector only.

FfprobeAudioInspector is tested via integration tests when ffprobe is available.
All tests here run without any external tools or API keys.
"""

from __future__ import annotations

import pytest

from sceneforge.audio.adapters.audio_inspector import MockAudioInspector
from sceneforge.audio.interfaces import AudioMetadata
from sceneforge.schemas.exceptions import CorruptedAudioError, UnsupportedAudioFormatError


class TestMockAudioInspector:
    """Tests for MockAudioInspector — the default for all no-key tests."""

    def test_returns_audio_metadata(self):
        inspector = MockAudioInspector()
        meta = inspector.inspect(b"\x00" * 100)
        assert isinstance(meta, AudioMetadata)

    def test_default_values(self):
        inspector = MockAudioInspector()
        meta = inspector.inspect(b"\x00" * 100)
        assert meta.duration_seconds == 5.0
        assert meta.sample_rate == 22050
        assert meta.channels == 1
        assert meta.codec == "pcm_s16le"
        assert meta.format_name == "wav"
        assert meta.has_speech is True
        assert meta.is_silent is False
        assert meta.is_music_only is False

    def test_custom_duration(self):
        inspector = MockAudioInspector(duration=10.5)
        meta = inspector.inspect(b"\x00" * 100)
        assert meta.duration_seconds == 10.5

    def test_silent_configuration(self):
        inspector = MockAudioInspector(is_silent=True, duration=5.0)
        meta = inspector.inspect(b"\x00" * 100)
        assert meta.is_silent is True

    def test_music_only_configuration(self):
        inspector = MockAudioInspector(is_music_only=True, has_speech=False)
        meta = inspector.inspect(b"\x00" * 100)
        assert meta.is_music_only is True
        assert meta.has_speech is False

    def test_raise_corrupted(self):
        inspector = MockAudioInspector(raise_corrupted=True)
        with pytest.raises(CorruptedAudioError):
            inspector.inspect(b"\x00" * 100)

    def test_raise_unsupported(self):
        inspector = MockAudioInspector(raise_unsupported=True)
        with pytest.raises(UnsupportedAudioFormatError):
            inspector.inspect(b"\x00" * 100)

    def test_deterministic_results(self):
        """Same inspector returns same result for different inputs (mock)."""
        inspector = MockAudioInspector(duration=3.0)
        m1 = inspector.inspect(b"\x00" * 50)
        m2 = inspector.inspect(b"\xff" * 200)
        assert m1.duration_seconds == m2.duration_seconds == 3.0

    def test_zero_duration_configuration(self):
        inspector = MockAudioInspector(duration=0.0)
        meta = inspector.inspect(b"\x00" * 100)
        assert meta.duration_seconds == 0.0

    def test_has_speech_none(self):
        inspector = MockAudioInspector(has_speech=None)
        meta = inspector.inspect(b"\x00" * 100)
        assert meta.has_speech is None


class TestFfprobeInspectorAvailability:
    """Test that FfprobeAudioInspector degrades gracefully when ffprobe is absent."""

    def test_corrupted_bytes_raises_corrupted_error(self, monkeypatch):
        """FfprobeAudioInspector should raise CorruptedAudioError, not crash."""
        from sceneforge.audio.adapters.audio_inspector import FfprobeAudioInspector

        inspector = FfprobeAudioInspector()

        # Patch _run to simulate ffprobe returning error
        def fake_run(args, timeout):
            return "", "Invalid data found when processing input", 1

        import sceneforge.audio.adapters.audio_inspector as mod
        monkeypatch.setattr(mod, "_run", fake_run)

        with pytest.raises(CorruptedAudioError):
            inspector.inspect(b"RIFF\x00\x00\x00\x00WAVE")

    def test_empty_bytes_raises_corrupted_error(self):
        from sceneforge.audio.adapters.audio_inspector import FfprobeAudioInspector

        inspector = FfprobeAudioInspector()
        with pytest.raises(CorruptedAudioError):
            inspector.inspect(b"")

    def test_valid_wav_parsed_correctly(self, monkeypatch):
        """FfprobeAudioInspector correctly parses ffprobe JSON output."""
        from sceneforge.audio.adapters.audio_inspector import FfprobeAudioInspector
        import json

        fake_probe = {
            "streams": [{
                "codec_type": "audio",
                "codec_name": "pcm_s16le",
                "sample_rate": "22050",
                "channels": 1,
                "duration": "5.0",
            }],
            "format": {
                "format_name": "wav",
                "duration": "5.0",
            },
        }

        call_count = [0]

        def fake_run(args, timeout):
            call_count[0] += 1
            if "ffprobe" in args[0]:
                return json.dumps(fake_probe), "", 0
            # ffmpeg calls return empty (no silence / volume analysis needed)
            return "", "", 0

        import sceneforge.audio.adapters.audio_inspector as mod
        monkeypatch.setattr(mod, "_run", fake_run)

        from tests.fixtures.audio_factory import silence_wav
        inspector = FfprobeAudioInspector()
        meta = inspector.inspect(silence_wav(5.0))

        assert meta.duration_seconds == 5.0
        assert meta.sample_rate == 22050
        assert meta.codec == "pcm_s16le"
        assert meta.channels == 1
        assert call_count[0] >= 1  # ffprobe was called

    def test_no_audio_stream_raises_unsupported(self, monkeypatch):
        from sceneforge.audio.adapters.audio_inspector import FfprobeAudioInspector
        import json

        fake_probe = {"streams": [{"codec_type": "video"}], "format": {}}

        def fake_run(args, timeout):
            if "ffprobe" in args[0]:
                return json.dumps(fake_probe), "", 0
            return "", "", 0

        import sceneforge.audio.adapters.audio_inspector as mod
        monkeypatch.setattr(mod, "_run", fake_run)

        inspector = FfprobeAudioInspector()
        with pytest.raises(UnsupportedAudioFormatError):
            inspector.inspect(b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 50)
