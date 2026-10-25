"""Unit tests for AudioPipeline — the three routing modes and error paths.

All tests use mock adapters and MockAudioInspector; no ffprobe, no network.
Covers hard cases:
  HC-09  Silent audio → SpeechNotDetectedError
  HC-10  Music-only audio → warning issued (not error)
  HC-11  Wrong file type → UnsupportedAudioFormatError
  HC-12  Empty script → EmptyScriptError
  HC-18  Script/audio mismatch → mismatch warning
"""

from __future__ import annotations

import pytest

from tests.fixtures.audio_factory import (
    corrupted_bytes,
    empty_bytes,
    silence_wav,
    speech_like_wav,
    tone_wav,
    wrong_type_bytes,
)
from sceneforge.audio.adapters.audio_inspector import MockAudioInspector
from sceneforge.audio.adapters.mock_stt import MockSTTAdapter
from sceneforge.audio.adapters.mock_tts import MockTTSAdapter
from sceneforge.audio.interfaces import NarrationResult, WordTimestamp
from sceneforge.audio.pipeline import AudioPipeline
from sceneforge.schemas.exceptions import (
    CorruptedAudioError,
    EmptyScriptError,
    SpeechNotDetectedError,
    UnsupportedAudioFormatError,
)


def _make_pipeline(
    *,
    is_silent: bool = False,
    is_music_only: bool = False,
    has_speech: bool = True,
    duration: float = 5.0,
    raise_corrupted: bool = False,
    raise_unsupported: bool = False,
) -> AudioPipeline:
    """Build an AudioPipeline with configured mock dependencies."""
    return AudioPipeline(
        tts_adapter=MockTTSAdapter(),
        stt_adapter=MockSTTAdapter(),
        inspector=MockAudioInspector(
            duration=duration,
            has_speech=has_speech if not is_silent else None,
            is_silent=is_silent,
            is_music_only=is_music_only,
            raise_corrupted=raise_corrupted,
            raise_unsupported=raise_unsupported,
        ),
    )


# ---------------------------------------------------------------------------
# Text-only path
# ---------------------------------------------------------------------------

class TestTextOnly:
    def test_returns_narration_result(self):
        pipeline = _make_pipeline()
        result = pipeline.process(script="Hello world.")
        assert isinstance(result, NarrationResult)

    def test_tts_used_true(self):
        pipeline = _make_pipeline()
        result = pipeline.process(script="Hello world.")
        assert result.tts_used is True

    def test_adapter_name_is_mock(self):
        pipeline = _make_pipeline()
        result = pipeline.process(script="Hello world.")
        assert result.adapter_name == "mock"

    def test_transcript_equals_script(self):
        script = "Innovation drives progress."
        result = _make_pipeline().process(script=script)
        assert result.transcript == script.strip()

    def test_duration_positive(self):
        result = _make_pipeline().process(script="Hello world this is a test.")
        assert result.duration_seconds > 0

    def test_word_timestamps_present(self):
        result = _make_pipeline().process(script="Hello world this is a test.")
        assert len(result.word_timestamps) > 0

    def test_word_timestamps_are_sorted(self):
        result = _make_pipeline().process(script="Word one two three four five.")
        for i in range(1, len(result.word_timestamps)):
            assert result.word_timestamps[i].start >= result.word_timestamps[i - 1].start

    def test_word_timestamps_cover_duration(self):
        result = _make_pipeline().process(script="Hello world.")
        if result.word_timestamps:
            assert result.word_timestamps[-1].end <= result.duration_seconds + 0.01

    def test_is_mock_true(self):
        result = _make_pipeline().process(script="Test")
        assert result.is_mock is True

    def test_no_warnings(self):
        result = _make_pipeline().process(script="Valid script text here.")
        assert result.warnings == []

    # HC-12: Empty script
    def test_empty_script_raises(self):
        """HC-12: Empty script must be rejected."""
        with pytest.raises(EmptyScriptError):
            _make_pipeline().process(script="")

    def test_whitespace_script_raises(self):
        """HC-12 variant: Whitespace-only script must be rejected."""
        with pytest.raises(EmptyScriptError):
            _make_pipeline().process(script="   \n  ")

    def test_none_script_no_audio_raises(self):
        """No script and no audio must raise EmptyScriptError."""
        with pytest.raises(EmptyScriptError):
            _make_pipeline().process(script=None, audio_bytes=None)


# ---------------------------------------------------------------------------
# Audio-only path
# ---------------------------------------------------------------------------

