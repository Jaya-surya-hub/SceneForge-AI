"""Rights serialiser — write rights.json and integrate with manifest.

Produces the rights.json artifact defined in §5 of the assessment brief.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sceneforge.rights.passport import RightsRecord


def rights_to_dict(records: list[RightsRecord], *, job_id: str) -> dict[str, Any]:
    """Convert a list of RightsRecords to a JSON-serialisable dict."""
    return {
        "job_id": job_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "records": [r.to_dict() for r in records],
    }


def serialise_rights(
    records: list[RightsRecord],
    *,
    job_id: str,
    indent: int = 2,
) -> str:
    """Serialise rights records to JSON string."""
    data = rights_to_dict(records, job_id=job_id)
    return json.dumps(data, indent=indent, default=str)


def validate_rights_coverage(
    records: list[RightsRecord],
    expected_scene_ids: list[str],
) -> list[str]:
    """Verify that every scene has a rights record.

    Args:
        records:           The rights records produced for this job.
        expected_scene_ids: Scene IDs that must have coverage.

    Returns:
        List of error strings (empty = full coverage).
    """
    covered = {r.scene_id for r in records if r.scene_id}
    errors = []
    for scene_id in expected_scene_ids:
        if scene_id not in covered:
            errors.append(f"No rights record for scene '{scene_id}'.")
    return errors
