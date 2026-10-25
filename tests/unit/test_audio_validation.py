"""Unit tests for audio validation module (Phase 3A).

Tests: validate_script, validate_audio_bytes, validate_audio_metadata,
       check_script_audio_mismatch, detect_mime_type.

All tests use in-memory bytes — no filesystem access, no ffprobe calls.
"""

from __future__ import annotations

import pytest

from tests.fixtures.audio_factory import (
    corrupted_bytes,
    empty_bytes,
    mp3_magic_bytes,
    ogg_magic_bytes,
    silence_wav,
    wrong_type_bytes,
)
from sceneforge.audio.interfaces import AudioMetadata
from sceneforge.audio.validation import (
    check_script_audio_mismatch,
    detect_mime_type,
    validate_audio_bytes,
    validate_audio_metadata,
    validate_script,
)
from sceneforge.schemas.exceptions import (
    CorruptedAudioError,
    EmptyScriptError,
    FileTooLargeError,
    SpeechNotDetectedError,
    UnsupportedAudioFormatError,
)


# ---------------------------------------------------------------------------
# validate_script
# ---------------------------------------------------------------------------

class TestValidateScript:
    def test_valid_script_passes(self):
        validate_script("Hello world.")  # must not raise

    def test_none_raises(self):
        with pytest.raises(EmptyScriptError):
            validate_script(None)

    def test_empty_string_raises(self):
        with pytest.raises(EmptyScriptError):
            validate_script("")

    def test_whitespace_only_raises(self):
        with pytest.raises(EmptyScriptError):
            validate_script("   \n\t  ")

    def test_single_word_passes(self):
        validate_script("Hi")

    def test_multiline_passes(self):
        validate_script("Line one.\nLine two.\nLine three.")


# ---------------------------------------------------------------------------
# validate_audio_bytes
# ---------------------------------------------------------------------------

class TestValidateAudioBytes:
    def test_valid_wav_returns_mime(self):
        wav = silence_wav(1.0)
        mime = validate_audio_bytes(wav, filename="test.wav")
        assert mime == "audio/wav"

    def test_mp3_magic_accepted(self):
        mime = validate_audio_bytes(mp3_magic_bytes(), filename="test.mp3")
        assert mime == "audio/mpeg"

    def test_ogg_magic_accepted(self):
        mime = validate_audio_bytes(ogg_magic_bytes(), filename="test.ogg")
        assert mime == "audio/ogg"

    def test_empty_bytes_raises_corrupted(self):
        with pytest.raises(CorruptedAudioError):
            validate_audio_bytes(empty_bytes())

    def test_too_short_raises_corrupted(self):
        with pytest.raises(CorruptedAudioError):
            validate_audio_bytes(b"\x00\x01\x02")

    def test_wrong_type_raises_unsupported(self):
        with pytest.raises(UnsupportedAudioFormatError):
            validate_audio_bytes(wrong_type_bytes(), filename="test.txt")

    def test_skip_magic_check_returns_wav(self):
        # When inspector is mock, we skip magic check
        mime = validate_audio_bytes(b"\x00" * 100, skip_magic_check=True)
        assert mime == "audio/wav"

    def test_oversized_raises_file_too_large(self, monkeypatch):
        import sceneforge.audio.validation as v
        monkeypatch.setattr(v, "_MAX_BYTES", 100)
        with pytest.raises(FileTooLargeError):
            validate_audio_bytes(b"\x52\x49\x46\x46" + b"\x00" * 200)


# ---------------------------------------------------------------------------
# detect_mime_type
# ---------------------------------------------------------------------------

class TestDetectMimeType:
    def test_wav_detected(self):
        assert detect_mime_type(silence_wav(0.1)) == "audio/wav"

    def test_mp3_id3_detected(self):
        assert detect_mime_type(mp3_magic_bytes()) == "audio/mpeg"

    def test_mp3_ff_fb_detected(self):
        assert detect_mime_type(b"\xff\xfb" + b"\x00" * 20) == "audio/mpeg"

    def test_ogg_detected(self):
        assert detect_mime_type(ogg_magic_bytes()) == "audio/ogg"

    def test_flac_detected(self):
        assert detect_mime_type(b"fLaC" + b"\x00" * 20) == "audio/flac"

    def test_mp4_ftyp_detected(self):
        data = b"\x00\x00\x00\x18" + b"ftyp" + b"isom" + b"\x00" * 20
        assert detect_mime_type(data) == "audio/mp4"

    def test_unknown_returns_none(self):
        assert detect_mime_type(b"NOTAUDIO_12345678") is None

    def test_empty_returns_none(self):
        assert detect_mime_type(b"") is None


