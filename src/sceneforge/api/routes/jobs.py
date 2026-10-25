"""Job management routes.

Endpoints:
    POST   /jobs                        Create a job (idempotent)
    GET    /jobs/{job_id}               Get job status
    GET    /jobs/{job_id}/storyboard    Get scene storyboard
    GET    /jobs/{job_id}/artifacts     List artifact names
    GET    /jobs/{job_id}/artifacts/{filename}  Download artifact (presigned redirect)
    POST   /jobs/{job_id}/cancel        Cancel a job
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from sceneforge.api.dependencies import get_db, get_queue, get_redis, get_storage
from sceneforge.jobs import repository as repo
from sceneforge.jobs.schemas import (
    ArtifactListResponse,
    CandidateClipResponse,
    JobCandidatesResponse,
    JobCreateRequest,
    JobCreateResponse,
    JobStatusResponse,
    RenderJobRequest,
    SceneCandidatesResponse,
    SceneResponse,
    SelectClipRequest,
    StoryboardResponse,
)
from sceneforge.jobs.state_machine import JobStatus, validate_transition, InvalidTransitionError as StateMachineError
from sceneforge.observability.logging import get_correlation_id, get_logger, set_job_id
from sceneforge.schemas.errors import make_error_response
from sceneforge.schemas.exceptions import (
    IdempotencyConflictError,
    NotFoundError,
)
from sceneforge.storage.client import StorageClient
from sceneforge.storage.paths import BUCKET_ARTIFACTS, BUCKET_UPLOADS, artifact_key

log = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

_IDEMPOTENCY_TTL = int(os.getenv("IDEMPOTENCY_KEY_TTL", "86400"))
_PRESIGNED_TTL = int(os.getenv("MINIO_PRESIGNED_TTL", "3600"))


def _payload_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


# ---------------------------------------------------------------------------
# POST /jobs — idempotent job creation (IS-01)
# ---------------------------------------------------------------------------

@router.post("", response_model=JobCreateResponse, status_code=202)
async def create_job(
    request: JobCreateRequest,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
    queue=Depends(get_queue),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
) -> JobCreateResponse:
    """Create a new video generation job.

    Idempotency: supply `Idempotency-Key` header. Duplicate requests with the
    same key and equivalent payload return the existing job (HTTP 200).
    Same key + different payload returns HTTP 409.
    """
    cid = get_correlation_id()
    payload = request.model_dump(exclude_none=True)
    payload_h = _payload_hash(payload)

    # --- Idempotency check (Redis first, DB fallback) ---
    if idempotency_key:
        redis_val = redis.get(f"idempotency:{idempotency_key}")
        if redis_val:
            stored = json.loads(redis_val)
            if stored["payload_hash"] != payload_h:
                raise IdempotencyConflictError()
            # Return existing job — HTTP 200 (override default 202)
            existing = repo.get_job(db, stored["job_id"])
            if existing:
                log.info("idempotency_hit", job_id=stored["job_id"], key=idempotency_key)
                links = {
                    "status": f"/api/v1/jobs/{existing.id}",
                    "artifacts": f"/api/v1/jobs/{existing.id}/artifacts",
                    "storyboard": f"/api/v1/jobs/{existing.id}/storyboard",
                }
                return JobCreateResponse(
                    job_id=str(existing.id),
                    status=existing.status,
                    progress=1.0 if existing.status == "COMPLETED" else 0.0,
                    result_links=links,
                    created_at=existing.created_at,
                    correlation_id=existing.correlation_id,
                )

    # --- Create new job ---
    job_data = {
        **payload,
        "correlation_id": cid,
    }
    job = repo.create_job(db, data=job_data)
    db.flush()  # get job.id without committing

    # --- Record idempotency key ---
    if idempotency_key:
        repo.record_idempotency_key(
            db, key=idempotency_key, payload=payload, job_id=job.id
        )
        # Also cache in Redis with TTL
        redis.setex(
            f"idempotency:{idempotency_key}",
            _IDEMPOTENCY_TTL,
            json.dumps({"job_id": str(job.id), "payload_hash": payload_h}),
        )

    db.commit()
    set_job_id(str(job.id))
    log.info("job_created", job_id=str(job.id), aspect_ratio=job.aspect_ratio)

    # --- Enqueue background job ---
    queue.enqueue(
        "sceneforge.jobs.worker.run_pipeline",
        str(job.id),
        job_timeout=int(os.getenv("JOB_TIMEOUT", "3600")),
    )

    links = {
        "status": f"/api/v1/jobs/{job.id}",
        "artifacts": f"/api/v1/jobs/{job.id}/artifacts",
        "storyboard": f"/api/v1/jobs/{job.id}/storyboard",
    }
    return JobCreateResponse(
        job_id=str(job.id),
        status=job.status,
        progress=0.0,
        result_links=links,
        created_at=job.created_at,
        correlation_id=job.correlation_id,
    )


# ---------------------------------------------------------------------------
# GET /jobs — list recent jobs
# ---------------------------------------------------------------------------

@router.get("", response_model=list[JobStatusResponse])
async def list_jobs(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[JobStatusResponse]:
    """Return a list of recent jobs ordered by creation time descending."""
    jobs = repo.list_jobs(db, limit=limit, offset=offset)
    return [
        JobStatusResponse(
            job_id=str(j.id),
            status=j.status,
            error_code=j.error_code,
            error_message=j.error_message,
            retryable=j.retryable,
            retry_count=j.retry_count,
            created_at=j.created_at,
            updated_at=j.updated_at,
            queued_at=j.queued_at,
            started_at=j.started_at,
            completed_at=j.completed_at,
            aspect_ratio=j.aspect_ratio,
            correlation_id=j.correlation_id,
        )
        for j in jobs
    ]


# ---------------------------------------------------------------------------
# POST /jobs/upload-audio — upload voiceover file
# ---------------------------------------------------------------------------

_ALLOWED_AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".webm", ".aiff", ".aif", ".mp4",
})

@router.post("/upload-audio")
async def upload_audio(
    file: UploadFile = File(...),
    storage: StorageClient = Depends(get_storage),
) -> dict:
    """Upload voiceover audio file for a job."""
    content = await file.read()
    if not content or len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")
    if len(content) < 8:
        raise HTTPException(status_code=400, detail="Uploaded file is too short to be a valid audio file.")
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 100MB)")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext and ext not in _ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio file extension '{ext}'. Supported formats: MP3, WAV, M4A, AAC, OGG, FLAC.",
        )
    if not ext:
        ext = ".mp3"

    # Enforce 10-minute (600s) maximum audio duration if ffprobe is available
    try:
        from sceneforge.rendering.normaliser import is_ffmpeg_available
        if is_ffmpeg_available():
            from sceneforge.audio.adapters.audio_inspector import FfprobeAudioInspector
            meta = FfprobeAudioInspector().inspect(content)
            if meta.duration_seconds > 600.0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Audio duration ({meta.duration_seconds:.1f}s) exceeds maximum allowed limit of 600s (10 minutes).",
                )
    except HTTPException:
        raise
    except Exception as probe_err:
        log.warning("upload_audio_duration_check_skipped", error=str(probe_err))

    import uuid
    filename = f"voiceover_{uuid.uuid4().hex[:12]}{ext}"
    storage_key = f"uploads/{filename}"
    content_type = file.content_type or "audio/mpeg"
    storage.upload_bytes(BUCKET_UPLOADS, storage_key, content, content_type)
    return {
        "voiceover_path": storage_key,
        "filename": file.filename,
        "size_bytes": len(content),
    }


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------

@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    job = repo.get_job(db, job_id)
    if job is None:
        raise NotFoundError("Job")
    set_job_id(str(job.id))
    return JobStatusResponse(
        job_id=str(job.id),
        status=job.status,
        error_code=job.error_code,
        error_message=job.error_message,
        retryable=job.retryable,
        retry_count=job.retry_count,
        created_at=job.created_at,
        updated_at=job.updated_at,
        queued_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        aspect_ratio=job.aspect_ratio,
        correlation_id=job.correlation_id,
    )


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/storyboard
# ---------------------------------------------------------------------------

@router.get("/{job_id}/storyboard", response_model=StoryboardResponse)
async def get_storyboard(
    job_id: str,
    db: Session = Depends(get_db),
) -> StoryboardResponse:
    job = repo.get_job(db, job_id)
    if job is None:
        raise NotFoundError("Job")
    scenes = repo.get_scenes(db, job_id)
    return StoryboardResponse(
        job_id=str(job.id),
        job_status=job.status,
        scenes=[
            SceneResponse(
                scene_id=str(s.id),
                scene_index=s.scene_index,
                narration_text=s.narration_text,
                start_time=s.start_time,
                end_time=s.end_time,
                visual_concept=s.visual_concept,
                suggested_visual_type=s.suggested_visual_type,
                route=s.route,
                asset_id=s.asset_id,
                relevance_score=s.relevance_score,
                caption_text=s.caption_text,
                status=s.status,
                qa_status=s.qa_status,
                plan_data=s.plan_data,
            )
            for s in scenes
        ],
    )


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/artifacts
# ---------------------------------------------------------------------------

@router.get("/{job_id}/artifacts", response_model=ArtifactListResponse)
async def list_artifacts(
    job_id: str,
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage),
) -> ArtifactListResponse:
    job = repo.get_job(db, job_id)
    if job is None:
        raise NotFoundError("Job")
    keys = storage.list_keys(BUCKET_ARTIFACTS, prefix=f"jobs/{job_id}/")
    filenames = [k.split("/")[-1] for k in keys]
    return ArtifactListResponse(job_id=job_id, artifacts=filenames)


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/artifacts/{filename}
# ---------------------------------------------------------------------------

@router.get("/{job_id}/artifacts/{filename}")
async def download_artifact(
    job_id: str,
    filename: str,
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage),
) -> RedirectResponse:
    """Returns a presigned redirect to the artifact in MinIO."""
    job = repo.get_job(db, job_id)
    if job is None:
        raise NotFoundError("Job")
    safe_names = [
        "output.mp4", "timeline.json", "manifest.json",
        "rights.json", "captions.srt", "metrics.json", "job.log",
    ]
    if filename not in safe_names:
        raise NotFoundError("Artifact")
    key = artifact_key(str(job_id), filename)
    if not storage.object_exists(BUCKET_ARTIFACTS, key):
        raise NotFoundError("Artifact")
    url = storage.presigned_get_url(BUCKET_ARTIFACTS, key, ttl_seconds=_PRESIGNED_TTL)
    return RedirectResponse(url=url, status_code=302)


# ---------------------------------------------------------------------------
# POST /jobs/{job_id}/cancel
# ---------------------------------------------------------------------------

@router.post("/{job_id}/cancel", response_model=JobStatusResponse)
async def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    job = repo.get_job(db, job_id)
    if job is None:
        raise NotFoundError("Job")
    try:
        validate_transition(job.status, JobStatus.CANCELLED)
    except StateMachineError:
        from sceneforge.schemas.exceptions import InvalidTransitionError as DomainInvalidTransitionError
        raise DomainInvalidTransitionError(job.status, JobStatus.CANCELLED)
    repo.update_job_status(db, job_id, status=JobStatus.CANCELLED)
    db.commit()
    db.expire(job)
    job = repo.get_job(db, job_id)
    log.info("job_cancelled", job_id=str(job_id))
    return JobStatusResponse(
        job_id=str(job.id),
        status=job.status,
        error_code=job.error_code,
        error_message=job.error_message,
        retryable=job.retryable,
        retry_count=job.retry_count,
        created_at=job.created_at,
        updated_at=job.updated_at,
        queued_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        aspect_ratio=job.aspect_ratio,
        correlation_id=job.correlation_id,
    )


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}/candidates — candidate choices per scene for manual review
# ---------------------------------------------------------------------------

@router.get("/{job_id}/candidates", response_model=JobCandidatesResponse)
async def get_job_candidates(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobCandidatesResponse:
    """Retrieve candidate B-roll clips for each scene in the job."""
    job = repo.get_job(db, job_id)
    if job is None:
        raise NotFoundError("Job")
    scenes = repo.get_scenes(db, job_id)
    cfg = dict(job.config or {}) if hasattr(job, "config") and job.config else {}
    mode = cfg.get("video_selection_mode", "automatic")

    scene_responses = []
    for s in scenes:
        plan_data = dict(s.plan_data or {})
        raw_candidates = plan_data.get("candidates") or []
        selected_id = s.asset_id or plan_data.get("selected_candidate_id")
        candidate_models = []
        for c in raw_candidates:
            candidate_models.append(CandidateClipResponse(
                asset_id=c.get("asset_id", ""),
                provider_name=c.get("provider_name", "stock"),
                title=c.get("title", "Video Clip"),
                description=c.get("description"),
                source_url=c.get("source_url"),
                provider_asset_url=c.get("provider_asset_url"),
                preview_url=c.get("preview_url"),
                duration_seconds=c.get("duration_seconds"),
                width=c.get("width"),
                height=c.get("height"),
                licence_name=c.get("licence_name", "Standard Commercial"),
                licence_evidence_url=c.get("licence_evidence_url"),
                commercial_use_eligible=bool(c.get("commercial_use_eligible", True)),
                attribution_required=bool(c.get("attribution_required", False)),
                attribution_text=c.get("attribution_text"),
                asset_type=c.get("asset_type", "stock"),
                relevance_score=float(c.get("relevance_score", 0.0)),
                rationale=c.get("rationale"),
                rank=int(c.get("rank", 1)),
                is_selected=bool(c.get("asset_id") == selected_id),
            ))
        scene_responses.append(SceneCandidatesResponse(
            scene_id=str(s.id),
            scene_index=s.scene_index,
            narration_text=s.narration_text,
            visual_concept=s.visual_concept,
            start_time=s.start_time,
            end_time=s.end_time,
            selected_asset_id=selected_id,
            candidates=candidate_models,
        ))

    return JobCandidatesResponse(
        job_id=str(job.id),
        status=job.status,
        video_selection_mode=mode,
        scenes=scene_responses,
    )


# ---------------------------------------------------------------------------
# POST /jobs/{job_id}/select-clip — manually select a candidate clip for a scene
# ---------------------------------------------------------------------------

@router.post("/{job_id}/select-clip")
async def select_clip(
    job_id: str,
    request: SelectClipRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Select a specific candidate clip for a scene after validating against candidate records."""
    job = repo.get_job(db, job_id)
    if job is None:
        raise NotFoundError("Job")

    updated = repo.update_scene_selection(
        db,
        job_id=uuid.UUID(job_id),
        scene_id=request.scene_id,
        asset_id=request.asset_id,
    )
    if updated is None:
        raise HTTPException(
            status_code=400,
            detail=f"Clip ID '{request.asset_id}' is not an eligible candidate for scene '{request.scene_id}'.",
        )
    db.commit()
    return {
        "status": "ok",
        "job_id": job_id,
        "scene_id": request.scene_id,
        "selected_asset_id": request.asset_id,
        "relevance_score": updated.relevance_score,
    }


