"""JobRepository — all database access for jobs, scenes, rights, and metrics.

No SQL lives outside this module. Routes and workers call repository methods only.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from sceneforge.jobs.models import (
    IdempotencyKey,
    Job,
    Metric,
    RightsRecord,
    Scene,
)


def _payload_hash(payload: dict) -> str:
    """Stable SHA-256 of a JSON-serialised payload (sorted keys)."""
    serialised = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Job CRUD
# ---------------------------------------------------------------------------

def create_job(session: Session, *, data: dict) -> Job:
    """Create and persist a new Job. Does NOT commit — caller commits."""
    cfg = dict(data.get("config") or {})
    if "burn_captions" in data and "burn_captions" not in cfg:
        cfg["burn_captions"] = bool(data["burn_captions"])
    elif "burn_captions" not in cfg:
        cfg["burn_captions"] = True

    if "video_selection_mode" in data and "video_selection_mode" not in cfg:
        cfg["video_selection_mode"] = str(data["video_selection_mode"])
    elif "video_selection_mode" not in cfg:
        cfg["video_selection_mode"] = "automatic"

    job = Job(
        id=str(uuid.uuid4()),
        script=data.get("script"),
        voiceover_path=data.get("voiceover_path"),
        aspect_ratio=data.get("aspect_ratio", "16:9"),
        tts_adapter=data.get("tts_adapter") or os.getenv("TTS_ADAPTER", "mock"),
        stt_adapter=data.get("stt_adapter") or os.getenv("STT_ADAPTER", "mock"),
        stock_provider=data.get("stock_provider") or os.getenv("STOCK_PROVIDER", "mock"),
        callback_url=data.get("callback_url"),
        config=cfg,
        correlation_id=data.get("correlation_id"),
        status="QUEUED",
        queued_at=datetime.now(timezone.utc),
    )
    session.add(job)
    return job


def get_job(session: Session, job_id: uuid.UUID) -> Optional[Job]:
    """Fetch a job by primary key."""
    return session.get(Job, str(job_id))


def get_job_or_raise(session: Session, job_id: uuid.UUID) -> Job:
    """Fetch a job or raise ValueError."""
    job = session.get(Job, str(job_id))
    if job is None:
        raise ValueError(f"Job {job_id} not found")
    return job


def list_jobs(session: Session, *, limit: int = 50, offset: int = 0) -> list[Job]:
    """Return a page of jobs ordered by creation time desc."""
    stmt = select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
    return list(session.scalars(stmt))


def update_job_status(
    session: Session,
    job_id: uuid.UUID,
    *,
    status: str,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    retryable: Optional[bool] = None,
) -> None:
    """Patch job status fields. Does NOT commit."""
    now = datetime.now(timezone.utc)
    values: dict = {"status": status, "updated_at": now}
    if status == "QUEUED":
        values["queued_at"] = now
    elif status in ("VALIDATING", "PLANNING", "RETRIEVING", "RENDERING", "QA"):
        if status == "VALIDATING":
            values["started_at"] = now
    elif status in ("COMPLETED", "FAILED", "CANCELLED"):
        values["completed_at"] = now
    if error_code is not None:
        values["error_code"] = error_code
    if error_message is not None:
        values["error_message"] = error_message
    if retryable is not None:
        values["retryable"] = retryable
    session.execute(update(Job).where(Job.id == str(job_id)).values(**values))


def increment_retry_count(session: Session, job_id: uuid.UUID) -> int:
    """Increment retry_count and return new value."""
    job = get_job_or_raise(session, job_id)
    job.retry_count += 1
    return job.retry_count


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def find_idempotent_job(
    session: Session, *, key: str
) -> Optional[tuple[Job, str]]:
    """Return (Job, payload_hash) for an existing idempotency key, or None."""
    stmt = select(IdempotencyKey).where(IdempotencyKey.key == key)
    ikey = session.scalars(stmt).first()
    if ikey is None:
        return None
    job = session.get(Job, str(ikey.job_id))
    if job is None:
        return None
    return job, ikey.payload_hash


def record_idempotency_key(
    session: Session,
    *,
    key: str,
    payload: dict,
    job_id: uuid.UUID,
) -> IdempotencyKey:
    """Persist an idempotency key after job creation. Does NOT commit."""
    ikey = IdempotencyKey(
        id=str(uuid.uuid4()),
        key=key,
        payload_hash=_payload_hash(payload),
        job_id=str(job_id),
    )
    session.add(ikey)
    return ikey


def compute_payload_hash(payload: dict) -> str:
    return _payload_hash(payload)


# ---------------------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------------------

def upsert_scenes(session: Session, job_id: uuid.UUID, scenes: list[dict]) -> list[Scene]:
    """Replace all scenes for a job with the supplied list."""
    existing = session.scalars(select(Scene).where(Scene.job_id == str(job_id))).all()
    for s in existing:
        session.delete(s)
    session.flush()
    result = []
    for idx, s in enumerate(scenes):
        scene = Scene(
            id=str(uuid.uuid4()),
            job_id=str(job_id),
            scene_index=idx,
            narration_text=s.get("narration_text"),
            start_time=s.get("start_time"),
            end_time=s.get("end_time"),
            visual_concept=s.get("visual_concept"),
            intended_meaning=s.get("intended_meaning"),
            suggested_visual_type=s.get("suggested_visual_type"),
            route=s.get("route"),
            asset_id=s.get("asset_id"),
            relevance_score=s.get("relevance_score"),
            caption_text=s.get("caption_text"),
            timeline_entry=s.get("timeline_entry"),
            plan_data=s.get("plan_data"),
            status=s.get("status", "PENDING"),
        )
        session.add(scene)
        result.append(scene)
    return result


def get_scenes(session: Session, job_id: uuid.UUID) -> list[Scene]:
    stmt = (
        select(Scene)
        .where(Scene.job_id == str(job_id))
        .order_by(Scene.scene_index)
    )
    return list(session.scalars(stmt))


def update_scene_selection(
    session: Session,
    *,
    job_id: uuid.UUID,
    scene_id: str,
    asset_id: str,
) -> Optional[Scene]:
    """Update selected asset for a scene after validating against candidate records."""
    scenes = get_scenes(session, job_id)
    target_scene = None
    for s in scenes:
        if str(s.id) == str(scene_id):
            target_scene = s
            break

    if target_scene is None:
        return None

    plan_data = dict(target_scene.plan_data or {})
    candidates = plan_data.get("candidates") or []

    # Validate that asset_id exists in server-side candidate list
    matched_candidate = None
    for c in candidates:
        if c.get("asset_id") == asset_id:
            matched_candidate = c
            break

    if matched_candidate is None:
        # Asset ID not in candidate list — rejection
        return None

    # Update selection
    target_scene.asset_id = asset_id
    target_scene.relevance_score = float(matched_candidate.get("relevance_score", target_scene.relevance_score or 0.0))
    plan_data["selected_candidate_id"] = asset_id

    # Update is_selected flags in candidates list
    for c in candidates:
        c["is_selected"] = (c.get("asset_id") == asset_id)

    plan_data["candidates"] = candidates
    target_scene.plan_data = plan_data
    session.flush()
    return target_scene



# ---------------------------------------------------------------------------
# Rights records
# ---------------------------------------------------------------------------

def add_rights_record(session: Session, *, job_id: uuid.UUID, data: dict) -> RightsRecord:
    """Add a rights record. Does NOT commit."""
    record = RightsRecord(
        id=str(uuid.uuid4()),
        job_id=str(job_id),
        scene_id=data.get("scene_id"),
        asset_id=data["asset_id"],
        provider_name=data["provider_name"],
        source_url=data.get("source_url"),
        provider_asset_url=data.get("provider_asset_url"),
        licence_name=data["licence_name"],
        licence_evidence_url=data.get("licence_evidence_url"),
        commercial_use_eligible=data.get("commercial_use_eligible", False),
        attribution_required=data.get("attribution_required", False),
        attribution_text=data.get("attribution_text"),
        sha256_hash=data.get("sha256_hash"),
        asset_type=data.get("asset_type", "stock"),
        model_provenance=data.get("model_provenance"),
    )
    session.add(record)
    return record


def get_rights_records(session: Session, job_id: uuid.UUID) -> list[RightsRecord]:
    stmt = select(RightsRecord).where(RightsRecord.job_id == str(job_id))
    return list(session.scalars(stmt))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def upsert_metric(session: Session, job_id: uuid.UUID, data: dict) -> Metric:
    """Create or update the metric row for a job."""
    existing = session.scalars(
        select(Metric).where(Metric.job_id == str(job_id))
    ).first()
    if existing:
        for k, v in data.items():
            setattr(existing, k, v)
        return existing
    metric = Metric(
        id=str(uuid.uuid4()),
        job_id=str(job_id),
        **{k: v for k, v in data.items() if k != "job_id"},
    )
    session.add(metric)
    return metric
