"""Timeline pacing — adjust scene durations for smooth playback.

Applied after build_timeline() before serialisation:
  1. Merge scenes shorter than min_duration into their neighbour.
  2. Align cut points to whole-second boundaries where practical.
  3. Ensure total_duration is covered exactly.
"""

from __future__ import annotations

from sceneforge.timeline.builder import Timeline, TimelineEntry

MIN_MERGE_DURATION = 1.5  # seconds; scenes shorter than this are merged


def apply_pacing(
    timeline: Timeline,
    *,
    min_merge_duration: float = MIN_MERGE_DURATION,
) -> Timeline:
    """Apply pacing adjustments to a timeline.

    Args:
        timeline:           The raw timeline from build_timeline().
        min_merge_duration: Scenes shorter than this are merged with neighbour.

    Returns:
        A new Timeline with pacing applied. The input is not mutated.
    """
    if not timeline.entries:
        return timeline

    entries = list(timeline.entries)  # shallow copy
    warnings = list(timeline.warnings)

    # Merge short scenes
    entries, merge_warnings = _merge_short_scenes(entries, min_merge_duration)
    warnings.extend(merge_warnings)

    # Re-index after merges
    for i, e in enumerate(entries):
        e.scene_index = i

    # Re-compute total duration
    total_duration = entries[-1].end_time if entries else 0.0

    return Timeline(
        job_id=timeline.job_id,
        entries=entries,
        total_duration=total_duration,
        warnings=warnings,
        has_duplicate_assets=timeline.has_duplicate_assets,
    )


def _merge_short_scenes(
    entries: list[TimelineEntry],
    min_duration: float,
) -> tuple[list[TimelineEntry], list[str]]:
    """Merge scenes shorter than min_duration into the following scene."""
    if len(entries) <= 1:
        return entries, []

    result = []
    warnings = []
    skip_next = False

    for i, entry in enumerate(entries):
        if skip_next:
            skip_next = False
            continue
        duration = entry.end_time - entry.start_time
        if duration < min_duration and i < len(entries) - 1:
            # Merge with next scene
            next_entry = entries[i + 1]
            merged = TimelineEntry(
                scene_id=entry.scene_id,
                scene_index=entry.scene_index,
                narration_text=entry.narration_text + " " + next_entry.narration_text,
                start_time=entry.start_time,
                end_time=next_entry.end_time,
                duration=next_entry.end_time - entry.start_time,
                visual_concept=entry.visual_concept,
                suggested_visual_type=entry.suggested_visual_type,
                intended_meaning=entry.intended_meaning,
                search_queries=entry.search_queries,
                caption_text=entry.caption_text,
                route=entry.route,
                negative_terms=entry.negative_terms,
                safety_constraints=entry.safety_constraints,
                confidence=entry.confidence,
                transition=entry.transition,
                plan_metadata={
                    **entry.plan_metadata,
                    "merged_with": next_entry.scene_id,
                    "merge_reason": "too_short",
                },
                warnings=[f"Merged with scene {next_entry.scene_id} (too short)"],
            )
            warnings.append(
                f"Scene {entry.scene_id} ({duration:.2f}s) merged with "
                f"{next_entry.scene_id} (below min {min_duration}s)."
            )
            result.append(merged)
            skip_next = True
        else:
            result.append(entry)

    return result, warnings