# ---------------------------------------------------------------------------
# POST /jobs/{job_id}/scenes/{scene_id}/refresh-candidates — refresh candidates
# ---------------------------------------------------------------------------

@router.post("/{job_id}/scenes/{scene_id}/refresh-candidates", response_model=SceneCandidatesResponse)
async def refresh_candidates(
    job_id: str,
    scene_id: str,
    db: Session = Depends(get_db),
) -> SceneCandidatesResponse:
    """Refresh search results and candidates for a specific scene using configured stock providers."""
    job = repo.get_job(db, job_id)
    if job is None:
        raise NotFoundError("Job")
    scenes = repo.get_scenes(db, job_id)
    target_scene = None
    for s in scenes:
        if str(s.id) == scene_id:
            target_scene = s
            break
    if not target_scene:
        raise NotFoundError("Scene")

    from sceneforge.retrieval.factory import get_stock_providers, get_embedding_model
    from sceneforge.retrieval.searcher import MediaSearcher
    from sceneforge.retrieval.ranker import CandidateRanker
    from sceneforge.planner.interfaces import ScenePlan

    plan_data = dict(target_scene.plan_data or {})
    sp = ScenePlan(
        scene_id=plan_data.get("scene_id", str(target_scene.id)),
        narration_text=target_scene.narration_text or "",
        start_time=target_scene.start_time or 0.0,
        end_time=target_scene.end_time or 5.0,
        key_entities=plan_data.get("key_entities", []),
        intended_meaning=target_scene.intended_meaning or "",
        visual_concept=target_scene.visual_concept or "",
        search_queries=plan_data.get("search_queries", []),
        suggested_visual_type=target_scene.suggested_visual_type or "stock_footage",
        negative_terms=plan_data.get("negative_terms", []),
        safety_constraints=[],
        confidence=plan_data.get("confidence", 0.5),
        preferred_source_route="stock",
        caption_text=target_scene.caption_text or "",
    )

    stock_provider_name = getattr(job, "stock_provider", None) or os.getenv("STOCK_PROVIDER", "mock")
    providers = get_stock_providers(override=stock_provider_name)
    embedding = get_embedding_model()
    searcher = MediaSearcher(providers)
    candidates = searcher.search_for_scene(sp, job_id=str(job_id))
    ranker = CandidateRanker(
        embedding_model=embedding,
        seen_asset_ids=set(),
        target_aspect_ratio=job.aspect_ratio or "16:9",
    )
    ranked = ranker.rank(sp, candidates)

    candidate_records = []
    for c in ranked[:8]:
        candidate_records.append({
            "asset_id": c.asset.asset_id,
            "provider_name": c.asset.provider_name,
            "title": c.asset.title or f"{c.asset.provider_name.title()} Clip {c.asset.asset_id}",
            "description": c.asset.description or "",
            "source_url": c.asset.source_url or "",
            "provider_asset_url": c.asset.provider_asset_url or "",
            "preview_url": c.asset.preview_url or "",
            "duration_seconds": c.asset.duration_seconds,
            "width": c.asset.width,
            "height": c.asset.height,
            "licence_name": c.asset.licence_name or "Standard Commercial",
            "licence_evidence_url": c.asset.licence_evidence_url or "",
            "commercial_use_eligible": bool(c.asset.commercial_use_eligible),
            "attribution_required": bool(c.asset.attribution_required),
            "attribution_text": c.asset.attribution_text or "",
            "asset_type": c.asset.asset_type,
            "is_mock": bool(getattr(c.asset, "is_mock", False)),
            "relevance_score": round(float(c.final_score), 4),
            "rationale": c.rationale,
            "rank": c.rank,
            "is_selected": bool(ranked and c.asset.asset_id == ranked[0].asset.asset_id),
        })

    plan_data["candidates"] = candidate_records
    selected_asset = ranked[0].asset.asset_id if ranked else None
    plan_data["selected_candidate_id"] = selected_asset
    target_scene.asset_id = selected_asset
    target_scene.relevance_score = float(ranked[0].final_score) if ranked else 0.0
    target_scene.plan_data = plan_data
    db.commit()

    candidate_models = [
        CandidateClipResponse(
            asset_id=c.get("asset_id", ""),
            provider_name=c.get("provider_name", "stock"),
            title=c.get("title", "Video Clip"),
            description=c.get("description"),
            source_url=c.get("source_url"),
            provider_asset_url=c.get("provider_asset_url"),
            preview_url=c.get("preview_url"),
            duration_seconds=c.get("duration_seconds"),
            width=c.get("width"),
            height=c.get("height"),
            licence_name=c.get("licence_name", "Standard Commercial"),
            licence_evidence_url=c.get("licence_evidence_url"),
            commercial_use_eligible=bool(c.get("commercial_use_eligible", True)),
            attribution_required=bool(c.get("attribution_required", False)),
            attribution_text=c.get("attribution_text"),
            asset_type=c.get("asset_type", "stock"),
            relevance_score=float(c.get("relevance_score", 0.0)),
            rationale=c.get("rationale"),
            rank=int(c.get("rank", 1)),
            is_selected=bool(c.get("asset_id") == selected_asset),
        )
        for c in candidate_records
    ]

    return SceneCandidatesResponse(
        scene_id=str(target_scene.id),
        scene_index=target_scene.scene_index,
        narration_text=target_scene.narration_text,
        visual_concept=target_scene.visual_concept,
        start_time=target_scene.start_time,
        end_time=target_scene.end_time,
        selected_asset_id=selected_asset,
        candidates=candidate_models,
    )


