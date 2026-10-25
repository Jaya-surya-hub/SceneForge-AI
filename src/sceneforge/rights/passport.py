"""Rights Passport — creates and validates RightsRecord objects.

A RightsRecord is created for every asset selected by the router.
For programmatic cards (typography/data), a record is created with
asset_type="programmatic" and no external licence required.

Important constraints:
  - sha256_hash is for file IDENTITY, not licence proof.
  - commercial_use_eligible=None means UNKNOWN — never treat as True.
  - Unverified assets are rejected when require_verified_commercial=True.
  - Licence evidence is stored by reference (URL); it is not fetched or
    validated at runtime — that would require network access.
  - We never fabricate licence evidence.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

from sceneforge.observability.logging import get_logger
from sceneforge.retrieval.interfaces import MediaAsset, RouteResult
from sceneforge.schemas.exceptions import LicenceVerificationError

log = get_logger(__name__)


@dataclass
class RightsRecord:
    """Rights and provenance record for a single media asset."""

    record_id: str
    asset_id: str
    provider_name: str
    source_url: str
    provider_asset_url: str
    licence_name: str
    licence_evidence_url: str
    commercial_use_eligible: Optional[bool]     # None = unknown
    commercial_use_verified: Optional[bool]     # None = not yet verified
    attribution_required: bool
    attribution_text: str
    retrieval_timestamp: str                    # ISO 8601 UTC
    sha256_hash: Optional[str]                  # of downloaded bytes; None if not downloaded
    asset_type: Literal["stock", "generated", "programmatic"]
    model_provenance: Optional[str]
    job_id: str
    scene_id: Optional[str]
    # Restriction flags
    restrictions: list[str] = field(default_factory=list)
    review_flags: list[str] = field(default_factory=list)

    @property
    def is_commercially_cleared(self) -> bool:
        """Return True only if eligibility is explicitly True."""
        return self.commercial_use_eligible is True

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "asset_id": self.asset_id,
            "provider_name": self.provider_name,
            "source_url": self.source_url,
            "provider_asset_url": self.provider_asset_url,
            "licence_name": self.licence_name,
            "licence_evidence_url": self.licence_evidence_url,
            "commercial_use_eligible": self.commercial_use_eligible,
            "commercial_use_verified": self.commercial_use_verified,
            "attribution_required": self.attribution_required,
            "attribution_text": self.attribution_text,
            "retrieval_timestamp": self.retrieval_timestamp,
            "sha256_hash": self.sha256_hash,
            "asset_type": self.asset_type,
            "model_provenance": self.model_provenance,
            "job_id": self.job_id,
            "scene_id": self.scene_id,
            "restrictions": self.restrictions,
            "review_flags": self.review_flags,
        }


def compute_sha256(data: bytes) -> str:
    """Return SHA-256 hex digest of *data*.

    This identifies the file contents at retrieval time. It does NOT prove
    ownership or licence validity.
    """
    return hashlib.sha256(data).hexdigest()


def create_rights_record(
    *,
    asset: MediaAsset,
    job_id: str,
    scene_id: Optional[str] = None,
    asset_bytes: Optional[bytes] = None,
) -> RightsRecord:
    """Create a RightsRecord from a MediaAsset.

    Args:
        asset:        The asset for which to create the record.
        job_id:       The job this asset belongs to.
        scene_id:     The scene this asset was selected for.
        asset_bytes:  Downloaded bytes (used to compute SHA-256). None when
                      asset has not been downloaded yet (Phase 2/3 stubs).

    Returns:
        A populated RightsRecord.
    """
    sha256 = (
        compute_sha256(asset_bytes)
        if asset_bytes is not None
        else getattr(asset, "sha256_hash", None)
    )
    timestamp = datetime.now(timezone.utc).isoformat()

    review_flags: list[str] = []
    if asset.commercial_use_eligible is None:
        review_flags.append("COMMERCIAL_USE_UNKNOWN — licence eligibility not verified")
    if not asset.licence_name or asset.licence_name.lower() in ("", "unknown"):
        review_flags.append("LICENCE_NAME_MISSING")
    if not asset.licence_evidence_url:
        review_flags.append("LICENCE_EVIDENCE_URL_MISSING")

    return RightsRecord(
        record_id=f"rights-{uuid.uuid4().hex[:12]}",
        asset_id=asset.asset_id,
        provider_name=asset.provider_name,
        source_url=asset.source_url or "",
        provider_asset_url=asset.provider_asset_url or "",
        licence_name=asset.licence_name or "unknown",
        licence_evidence_url=asset.licence_evidence_url or "",
        commercial_use_eligible=asset.commercial_use_eligible,
        commercial_use_verified=getattr(asset, "commercial_use_verified", None),
        attribution_required=asset.attribution_required,
        attribution_text=asset.attribution_text or "",
        retrieval_timestamp=timestamp,
        sha256_hash=sha256,
        asset_type=asset.asset_type,  # type: ignore[arg-type]
        model_provenance=asset.model_provenance,
        job_id=job_id,
        scene_id=scene_id,
        restrictions=[],
        review_flags=review_flags,
    )


def create_programmatic_record(
    *,
    card_type: str,
    job_id: str,
    scene_id: Optional[str] = None,
) -> RightsRecord:
    """Create a RightsRecord for a programmatically generated card.

    Typography and data cards have no external licence requirements.
    """
    asset_id = f"card-{uuid.uuid4().hex[:8]}"
    return RightsRecord(
        record_id=f"rights-{uuid.uuid4().hex[:12]}",
        asset_id=asset_id,
        provider_name="sceneforge_internal",
        source_url="",
        provider_asset_url="",
        licence_name="SceneForge Internal (programmatic)",
        licence_evidence_url="",
        commercial_use_eligible=True,
        commercial_use_verified=True,
        attribution_required=False,
        attribution_text="",
        retrieval_timestamp=datetime.now(timezone.utc).isoformat(),
        sha256_hash=None,
        asset_type="programmatic",
        model_provenance=None,
        job_id=job_id,
        scene_id=scene_id,
        restrictions=[],
        review_flags=[],
    )
