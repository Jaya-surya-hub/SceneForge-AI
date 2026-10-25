"""Pydantic schemas for job create/read/update API contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class JobCreateRequest(BaseModel):
    """Request body for POST /jobs."""

    script: Optional[str] = Field(
        default=None,
        max_length=100_000,
        description="Narration script text. Required unless voiceover is supplied.",
    )
    voiceover_path: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Path to uploaded voiceover audio file.",
    )
    aspect_ratio: str = Field(
        default="16:9",
        pattern=r"^(16:9|9:16|1:1)$",
        description="Output video aspect ratio: 16:9 | 9:16 | 1:1.",
    )
    burn_captions: bool = Field(
        default=True,
        description="Whether to burn captions directly into the video.",
    )
    video_selection_mode: str = Field(
        default="automatic",
        pattern=r"^(automatic|manual)$",
        description="Video selection mode: automatic | manual",
    )
    tts_adapter: Optional[str] = Field(
        default=None,
        description="TTS adapter to use: mock | gtts | edge_tts | coqui",
    )
    stt_adapter: Optional[str] = Field(
        default=None,
        description="STT adapter to use: mock | speech_recognition | whisper",
    )
    stock_provider: Optional[str] = Field(
        default=None,
        description="Stock footage provider: mock | pexels | pixabay",
    )
    callback_url: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Webhook URL for job completion callbacks.",
    )
    config: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional extra rendering configuration.",
    )

    @model_validator(mode="before")
    @classmethod
    def validate_inputs(cls, data: Any) -> Any:
        if isinstance(data, dict):
            script = data.get("script")
            voiceover = data.get("voiceover_path")
            has_script = bool(script and isinstance(script, str) and script.strip())
            has_voiceover = bool(voiceover and isinstance(voiceover, str) and voiceover.strip())
            if not has_script and not has_voiceover:
                raise ValueError("At least one of 'script' or 'voiceover_path' must be provided.")
            if not has_script and script is not None:
                data["script"] = None
        return data

    @field_validator("script")
    @classmethod
    def script_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("script must not be blank")
        return v


class JobStatusResponse(BaseModel):
    """Response for GET /jobs/{id}."""

    job_id: str
    status: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: Optional[bool] = None
    retry_count: int = 0
    created_at: datetime
    updated_at: datetime
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    aspect_ratio: str
    correlation_id: Optional[str] = None

    model_config = {"from_attributes": True, "populate_by_name": True}

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Map ORM Job.id → job_id automatically."""
        if hasattr(obj, "id") and not hasattr(obj, "job_id"):
            # Build from ORM attributes directly
            data = {
                "job_id": str(obj.id),
                "status": obj.status,
                "error_code": obj.error_code,
                "error_message": obj.error_message,
                "retryable": obj.retryable,
                "retry_count": obj.retry_count,
                "created_at": obj.created_at,
                "updated_at": obj.updated_at,
                "queued_at": obj.queued_at,
                "started_at": obj.started_at,
                "completed_at": obj.completed_at,
                "aspect_ratio": obj.aspect_ratio,
                "correlation_id": obj.correlation_id,
            }
            return super().model_validate(data, **kwargs)
        return super().model_validate(obj, **kwargs)


class JobCreateResponse(BaseModel):
    """Response for POST /jobs (new job created) following Integration Standard IS-03."""

    job_id: str
    status: str
    progress: float = 0.0
    result_links: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    correlation_id: Optional[str] = None

    model_config = {"from_attributes": True}


class SceneResponse(BaseModel):
    """A single scene entry in the storyboard."""

    scene_id: str
    scene_index: int
    narration_text: Optional[str]
    start_time: Optional[float]
    end_time: Optional[float]
    visual_concept: Optional[str]
    suggested_visual_type: Optional[str]
    route: Optional[str]
    asset_id: Optional[str]
    relevance_score: Optional[float]
    caption_text: Optional[str]
    status: str
    qa_status: Optional[str]
    plan_data: Optional[dict[str, Any]]

    model_config = {"from_attributes": True}


class StoryboardResponse(BaseModel):
    """Response for GET /jobs/{id}/storyboard."""

    job_id: str
    job_status: str
    scenes: list[SceneResponse]


class ArtifactListResponse(BaseModel):
    """Response for GET /jobs/{id}/artifacts."""

    job_id: str
    artifacts: list[str]


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, str]


# ---------------------------------------------------------------------------
# Manual video selection schemas
# ---------------------------------------------------------------------------

class CandidateClipResponse(BaseModel):
    """A candidate video clip for a scene."""

    asset_id: str
    provider_name: str
    title: str
    description: Optional[str] = None
    source_url: Optional[str] = None
    provider_asset_url: Optional[str] = None
    preview_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    licence_name: str
    licence_evidence_url: Optional[str] = None
    commercial_use_eligible: bool
    attribution_required: bool
    attribution_text: Optional[str] = None
    asset_type: str = "stock"
    relevance_score: float
    rationale: Optional[str] = None
    rank: int = 1
    is_selected: bool = False


class SceneCandidatesResponse(BaseModel):
    """A scene with its candidate clip choices."""

    scene_id: str
    scene_index: int
    narration_text: Optional[str] = None
    visual_concept: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    selected_asset_id: Optional[str] = None
    candidates: list[CandidateClipResponse] = Field(default_factory=list)


class JobCandidatesResponse(BaseModel):
    """Response for GET /jobs/{id}/candidates."""

    job_id: str
    status: str
    video_selection_mode: str = "automatic"
    scenes: list[SceneCandidatesResponse] = Field(default_factory=list)


class SelectClipRequest(BaseModel):
    """Request body for POST /jobs/{id}/select-clip."""

    scene_id: str
    asset_id: str


class RenderJobRequest(BaseModel):
    """Request body for POST /jobs/{id}/render."""

    selections: Optional[dict[str, str]] = None  # {scene_id: asset_id}

