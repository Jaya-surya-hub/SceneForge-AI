"""Timeline builder — assembles a deterministic timeline from ScenePlans.

Takes an ordered list of ScenePlan objects and produces a TimelineEntry list
suitable for rendering and serialisation.

Responsibilities:
  - Ensure scene timings are non-negative and internally consistent.
  - Scenes must cover the full narration duration.
  - Flag duplicate asset IDs.
  - Apply simple transition metadata.
  - Record selection reasons and routing info from ScenePlans.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from sceneforge.observability.logging import get_logger
from sceneforge.planner.interfaces import ScenePlan

log = get_logger(__name__)

DEFAULT_TRANSITION = "cut"  # "cut" | "fade"
MIN_SCENE_DURATION = 1.0     # seconds


@dataclass
class TimelineEntry:
    """A single entry in the video timeline."""

    scene_id: str
    scene_index: int
    narration_text: str
    start_time: float
    end_time: float
    duration: float
    visual_concept: str
    suggested_visual_type: str
    intended_meaning: str
    search_queries: list[str]
    caption_text: str
    route: str                           # "stock" | "generated" | "card" | "pending"
    asset_id: Optional[str] = None       # filled by retrieval stage
    relevance_score: Optional[float] = None
    selection_reason: str = ""
    rights_record_id: Optional[str] = None
    transition: str = DEFAULT_TRANSITION
    reframe_params: Optional[dict] = None
    negative_terms: list[str] = field(default_factory=list)
    safety_constraints: list[str] = field(default_factory=list)
    confidence: float = 1.0
    warnings: list[str] = field(default_factory=list)
    plan_metadata: dict = field(default_factory=dict)


@dataclass
class Timeline:
    """Complete timeline for a job."""

    job_id: str
    entries: list[TimelineEntry]
    total_duration: float
    warnings: list[str] = field(default_factory=list)
    has_duplicate_assets: bool = False


def build_timeline(
    job_id: str,
    scene_plans: list[ScenePlan],
    *,
    transition: str = DEFAULT_TRANSITION,
    min_scene_duration: float = MIN_SCENE_DURATION,
) -> Timeline:
    """Build a Timeline from a list of ScenePlan objects.

    Args:
        job_id:             Job identifier (for logging).
        scene_plans:        Ordered list from the scene planner.
        transition:         Default transition type ("cut" or "fade").
        min_scene_duration: Scenes shorter than this duration are flagged.

    Returns:
        A Timeline with validated entries and any warnings noted.
    """
    if not scene_plans:
        return Timeline(job_id=job_id, entries=[], total_duration=0.0,
                        warnings=["No scene plans provided."])

    warnings: list[str] = []
    entries: list[TimelineEntry] = []
    seen_asset_ids: set[str] = set()
    has_duplicates = False

    for i, plan in enumerate(scene_plans):
        # Validate timing
        start = max(0.0, plan.start_time)
        end = plan.end_time
        if end <= start:
            end = start + min_scene_duration
            warnings.append(
                f"Scene {i} ({plan.scene_id}): end_time <= start_time; "
                f"adjusted to {end:.2f}s."
            )

        if end - start < min_scene_duration:
            warnings.append(
                f"Scene {i} ({plan.scene_id}): duration "
                f"{end - start:.2f}s < minimum {min_scene_duration}s."
            )

        # Duplicate asset check (asset_id not set yet at planning stage)
        asset_id = plan.plan_metadata.get("asset_id")
        if asset_id:
            if asset_id in seen_asset_ids:
                warnings.append(
                    f"Scene {i}: duplicate asset_id {asset_id!r} detected."
                )
                has_duplicates = True
            else:
                seen_asset_ids.add(asset_id)

        entry = TimelineEntry(
            scene_id=plan.scene_id,
            scene_index=i,
            narration_text=plan.narration_text,
            start_time=round(start, 3),
            end_time=round(end, 3),
            duration=round(end - start, 3),
            visual_concept=plan.visual_concept,
            suggested_visual_type=plan.suggested_visual_type,
            intended_meaning=plan.intended_meaning,
            search_queries=plan.search_queries,
            caption_text=plan.caption_text,
            route=plan.preferred_source_route,
            asset_id=asset_id,
            negative_terms=plan.negative_terms,
            safety_constraints=plan.safety_constraints,
            confidence=plan.confidence,
            transition=transition,
            plan_metadata=plan.plan_metadata,
        )
        entries.append(entry)

    total_duration = entries[-1].end_time if entries else 0.0

    # Ensure no gaps between consecutive scenes
    for j in range(1, len(entries)):
        prev_end = entries[j - 1].end_time
        curr_start = entries[j].start_time
        if curr_start > prev_end + 0.001:
            warnings.append(
                f"Gap detected between scenes {j - 1} and {j}: "
                f"{curr_start - prev_end:.3f}s."
            )
            # Close the gap by extending the previous entry
            entries[j - 1].end_time = curr_start

    log.info(
        "timeline_built",
        job_id=job_id,
        scene_count=len(entries),
        total_duration=total_duration,
        warnings=len(warnings),
    )

    return Timeline(
        job_id=job_id,
        entries=entries,
        total_duration=total_duration,
        warnings=warnings,
        has_duplicate_assets=has_duplicates,
    )
