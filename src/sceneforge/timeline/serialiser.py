"""Timeline serialiser — write and validate timeline.json.

Produces the timeline.json artifact defined in §5 of the assessment brief.
Validates output against schemas/timeline.schema.json before returning.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sceneforge.observability.logging import get_logger
from sceneforge.timeline.builder import Timeline, TimelineEntry

log = get_logger(__name__)

_SCHEMA_PATH = (
    Path(__file__).parent.parent.parent.parent / "schemas" / "timeline.schema.json"
)


def timeline_to_dict(timeline: Timeline) -> dict[str, Any]:
    """Convert a Timeline to a JSON-serialisable dict matching the schema."""
    return {
        "job_id": timeline.job_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_duration_seconds": timeline.total_duration,
        "scene_count": len(timeline.entries),
        "has_duplicate_assets": timeline.has_duplicate_assets,
        "warnings": timeline.warnings,
        "scenes": [_entry_to_dict(e) for e in timeline.entries],
    }


def _entry_to_dict(entry: TimelineEntry) -> dict[str, Any]:
    return {
        "scene_index": entry.scene_index,
        "scene_id": entry.scene_id,
        "narration_text": entry.narration_text,
        "start_time": entry.start_time,
        "end_time": entry.end_time,
        "duration": entry.duration,
        "visual_concept": entry.visual_concept,
        "suggested_visual_type": entry.suggested_visual_type,
        "intended_meaning": entry.intended_meaning,
        "search_queries": entry.search_queries,
        "caption_text": entry.caption_text,
        "route": entry.route,
        "asset_id": entry.asset_id,
        "relevance_score": entry.relevance_score,
        "selection_reason": entry.selection_reason,
        "rights_record_id": entry.rights_record_id,
        "transition": entry.transition,
        "reframe_params": entry.reframe_params,
        "negative_terms": entry.negative_terms,
        "safety_constraints": entry.safety_constraints,
        "confidence": entry.confidence,
        "warnings": entry.warnings,
        "plan_metadata": entry.plan_metadata,
    }


def serialise_timeline(timeline: Timeline, *, indent: int = 2) -> str:
    """Serialise a Timeline to a JSON string.

    Args:
        timeline: The timeline to serialise.
        indent:   JSON indentation level.

    Returns:
        JSON string.
    """
    data = timeline_to_dict(timeline)
    return json.dumps(data, indent=indent, default=str)


def validate_timeline_dict(data: dict[str, Any]) -> list[str]:
    """Validate a timeline dict against the JSON schema.

    Returns a list of validation error messages (empty = valid).
    Uses jsonschema if available; falls back to structural checks otherwise.
    """
    errors: list[str] = []

    # Structural checks (always run, no jsonschema dependency)
    if "job_id" not in data:
        errors.append("Missing required field: job_id")
    if "generated_at" not in data:
        errors.append("Missing required field: generated_at")
    if "scenes" not in data:
        errors.append("Missing required field: scenes")
        return errors

    for i, scene in enumerate(data.get("scenes", [])):
        prefix = f"Scene {i}"
        if "scene_index" not in scene:
            errors.append(f"{prefix}: missing scene_index")
        if "narration_text" not in scene:
            errors.append(f"{prefix}: missing narration_text")
        start = scene.get("start_time")
        end = scene.get("end_time")
        if start is not None and end is not None:
            if start < 0:
                errors.append(f"{prefix}: start_time {start} is negative")
            if end < start:
                errors.append(f"{prefix}: end_time {end} < start_time {start}")

    # Try jsonschema validation if library available
    try:
        import jsonschema
        if _SCHEMA_PATH.exists():
            schema = json.loads(_SCHEMA_PATH.read_text())
            validator = jsonschema.Draft202012Validator(schema)
            for error in validator.iter_errors(data):
                errors.append(f"Schema: {error.message} (path: {list(error.path)})")
        else:
            log.debug("timeline_schema_not_found", path=str(_SCHEMA_PATH))
    except ImportError:
        log.debug("jsonschema_not_installed", note="skipping schema validation")

    return errors


def validate_timeline(timeline: Timeline) -> list[str]:
    """Validate a Timeline object. Returns list of error strings."""
    data = timeline_to_dict(timeline)
    return validate_timeline_dict(data)
