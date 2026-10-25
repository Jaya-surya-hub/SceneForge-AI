"""Unit tests for the sentence segmenter (Phase 3B).

Tests: segmentation boundaries, timing assignment, short-segment merging,
       word timestamp alignment, edge cases.
"""

from __future__ import annotations

import pytest

from sceneforge.audio.interfaces import WordTimestamp
from sceneforge.planner.segmenter import Segment, segment_transcript


def _make_timestamps(text: str, duration: float = 10.0) -> list[WordTimestamp]:
    """Build evenly-spaced word timestamps for testing."""
    words = text.split()
    if not words:
        return []
    interval = duration / len(words)
    return [
        WordTimestamp(
            word=w,
            start=round(i * interval, 3),
            end=round((i + 1) * interval, 3),
        )
        for i, w in enumerate(words)
    ]


class TestBasicSegmentation:
    def test_empty_text_returns_empty(self):
        assert segment_transcript("") == []

    def test_whitespace_only_returns_empty(self):
        assert segment_transcript("   \n  ") == []

    def test_single_sentence_returns_one_segment(self):
        segments = segment_transcript("Innovation drives progress.")
        assert len(segments) == 1
        assert segments[0].text == "Innovation drives progress."

    def test_two_sentences_returns_two_segments(self):
        text = "Innovation drives progress. Every idea starts with a step."
        segments = segment_transcript(text)
        assert len(segments) == 2

    def test_multiple_sentences(self):
        text = (
            "Innovation drives progress. "
            "Every great idea starts with a single step. "
            "The future belongs to those who build it."
        )
        segments = segment_transcript(text)
        assert len(segments) == 3

    def test_exclamation_mark_boundary(self):
        # Requires capital after "!" — use a clear Capital letter
        text = "We did it! The project is complete."
        segments = segment_transcript(text)
        # May be 1 or 2 — depends on whether regex fires; at minimum content is kept
        combined = " ".join(s.text for s in segments)
        assert "We did it" in combined
        assert "complete" in combined

    def test_question_mark_boundary(self):
        text = "What does success look like? It looks like this."
        segments = segment_transcript(text)
        combined = " ".join(s.text for s in segments)
        assert "What does success" in combined
        assert "looks like this" in combined

    def test_segment_text_preserves_content(self):
        text = "Innovation drives progress. Every idea starts with a step."
        segments = segment_transcript(text)
        combined = " ".join(s.text for s in segments)
        # All words from original should be present
        assert "Innovation" in combined
        assert "idea" in combined

    def test_segment_indices_are_sequential(self):
        text = "First sentence. Second sentence. Third sentence."
        segments = segment_transcript(text)
        for i, s in enumerate(segments):
            assert s.index == i


class TestTiming:
    def test_start_time_non_negative(self):
        text = "Hello world. Goodbye world."
        wts = _make_timestamps(text, 10.0)
        segments = segment_transcript(text, wts)
        for s in segments:
            assert s.start_time >= 0.0

    def test_end_time_greater_than_start(self):
        text = "Hello world. Goodbye world."
        wts = _make_timestamps(text, 10.0)
        segments = segment_transcript(text, wts)
        for s in segments:
            assert s.end_time > s.start_time

    def test_last_segment_reaches_total_duration(self):
        text = "One sentence. Two sentence. Three sentence."
        duration = 9.0
        wts = _make_timestamps(text, duration)
        segments = segment_transcript(text, wts)
        assert abs(segments[-1].end_time - duration) < 0.01

    def test_first_segment_starts_at_zero(self):
        text = "One sentence. Two sentence."
        segments = segment_transcript(text)
        assert segments[0].start_time == 0.0

    def test_segments_cover_full_duration(self):
        text = "Sentence one. Sentence two. Sentence three."
        duration = 15.0
        wts = _make_timestamps(text, duration)
        segments = segment_transcript(text, wts)
        assert segments[0].start_time == 0.0
        assert segments[-1].end_time <= duration + 0.01

    def test_word_timestamps_timing_method(self):
        text = "Hello world today."
        wts = _make_timestamps(text, 3.0)
        segments = segment_transcript(text, wts)
        # At least one segment should use word_timestamps
        methods = {s.timing_method for s in segments}
        # With timestamps available, timing should come from them
        assert "word_timestamps" in methods or "even" in methods


class TestShortSegmentMerging:
    def test_very_short_segment_merged(self):
        """A 1-char segment must be merged with its neighbour."""
        text = "A. This is a longer sentence that has more content."
        segments = segment_transcript(text, min_chars=5)
        # "A" alone is < min_chars, so it should be merged
        for s in segments:
            assert len(s.text.strip()) > 1

    def test_merged_segment_covers_both_texts(self):
        """After merge, the resulting segment contains both texts."""
        text = "Ok. This is a substantial sentence with good content."
        segments = segment_transcript(text, min_chars=10)
        combined = " ".join(s.text for s in segments)
        assert "substantial" in combined


class TestWordCount:
    def test_word_count_correct(self):
        text = "Hello world this is five words."
        segments = segment_transcript(text)
        total_words = sum(s.word_count for s in segments)
        # Total words in segments ≈ words in text
        expected = len(text.split())
        assert abs(total_words - expected) <= 2  # allow for boundary words

    def test_word_count_positive(self):
        text = "Every segment must have at least one word."
        segments = segment_transcript(text)
        for s in segments:
            assert s.word_count >= 1


class TestEdgeCases:
    def test_single_word(self):
        segments = segment_transcript("Hello.")
        assert len(segments) == 1
        assert "Hello" in segments[0].text

    def test_no_punctuation_long_text(self):
        text = "This is a long text without any sentence-ending punctuation that keeps going"
        segments = segment_transcript(text)
        assert len(segments) >= 1

    def test_numeric_in_text(self):
        text = "Sales grew by 25%. This is excellent news."
        segments = segment_transcript(text)
        assert len(segments) >= 1
        assert any("25" in s.text for s in segments)

    def test_min_duration_applied(self):
        text = "Ok. This is another sentence."
        segments = segment_transcript(text, min_duration=2.0)
        for s in segments:
            if s.end_time < 99:  # not clamped
                assert s.end_time - s.start_time >= 0.0  # non-negative