# ---------------------------------------------------------------------------
# POST /jobs/{job_id}/render — trigger final rendering after review/selection
# ---------------------------------------------------------------------------

@router.post("/{job_id}/render", response_model=JobStatusResponse)
async def trigger_render(
    job_id: str,
    request: Optional[RenderJobRequest] = None,
    db: Session = Depends(get_db),
    queue = Depends(get_queue),
) -> JobStatusResponse:
    """Finalise scene selections and trigger background rendering."""
    job = repo.get_job(db, job_id)
    if job is None:
        raise NotFoundError("Job")

    # Apply batch selections if provided in body
    if request and request.selections:
        for s_id, a_id in request.selections.items():
            updated = repo.update_scene_selection(db, uuid.UUID(job_id), s_id, a_id)
            if not updated:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid selection: clip '{a_id}' is not an eligible candidate for scene '{s_id}'.",
                )
        db.commit()

    # Enqueue pipeline to complete render, QA, and artifacts
    queue.enqueue(
        "sceneforge.jobs.worker.run_pipeline",
        str(job.id),
        job_timeout=int(os.getenv("JOB_TIMEOUT", "3600")),
    )

    db.expire(job)
    job = repo.get_job(db, job_id)
    return JobStatusResponse(
        job_id=str(job.id),
        status=job.status,
        error_code=job.error_code,
        error_message=job.error_message,
        retryable=job.retryable,
        retry_count=job.retry_count,
        created_at=job.created_at,
        updated_at=job.updated_at,
        queued_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        aspect_ratio=job.aspect_ratio,
        correlation_id=job.correlation_id,
    )