# ---------------------------------------------------------------------------
# validate_audio_metadata
# ---------------------------------------------------------------------------

class TestValidateAudioMetadata:
    def _meta(self, **kwargs) -> AudioMetadata:
        defaults = dict(
            duration_seconds=5.0,
            sample_rate=22050,
            channels=1,
            codec="pcm_s16le",
            format_name="wav",
            has_speech=True,
            is_silent=False,
            is_music_only=False,
        )
        defaults.update(kwargs)
        return AudioMetadata(**defaults)

    def test_normal_metadata_returns_no_warnings(self):
        warnings = validate_audio_metadata(self._meta())
        assert warnings == []

    def test_silent_audio_raises(self):
        with pytest.raises(SpeechNotDetectedError):
            validate_audio_metadata(self._meta(is_silent=True))

    def test_zero_duration_raises(self):
        with pytest.raises(SpeechNotDetectedError):
            validate_audio_metadata(self._meta(duration_seconds=0.0))

    def test_negative_duration_raises(self):
        with pytest.raises(SpeechNotDetectedError):
            validate_audio_metadata(self._meta(duration_seconds=-1.0))

    def test_music_only_returns_warning(self):
        warnings = validate_audio_metadata(self._meta(is_music_only=True))
        assert len(warnings) == 1
        assert "MUSIC_ONLY_SUSPECTED" in warnings[0]

    def test_music_only_warning_says_suspected(self):
        """Music-only must be SUSPECTED not CERTAIN."""
        warnings = validate_audio_metadata(self._meta(is_music_only=True))
        assert "SUSPECTED" in warnings[0] or "heuristic" in warnings[0].lower()

    def test_no_speech_detected_returns_warning(self):
        warnings = validate_audio_metadata(
            self._meta(has_speech=False, is_music_only=False)
        )
        assert any("SPEECH_NOT_DETECTED" in w for w in warnings)

    def test_has_speech_none_no_warning(self):
        """Unknown speech status → no warning (we cannot be certain)."""
        warnings = validate_audio_metadata(self._meta(has_speech=None))
        assert warnings == []

    def test_audio_duration_exceeding_10_minutes_raises(self):
        """Audio > 600 seconds (10 minutes) must raise AudioDurationExceededError."""
        from sceneforge.schemas.exceptions import AudioDurationExceededError
        with pytest.raises(AudioDurationExceededError):
            validate_audio_metadata(self._meta(duration_seconds=601.0))


# ---------------------------------------------------------------------------
# check_script_audio_mismatch (HC-18)
# ---------------------------------------------------------------------------

class TestMismatchDetection:
    def test_identical_script_transcript_no_warning(self):
        warnings = check_script_audio_mismatch(
            "Innovation drives progress every day",
            "Innovation drives progress every day",
        )
        assert warnings == []

    def test_partial_overlap_above_threshold_no_warning(self):
        # 6 of 8 words overlap → 75% > 30% threshold
        warnings = check_script_audio_mismatch(
            "innovation drives progress today in every single place",
            "innovation drives progress today but also elsewhere fast",
            min_word_overlap=0.3,
        )
        assert warnings == []

    def test_low_overlap_raises_warning(self):
        warnings = check_script_audio_mismatch(
            "The quick brown fox jumped over the lazy dog",
            "Solar panels generate renewable electricity from sunlight",
            min_word_overlap=0.3,
        )
        assert len(warnings) == 1
        assert "SCRIPT_AUDIO_MISMATCH" in warnings[0]

    def test_completely_different_warns(self):
        warnings = check_script_audio_mismatch(
            "trust time patience",
            "solar panels electricity",
        )
        assert any("SCRIPT_AUDIO_MISMATCH" in w for w in warnings)

    def test_empty_script_returns_no_warning(self):
        """Empty script → nothing to compare, no mismatch warning."""
        warnings = check_script_audio_mismatch("", "some transcript text here")
        assert warnings == []

    def test_case_insensitive_comparison(self):
        """Mismatch check must be case-insensitive."""
        warnings = check_script_audio_mismatch(
            "Innovation Drives Progress",
            "innovation drives progress",
        )
        assert warnings == []

    def test_punctuation_ignored(self):
        warnings = check_script_audio_mismatch(
            "Hello, world! How are you?",
            "hello world how are you",
        )
        assert warnings == []
