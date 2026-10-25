"""SRT subtitle writer.

Generates a standards-compliant SRT file from scene caption data.

SRT format:
    1
    00:00:00,000 --> 00:00:05,000
    Caption text here.

    2
    ...

Rules applied:
  - Timestamps are non-negative and end > start.
  - Minimum subtitle display duration: MIN_DISPLAY_S seconds.
  - Overlapping cues are detected and warned about (not silently fixed).
  - Empty captions are skipped.
  - Long lines are wrapped at MAX_LINE_CHARS characters.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from typing import Optional

from sceneforge.observability.logging import get_logger
from sceneforge.timeline.builder import TimelineEntry

log = get_logger(__name__)

MIN_DISPLAY_S = float(0.5)   # minimum cue duration
MAX_LINE_CHARS = int(42)      # SRT convention for legibility


@dataclass
class SubtitleCue:
    index: int
    start_seconds: float
    end_seconds: float
    text: str

    def to_srt_block(self) -> str:
        return (
            f"{self.index}\n"
            f"{_format_ts(self.start_seconds)} --> {_format_ts(self.end_seconds)}\n"
            f"{self.text}\n"
        )


def build_srt_from_timeline(
    entries: list[TimelineEntry],
    *,
    min_display: float = MIN_DISPLAY_S,
    max_line_chars: int = MAX_LINE_CHARS,
) -> str:
    """Build an SRT string from a list of TimelineEntry objects.

    Args:
        entries:        Timeline entries in scene order.
        min_display:    Minimum cue duration in seconds.
        max_line_chars: Wrap lines at this character count.

    Returns:
        SRT file content as a string. Empty string if no valid cues.
    """
    cues = _entries_to_cues(entries, min_display, max_line_chars)
    if not cues:
        return ""
    _warn_overlapping(cues)
    return "\n".join(cue.to_srt_block() for cue in cues)


def build_srt_from_cues(cues: list[SubtitleCue]) -> str:
    """Build SRT from an already-constructed list of SubtitleCue objects."""
    if not cues:
        return ""
    _warn_overlapping(cues)
    return "\n".join(cue.to_srt_block() for cue in cues)


def validate_srt(srt_text: str) -> list[str]:
    """Validate SRT content and return a list of error strings (empty = valid).

    Checks:
      - At least one cue present.
      - Each cue has an index, two timestamps, and non-empty text.
      - end > start for every cue.
      - Timestamps are non-negative.
    """
    errors: list[str] = []
    if not srt_text.strip():
        errors.append("SRT is empty.")
        return errors

    blocks = [b.strip() for b in srt_text.strip().split("\n\n") if b.strip()]
    if not blocks:
        errors.append("No cue blocks found in SRT.")
        return errors

    _TS_LINE = re.compile(
        r"^(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})$"
    )

    for i, block in enumerate(blocks):
        lines = block.split("\n")
        if len(lines) < 3:
            errors.append(f"Cue {i + 1}: too few lines ({len(lines)}).")
            continue

        # Line 0: index
        try:
            int(lines[0])
        except ValueError:
            errors.append(f"Cue {i + 1}: first line is not a valid index: {lines[0]!r}.")

        # Line 1: timestamps
        m = _TS_LINE.match(lines[1])
        if not m:
            errors.append(f"Cue {i + 1}: invalid timestamp line: {lines[1]!r}.")
            continue

        start_s = _parse_srt_ts(m.group(1))
        end_s = _parse_srt_ts(m.group(2))

        if start_s < 0:
            errors.append(f"Cue {i + 1}: negative start time.")
        if end_s <= start_s:
            errors.append(f"Cue {i + 1}: end ({end_s:.3f}s) <= start ({start_s:.3f}s).")

        # Line 2+: text
        text = "\n".join(lines[2:]).strip()
        if not text:
            errors.append(f"Cue {i + 1}: empty caption text.")

    return errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entries_to_cues(
    entries: list[TimelineEntry],
    min_display: float,
    max_line_chars: int,
) -> list[SubtitleCue]:
    cues = []
    index = 1
    for entry in entries:
        text = (entry.caption_text or entry.narration_text or "").strip()
        if not text:
            continue
        start = max(0.0, entry.start_time)
        end = entry.end_time
        if end - start < min_display:
            end = start + min_display
        # Wrap long lines
        wrapped = "\n".join(textwrap.wrap(text, width=max_line_chars) or [text])
        cues.append(SubtitleCue(
            index=index,
            start_seconds=start,
            end_seconds=end,
            text=wrapped,
        ))
        index += 1
    return cues


def _warn_overlapping(cues: list[SubtitleCue]) -> None:
    for i in range(1, len(cues)):
        if cues[i].start_seconds < cues[i - 1].end_seconds - 0.001:
            log.warning(
                "subtitle_overlap",
                cue_a=cues[i - 1].index,
                cue_b=cues[i].index,
                gap=round(cues[i].start_seconds - cues[i - 1].end_seconds, 3),
            )


def _format_ts(seconds: float) -> str:
    """Convert seconds to SRT timestamp HH:MM:SS,mmm."""
    s = max(0.0, seconds)
    ms = int(round((s % 1) * 1000))
    s_int = int(s)
    hh = s_int // 3600
    mm = (s_int % 3600) // 60
    ss = s_int % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def _parse_srt_ts(ts: str) -> float:
    """Parse SRT timestamp HH:MM:SS,mmm to seconds."""
    try:
        time_part, ms_part = ts.split(",")
        hh, mm, ss = time_part.split(":")
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms_part) / 1000
    except (ValueError, AttributeError):
        return -1.0
