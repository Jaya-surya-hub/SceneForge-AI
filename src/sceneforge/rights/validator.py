"""Rights validator — checks RightsRecord against the configured policy.

Policy is controlled by environment variables:
  ROUTER_REQUIRE_VERIFIED_LICENCE=true  (default)
  ROUTER_ALLOW_UNVERIFIED_MEDIA=false   (default)

Validation checks (all applied):
  1. Licence name must be present and not "unknown".
  2. commercial_use_eligible must be True (or None if allow_unverified=True).
  3. asset_id must be non-empty.
  4. source_url must be non-empty (for non-programmatic assets).

A failing check raises LicenceVerificationError when policy requires it,
or adds a warning string when the policy permits continuation.
"""

from __future__ import annotations

import os

from sceneforge.observability.logging import get_logger
from sceneforge.rights.passport import RightsRecord
from sceneforge.schemas.exceptions import LicenceVerificationError

log = get_logger(__name__)

_REQUIRE_VERIFIED = os.getenv("ROUTER_REQUIRE_VERIFIED_LICENCE", "true").lower() == "true"
_ALLOW_UNVERIFIED = os.getenv("ROUTER_ALLOW_UNVERIFIED_MEDIA", "false").lower() == "true"


def validate_record(
    record: RightsRecord,
    *,
    require_verified: bool = _REQUIRE_VERIFIED,
    allow_unverified: bool = _ALLOW_UNVERIFIED,
) -> list[str]:
    """Validate a RightsRecord against policy.

    Args:
        record:            The record to validate.
        require_verified:  Raise on unverified/unknown commercial use.
        allow_unverified:  If True, unknown commercial use is permitted.

    Returns:
        List of warning strings (empty = all clear).

    Raises:
        LicenceVerificationError: When a hard policy violation is detected
                                  and require_verified is True.
    """
    warnings: list[str] = []

    # Check 1: Licence name must be present and not "unknown"
    if not record.licence_name or record.licence_name.lower() in ("", "unknown"):
        msg = f"Asset '{record.asset_id}' has no valid licence name."
        if require_verified:
            raise LicenceVerificationError(record.asset_id)
        warnings.append(f"LICENCE_MISSING: {msg}")

    # Check 2: Commercial use eligibility
    if record.commercial_use_eligible is False:
        # Definitively not commercial — always reject
        raise LicenceVerificationError(record.asset_id)

    if record.commercial_use_eligible is None:
        # Unknown/unverified
        if not allow_unverified and require_verified:
            raise LicenceVerificationError(record.asset_id)
        warnings.append(
            f"COMMERCIAL_USE_UNKNOWN: Asset '{record.asset_id}' — "
            "commercial eligibility not verified."
        )

    # Check 3: Asset ID must be non-empty
    if not record.asset_id:
        if require_verified:
            raise LicenceVerificationError("")
        warnings.append("ASSET_ID_MISSING")

    # Check 4: Source URL required for non-programmatic assets
    if record.asset_type != "programmatic" and not record.source_url:
        warnings.append(
            f"SOURCE_URL_MISSING: Asset '{record.asset_id}' has no source URL."
        )

    log.debug(
        "rights_validated",
        asset_id=record.asset_id,
        warnings=len(warnings),
        commercial=record.commercial_use_eligible,
    )
    return warnings