class TestAudioOnly:
    def test_returns_narration_result(self):
        pipeline = _make_pipeline()
        result = pipeline.process(audio_bytes=silence_wav(2.0))
        assert isinstance(result, NarrationResult)

    def test_tts_used_false(self):
        result = _make_pipeline().process(audio_bytes=silence_wav(2.0))
        assert result.tts_used is False

    def test_transcript_not_empty(self):
        """Mock STT returns a fixed transcript."""
        result = _make_pipeline().process(audio_bytes=silence_wav(2.0))
        assert len(result.transcript) > 0

    def test_word_timestamps_present(self):
        result = _make_pipeline().process(audio_bytes=silence_wav(2.0))
        assert isinstance(result.word_timestamps, list)

    def test_duration_from_metadata(self):
        pipeline = _make_pipeline(duration=7.5)
        result = pipeline.process(audio_bytes=silence_wav(2.0))
        assert result.duration_seconds == 7.5

    # HC-09: Silent audio
    def test_silent_audio_raises(self):
        """HC-09: Silent audio must raise SpeechNotDetectedError."""
        pipeline = _make_pipeline(is_silent=True)
        with pytest.raises(SpeechNotDetectedError):
            pipeline.process(audio_bytes=silence_wav(5.0))

    # HC-10: Music-only audio
    def test_music_only_issues_warning(self):
        """HC-10: Music-only audio must issue a warning, not raise an error."""
        pipeline = _make_pipeline(is_music_only=True, has_speech=False)
        result = pipeline.process(audio_bytes=tone_wav(440, 5.0))
        assert any("MUSIC_ONLY_SUSPECTED" in w for w in result.warnings)

    def test_music_only_warning_is_suspected_not_certain(self):
        """HC-10: Warning must say SUSPECTED, not claim certainty."""
        pipeline = _make_pipeline(is_music_only=True, has_speech=False)
        result = pipeline.process(audio_bytes=tone_wav(440, 5.0))
        music_warnings = [w for w in result.warnings if "MUSIC_ONLY" in w]
        assert len(music_warnings) == 1
        assert "SUSPECTED" in music_warnings[0] or "heuristic" in music_warnings[0].lower()

    # HC-11: Wrong file type
    def test_wrong_file_type_raises(self):
        """HC-11: Wrong file type must raise UnsupportedAudioFormatError."""
        pipeline = AudioPipeline(
            tts_adapter=MockTTSAdapter(),
            stt_adapter=MockSTTAdapter(),
            inspector=MockAudioInspector(),
        )
        with pytest.raises(UnsupportedAudioFormatError):
            pipeline.process(
                audio_bytes=wrong_type_bytes(),
                filename="document.txt",
            )

    def test_empty_bytes_raises_corrupted(self):
        pipeline = AudioPipeline(
            tts_adapter=MockTTSAdapter(),
            stt_adapter=MockSTTAdapter(),
            inspector=MockAudioInspector(),
        )
        with pytest.raises(CorruptedAudioError):
            pipeline.process(audio_bytes=empty_bytes())

    def test_inspector_corrupted_error_propagates(self):
        """Inspector raising CorruptedAudioError must propagate through pipeline."""
        pipeline = _make_pipeline(raise_corrupted=True)
        with pytest.raises(CorruptedAudioError):
            pipeline.process(audio_bytes=silence_wav(2.0))


# ---------------------------------------------------------------------------
# Combined (script + audio) path
# ---------------------------------------------------------------------------

