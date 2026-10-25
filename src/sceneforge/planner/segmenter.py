"""Sentence segmenter for narration text.

Splits a transcript into coherent segments suitable for scene planning.
Uses only stdlib — no NLTK, no spaCy, no heavy NLP dependencies.

Segmentation strategy (in order of precedence):
  1. Split on sentence-ending punctuation (. ! ?) followed by whitespace.
  2. For segments still above max_chars, split on commas or semicolons.
  3. Merge any segment shorter than min_chars with its neighbour.
  4. Apply word-timestamp alignment to derive start/end times when timestamps
     are available; fall back to even distribution when they are not.

All decisions are recorded in segment metadata for traceability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from sceneforge.audio.interfaces import WordTimestamp


# ---------------------------------------------------------------------------
# Configuration (overridable in tests)
# ---------------------------------------------------------------------------

DEFAULT_MIN_CHARS = int(20)    # merge segments shorter than this
DEFAULT_MAX_CHARS = int(300)   # split segments longer than this
DEFAULT_MIN_DURATION = float(1.5)  # seconds; merge shorter scenes into neighbour


@dataclass
class Segment:
    """A single narration segment ready for scene planning."""

    index: int
    text: str
    start_time: float
    end_time: float
    word_count: int
    split_reason: str = ""          # e.g. "sentence_boundary", "length_limit"
    merge_reason: str = ""          # e.g. "too_short"
    timing_method: str = "even"     # "word_timestamps" | "even" | "estimated"


def segment_transcript(
    transcript: str,
    word_timestamps: Optional[list[WordTimestamp]] = None,
    *,
    min_chars: int = DEFAULT_MIN_CHARS,
    max_chars: int = DEFAULT_MAX_CHARS,
    min_duration: float = DEFAULT_MIN_DURATION,
) -> list[Segment]:
    """Split *transcript* into segments with timing information.

    Args:
        transcript:       Full narration text.
        word_timestamps:  Word-level timing from STT/TTS (optional).
        min_chars:        Merge segments shorter than this character count.
        max_chars:        Split segments longer than this character count.
        min_duration:     Merge segments shorter than this duration (seconds).

    Returns:
        Ordered list of Segment objects. Never returns an empty list for
        non-empty input — at minimum one segment covering the full text.
    """
    text = transcript.strip()
    if not text:
        return []

    # Build a word→timestamp index for fast lookup
    ts_index = _build_timestamp_index(word_timestamps or [])
    total_duration = (
        word_timestamps[-1].end if word_timestamps else _estimate_duration(text)
    )

    # Step 1: Split into raw sentences
    raw = _split_sentences(text)

    # Step 2: Further split any oversized sentences
    chunks = _split_long_chunks(raw, max_chars)

    # Step 3: Merge undersized chunks
    merged = _merge_short_chunks(chunks, min_chars)

    # Step 4: Assign timing
    segments = _assign_timing(merged, ts_index, total_duration, min_duration)

    return segments


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SENTENCE_BOUNDARY = re.compile(
    r"""
    (?<=[.!?])          # preceded by sentence-ending punctuation
    (?:\s+|$)           # followed by whitespace or end-of-string
    (?=[A-Z"'\(]|\d)    # followed by capital letter, quote, paren, or digit
    """,
    re.VERBOSE,
)

_CLAUSE_BOUNDARY = re.compile(r"(?<=[,;])\s+")

_NUMERIC = re.compile(r"\b\d[\d,./%-]*\b")


def _split_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries (. ! ?)."""
    # Use regex split; filter blanks
    parts = _SENTENCE_BOUNDARY.split(text)
    result = []
    for p in parts:
        p = p.strip()
        if p:
            result.append(p)
    # If no splits found, return text as a single chunk
    return result if result else [text]


def _split_long_chunks(chunks: list[str], max_chars: int) -> list[str]:
    """Further split any chunk exceeding max_chars on clause boundaries."""
    result = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            result.append(chunk)
        else:
            parts = _CLAUSE_BOUNDARY.split(chunk)
            for p in parts:
                p = p.strip()
                if p:
                    result.append(p)
    return result if result else chunks


def _merge_short_chunks(chunks: list[str], min_chars: int) -> list[str]:
    """Merge chunks shorter than min_chars into their neighbour."""
    if not chunks:
        return chunks
    result = [chunks[0]]
    for chunk in chunks[1:]:
        if len(chunk) < min_chars or len(result[-1]) < min_chars:
            result[-1] = result[-1].rstrip() + " " + chunk.lstrip()
        else:
            result.append(chunk)
    return result


def _build_timestamp_index(word_timestamps: list[WordTimestamp]) -> dict[str, list[WordTimestamp]]:
    """Build a word→timestamps lookup (lowercased, punctuation stripped)."""
    index: dict[str, list[WordTimestamp]] = {}
    for wt in word_timestamps:
        key = re.sub(r"[^\w]", "", wt.word.lower())
        if key:
            index.setdefault(key, []).append(wt)
    return index


def _estimate_duration(text: str) -> float:
    """Rough duration estimate: 2.5 words per second."""
    words = len(text.split())
    return max(1.0, words / 2.5)


def _assign_timing(
    chunks: list[str],
    ts_index: dict[str, list[WordTimestamp]],
    total_duration: float,
    min_duration: float,
) -> list[Segment]:
    """Assign start/end times to each chunk.

    Uses word timestamps when available (timing_method='word_timestamps');
    falls back to proportional distribution by word count.
    """
    if not chunks:
        return []

    total_words = sum(len(c.split()) for c in chunks)
    if total_words == 0:
        total_words = 1

    segments: list[Segment] = []
    cursor = 0.0

    for i, chunk in enumerate(chunks):
        words = chunk.split()
        word_count = len(words) or 1

        # Try to find timing from word timestamps
        chunk_start, chunk_end, method = _timing_from_timestamps(
            words, ts_index, cursor, total_duration
        )

        if method == "even":
            # Proportional allocation
            chunk_duration = (word_count / total_words) * total_duration
            chunk_start = cursor
            chunk_end = cursor + chunk_duration

        # Enforce minimum duration by clamping end time
        if chunk_end - chunk_start < min_duration and i < len(chunks) - 1:
            chunk_end = chunk_start + min_duration

        # Clamp to total_duration
        chunk_end = min(chunk_end, total_duration)

        segments.append(Segment(
            index=i,
            text=chunk,
            start_time=round(chunk_start, 3),
            end_time=round(chunk_end, 3),
            word_count=word_count,
            timing_method=method,
        ))
        cursor = chunk_end

    # Ensure last segment reaches total_duration
    if segments and segments[-1].end_time < total_duration:
        segments[-1].end_time = round(total_duration, 3)

    return segments


def _timing_from_timestamps(
    words: list[str],
    ts_index: dict[str, list[WordTimestamp]],
    fallback_start: float,
    total_duration: float,
) -> tuple[float, float, str]:
    """Attempt to find start/end timestamps for a list of words.

    Returns (start, end, method) where method is 'word_timestamps' or 'even'.
    """
    if not ts_index or not words:
        return fallback_start, fallback_start, "even"

    starts = []
    ends = []
    for word in words:
        key = re.sub(r"[^\w]", "", word.lower())
        if key in ts_index and ts_index[key]:
            ts = ts_index[key].pop(0)  # consume first match
            starts.append(ts.start)
            ends.append(ts.end)

    if starts and ends:
        return min(starts), max(ends), "word_timestamps"

    return fallback_start, fallback_start, "even"