class TestCombined:
    def test_returns_narration_result(self):
        pipeline = _make_pipeline()
        result = pipeline.process(
            script="Hello world.",
            audio_bytes=silence_wav(2.0),
        )
        assert isinstance(result, NarrationResult)

    def test_tts_used_false(self):
        result = _make_pipeline().process(
            script="Hello world.",
            audio_bytes=silence_wav(2.0),
        )
        assert result.tts_used is False

    def test_audio_duration_used(self):
        pipeline = _make_pipeline(duration=8.0)
        result = pipeline.process(
            script="Some script text.",
            audio_bytes=silence_wav(2.0),
        )
        assert result.duration_seconds == 8.0

    # HC-18: Script/audio mismatch
    def test_matching_script_and_transcript_no_warning(self):
        """HC-18: When script matches transcript, no mismatch warning."""
        from sceneforge.audio.adapters.mock_stt import _MOCK_TRANSCRIPT

        pipeline = _make_pipeline()
        result = pipeline.process(
            script=_MOCK_TRANSCRIPT,
            audio_bytes=silence_wav(2.0),
        )
        mismatch_warnings = [w for w in result.warnings if "MISMATCH" in w]
        assert len(mismatch_warnings) == 0

    def test_mismatched_script_and_transcript_warns(self):
        """HC-18: When script does not match transcript, mismatch warning issued."""
        pipeline = _make_pipeline()
        result = pipeline.process(
            script="Solar panels generate renewable electricity from sunlight",
            audio_bytes=silence_wav(2.0),
        )
        # MockSTT returns a fixed transcript about innovation; solar script won't match
        mismatch_warnings = [w for w in result.warnings if "MISMATCH" in w]
        assert len(mismatch_warnings) == 1

    def test_combined_empty_script_raises(self):
        """HC-12 in combined mode: empty script must be rejected."""
        with pytest.raises(EmptyScriptError):
            _make_pipeline().process(
                script="",
                audio_bytes=silence_wav(2.0),
            )

    def test_combined_silent_audio_raises(self):
        """HC-09 in combined mode: silent audio must raise."""
        pipeline = _make_pipeline(is_silent=True)
        with pytest.raises(SpeechNotDetectedError):
            pipeline.process(
                script="Valid script.",
                audio_bytes=silence_wav(5.0),
            )


# ---------------------------------------------------------------------------
# Adapter factory
# ---------------------------------------------------------------------------

class TestAdapterFactory:
    def test_default_tts_is_mock(self, monkeypatch):
        monkeypatch.setenv("TTS_ADAPTER", "mock")
        from sceneforge.audio.factory import get_tts_adapter
        adapter = get_tts_adapter()
        assert adapter.is_mock is True
        assert adapter.adapter_name == "mock"

    def test_default_stt_is_mock(self, monkeypatch):
        monkeypatch.setenv("STT_ADAPTER", "mock")
        from sceneforge.audio.factory import get_stt_adapter
        adapter = get_stt_adapter()
        assert adapter.is_mock is True
        assert adapter.adapter_name == "mock"

    def test_override_returns_correct_adapter(self):
        from sceneforge.audio.factory import get_tts_adapter
        adapter = get_tts_adapter(override="mock")
        assert adapter.is_mock is True

    def test_unknown_adapter_name_falls_back_to_mock(self):
        from sceneforge.audio.factory import get_tts_adapter
        adapter = get_tts_adapter(override="nonexistent_adapter")
        assert adapter.is_mock is True

    def test_edge_tts_name_returns_correct_type(self):
        from sceneforge.audio.factory import get_tts_adapter
        from sceneforge.audio.adapters.edge_tts_adapter import EdgeTTSAdapter
        adapter = get_tts_adapter(override="edge_tts")
        assert isinstance(adapter, EdgeTTSAdapter)
        assert adapter.is_mock is False

    def test_whisper_name_returns_correct_type(self):
        from sceneforge.audio.factory import get_stt_adapter
        from sceneforge.audio.adapters.whisper_stt import WhisperSTTAdapter
        adapter = get_stt_adapter(override="whisper")
        assert isinstance(adapter, WhisperSTTAdapter)
        assert adapter.is_mock is False


# ---------------------------------------------------------------------------
# Hard case — concurrent isolation
# ---------------------------------------------------------------------------

class TestConcurrentIsolation:
    def test_two_pipelines_independent(self):
        """Two AudioPipeline instances must not share state."""
        p1 = _make_pipeline(duration=3.0)
        p2 = _make_pipeline(duration=7.0)
        # Text-only uses TTS estimated duration (word-count based), not inspector
        r1 = p1.process(script="First pipeline script.")
        r2 = p2.process(script="Second pipeline script.")
        # Both results are valid NarrationResult instances
        assert isinstance(r1, NarrationResult)
        assert isinstance(r2, NarrationResult)
        # Scripts are preserved in transcript
        assert "First" in r1.transcript
        assert "Second" in r2.transcript

    def test_audio_only_pipelines_use_inspector_duration(self):
        """Audio-only path reads duration from inspector — isolation verified."""
        from tests.fixtures.audio_factory import silence_wav
        p1 = _make_pipeline(duration=3.0)
        p2 = _make_pipeline(duration=7.0)
        r1 = p1.process(audio_bytes=silence_wav(1.0))
        r2 = p2.process(audio_bytes=silence_wav(1.0))
        assert r1.duration_seconds == 3.0
        assert r2.duration_seconds == 7.0
