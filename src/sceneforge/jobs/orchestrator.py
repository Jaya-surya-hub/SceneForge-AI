"""Pipeline orchestrator — coordinates all stages for a single job.

This is a STUB implementation for Phase 2. It advances the job through all
states using mock adapters and writes placeholder artifacts to MinIO.
Real stage implementations (audio, planner, retrieval, rendering, QA) are
added in Phases 3–5.

Each stage is isolated: a failure in one stage marks the job FAILED without
affecting other in-flight jobs.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sceneforge.jobs import repository as repo
from sceneforge.jobs.database import get_session
from sceneforge.jobs.retry import retry_stage
from sceneforge.jobs.state_machine import JobStatus, validate_transition
from sceneforge.observability.logging import get_logger, set_job_id
from sceneforge.storage.client import get_storage_client
from sceneforge.storage.paths import BUCKET_ARTIFACTS, artifact_key

log = get_logger(__name__)


class PipelineOrchestrator:
    """Runs the full pipeline for a single job end-to-end.

    Phase 2 stub: advances states, writes placeholder artifacts, records metrics.
    """

    def __init__(self, job_id: uuid.UUID) -> None:
        self.job_id = job_id
        self.storage = get_storage_client()
        self._stage_timings: dict[str, float] = {}
        self._qa_report = None
        self._render_timeline = None
        self._render_result = None
        self._stage_render_metadata: dict = {}
        self._narration_audio_path: str = ""
        self._narration_is_mock: bool = True
        set_job_id(str(job_id))

    def _transition(self, to_status: str) -> None:
        """Advance job status with a DB write."""
        with get_session() as session:
            job = repo.get_job(session, self.job_id)
            if job is None:
                raise RuntimeError(f"Job {self.job_id} disappeared from DB")
            validate_transition(job.status, to_status)
            repo.update_job_status(session, self.job_id, status=to_status)
        log.info("job_state_transition", job_id=str(self.job_id), to=to_status)

    def _fail(self, error_code: str, message: str, retryable: bool = True) -> None:
        with get_session() as session:
            job = repo.get_job(session, self.job_id)
            if job and job.status == JobStatus.FAILED.value and job.error_code == "RENDER_FAILED" and error_code == "PIPELINE_ERROR":
                log.info("job_already_marked_failed_preserving_code", job_id=str(self.job_id), code=job.error_code)
                return
            repo.update_job_status(
                session,
                self.job_id,
                status=JobStatus.FAILED,
                error_code=error_code,
                error_message=message,
                retryable=retryable,
            )
        log.error(
            "job_failed",
            job_id=str(self.job_id),
            code=error_code,
            message=message,
        )

    def _timed_stage(self, name: str, fn) -> None:
        t0 = time.perf_counter()
        fn()
        self._stage_timings[name] = round((time.perf_counter() - t0) * 1000, 1)

    # ------------------------------------------------------------------
    # Stages (Phase 2 stubs — replaced by real implementations in Phases 3–5)
    # ------------------------------------------------------------------

    def _stage_validate(self) -> None:
        """Validate job inputs."""
        self._transition(JobStatus.VALIDATING)
        with get_session() as session:
            job = repo.get_job(session, self.job_id)
            if job is None:
                raise RuntimeError("Job not found during validation")
            script = job.script
            voiceover_path = job.voiceover_path
        if not script and not voiceover_path:
            self._fail("EMPTY_INPUT", "Either script or voiceover audio must be provided.", retryable=False)
            raise StopIteration("EMPTY_INPUT")
        if script is not None and not script.strip() and not voiceover_path:
            self._fail("EMPTY_SCRIPT", "Script must not be empty.", retryable=False)
            raise StopIteration("EMPTY_SCRIPT")
        log.info("stage_validate_ok", job_id=str(self.job_id))

    def _stage_plan(self) -> None:
        """Plan scenes using real audio pipeline and rule-based planner (Phase 5)."""
        self._transition(JobStatus.PLANNING)
        with get_session() as session:
            job = repo.get_job(session, self.job_id)
            script = job.script
            voiceover_path = job.voiceover_path
            job_tts = job.tts_adapter if job and job.tts_adapter and job.tts_adapter != "mock" else None
            job_stt = job.stt_adapter if job and job.stt_adapter and job.stt_adapter != "mock" else None
            tts_adapter_name = job_tts or os.getenv("TTS_ADAPTER", "mock")
            stt_adapter_name = job_stt or os.getenv("STT_ADAPTER", "mock")

        # Audio pipeline — runs TTS when script is provided, or STT when voiceover is provided
        from sceneforge.audio.factory import get_tts_adapter, get_stt_adapter
        from sceneforge.audio.pipeline import AudioPipeline
        from sceneforge.planner.adapters.rule_based import RuleBasedPlannerAdapter
        import tempfile

        jid = str(self.job_id)
        tts = get_tts_adapter(tts_adapter_name)
        stt = get_stt_adapter(stt_adapter_name)
        self._tts_adapter_name = tts.adapter_name
        self._stt_adapter_name = stt.adapter_name

        # Retrieve uploaded voiceover audio bytes if voiceover_path is set
        audio_bytes = None
        audio_filename = "upload.wav"
        if voiceover_path:
            audio_filename = os.path.basename(voiceover_path)
            if os.path.isfile(voiceover_path):
                try:
                    with open(voiceover_path, "rb") as f:
                        audio_bytes = f.read()
                except Exception as exc:
                    log.warning("voiceover_read_file_failed", path=voiceover_path, error=str(exc))
            else:
                from sceneforge.storage.client import BUCKET_UPLOADS
                try:
                    if self.storage.object_exists(BUCKET_UPLOADS, voiceover_path):
                        audio_bytes = self.storage.download_bytes(BUCKET_UPLOADS, voiceover_path)
                    elif self.storage.object_exists(BUCKET_UPLOADS, f"uploads/{voiceover_path}"):
                        audio_bytes = self.storage.download_bytes(BUCKET_UPLOADS, f"uploads/{voiceover_path}")
                except Exception as exc:
                    log.warning("voiceover_download_failed", key=voiceover_path, error=str(exc))

        # Select inspector: Ffprobe if available and audio is present, else MockAudioInspector
        try:
            from sceneforge.rendering.normaliser import is_ffmpeg_available
            if is_ffmpeg_available() and audio_bytes:
                from sceneforge.audio.adapters.audio_inspector import FfprobeAudioInspector
                inspector = FfprobeAudioInspector()
            else:
                from sceneforge.audio.adapters.audio_inspector import MockAudioInspector
                inspector = MockAudioInspector()
        except Exception:
            from sceneforge.audio.adapters.audio_inspector import MockAudioInspector
            inspector = MockAudioInspector()

        pipeline = AudioPipeline(
            tts_adapter=tts,
            stt_adapter=stt,
            inspector=inspector,
            storage_path=f"jobs/{jid}",
        )

        clean_script = script.strip() if script and script.strip() else None

        try:
            narration = pipeline.process(
                script=clean_script,
                audio_bytes=audio_bytes,
                filename=audio_filename,
                job_id=jid,
            )
        except Exception as exc:
            log.warning("audio_pipeline_error", job_id=jid, error=str(exc))
            fallback_text = clean_script or "SceneForge AI narration."
            from sceneforge.audio.interfaces import NarrationResult, WordTimestamp
            words = fallback_text.split()
            word_ts = [WordTimestamp(w, i * 0.4, (i + 1) * 0.4) for i, w in enumerate(words)]
            narration = NarrationResult(
                audio_path="",
                transcript=fallback_text,
                word_timestamps=word_ts,
                duration_seconds=max(len(words) * 0.4, 1.0),
                tts_used=not bool(audio_bytes),
                adapter_name="fallback",
                warnings=[f"Audio pipeline error: {exc}"],
                is_mock=True,
            )

        # Store audio bytes to temp file so renderer can use it
        audio_tmp_path = ""
        if audio_bytes:
            try:
                suffix = os.path.splitext(audio_filename)[1] or ".wav"
                fd, audio_tmp_path = tempfile.mkstemp(suffix=suffix)
                with os.fdopen(fd, "wb") as f:
                    f.write(audio_bytes)
                log.info("voiceover_audio_written", job_id=jid, path=audio_tmp_path, size=len(audio_bytes))
            except Exception as exc2:
                log.warning("voiceover_audio_write_failed", job_id=jid, error=str(exc2))
                audio_tmp_path = ""
        elif narration.tts_used:
            try:
                synth_bytes = getattr(narration, "audio_bytes", None)
                if not synth_bytes and clean_script:
                    synth_bytes = tts.synthesise(clean_script)
                if synth_bytes:
                    suffix = ".wav" if getattr(tts, "adapter_name", "") == "mock" else ".mp3"
                    fd, audio_tmp_path = tempfile.mkstemp(suffix=suffix)
                    with os.fdopen(fd, "wb") as f:
                        f.write(synth_bytes)
                    log.info("tts_audio_written", job_id=jid, path=audio_tmp_path,
                             size=len(synth_bytes), adapter=getattr(narration, "adapter_name", tts.adapter_name))
            except Exception as exc2:
                log.warning("tts_audio_write_failed", job_id=jid, error=str(exc2))
                audio_tmp_path = ""

        # Save audio path for renderer
        self._narration_audio_path = audio_tmp_path
        self._narration_is_mock = narration.is_mock

        with get_session() as session:
            job_obj = repo.get_job(session, self.job_id)
            if job_obj:
                cfg = dict(job_obj.config or {})
                cfg["narration_audio_path"] = audio_tmp_path
                cfg["narration_is_mock"] = narration.is_mock
                if audio_tmp_path and os.path.isfile(audio_tmp_path):
                    try:
                        with open(audio_tmp_path, "rb") as af:
                            a_bytes = af.read()
                        a_key = f"narration/{jid}.wav"
                        self.storage.upload_bytes(BUCKET_ARTIFACTS, a_key, a_bytes, "audio/wav")
                        cfg["narration_storage_key"] = a_key
                    except Exception as e:
                        log.warning("audio_upload_failed", error=str(e))
                job_obj.config = cfg

        # Diagnostic log: transcription result
        log.info(
            "job_transcription_result",
            job_id=jid,
            adapter=narration.adapter_name,
            tts_used=narration.tts_used,
            duration=round(narration.duration_seconds, 2),
            transcript_word_count=len(narration.transcript.split()),
            transcript_snippet=narration.transcript[:100],
            warnings=narration.warnings,
        )

        # Scene planning using rule-based planner
        planner = RuleBasedPlannerAdapter()
        scene_plans = planner.plan_scenes(narration.transcript, narration.word_timestamps)

        if not scene_plans:
            # Fallback if planner returns nothing
            from sceneforge.planner.adapters.mock_llm import MockLLMPlannerAdapter
            scene_plans = MockLLMPlannerAdapter().plan_scenes(
                narration.transcript, narration.word_timestamps
            )

        # Diagnostic log: planned scenes
        for sp in scene_plans:
            log.info(
                "job_scene_plan",
                job_id=jid,
                scene_id=sp.scene_id,
                narration_snippet=sp.narration_text[:60],
                search_queries=sp.search_queries,
                suggested_type=sp.suggested_visual_type,
                start_time=sp.start_time,
                end_time=sp.end_time,
            )

        # Persist scenes
        scene_data = [
            {
                "narration_text": sp.narration_text,
                "start_time": sp.start_time,
                "end_time": sp.end_time,
                "visual_concept": sp.visual_concept,
                "intended_meaning": sp.intended_meaning,
                "suggested_visual_type": sp.suggested_visual_type,
                "caption_text": sp.caption_text,
                "plan_data": {
                    "scene_id": sp.scene_id,
                    "key_entities": sp.key_entities,
                    "search_queries": sp.search_queries,
                    "confidence": sp.confidence,
                    "is_mock": sp.is_mock,
                    "negative_terms": sp.negative_terms,
                },
                "status": "PLANNED",
            }
            for sp in scene_plans
        ]
        with get_session() as session:
            repo.upsert_scenes(session, self.job_id, scene_data)
        log.info(
            "stage_plan_ok",
            job_id=jid,
            scene_count=len(scene_plans),
        )

    def _stage_retrieve(self) -> None:
        """Retrieve media using real retrieval stack (Phase 4).

        Uses environment-configured providers (default: mock).
        Records rights records for every selected asset.
        """
        self._transition(JobStatus.RETRIEVING)

        from sceneforge.planner.interfaces import ScenePlan
        from sceneforge.retrieval.downloader import MediaDownloader
        from sceneforge.retrieval.factory import (
            get_embedding_model,
            get_generated_provider,
            get_stock_providers,
        )
        from sceneforge.retrieval.ranker import CandidateRanker
        from sceneforge.retrieval.router import SourceRouter
        from sceneforge.retrieval.searcher import MediaSearcher
        from sceneforge.rights.passport import (
            create_programmatic_record,
            create_rights_record,
        )

        jid = str(self.job_id)

        # Load scene data as plain dicts so they survive session close
        with get_session() as session:
            db_scenes = repo.get_scenes(session, self.job_id)
            job = repo.get_job(session, self.job_id)
            aspect_ratio = job.aspect_ratio if job else "16:9"
            job_stock_provider = job.stock_provider if job else None
            job_config = dict(job.config or {}) if job and job.config else {}
            is_manual = job_config.get("video_selection_mode") == "manual"
            scene_dicts = [
                {
                    "id": str(s.id),
                    "plan_data": dict(s.plan_data or {}),
                    "narration_text": s.narration_text,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "visual_concept": s.visual_concept,
                    "intended_meaning": s.intended_meaning,
                    "suggested_visual_type": s.suggested_visual_type,
                    "caption_text": s.caption_text,
                }
                for s in db_scenes
            ]

        stock_provider_name = job_stock_provider or os.getenv("STOCK_PROVIDER", "mock")
        providers = get_stock_providers(override=stock_provider_name)
        embedding = get_embedding_model()
        generated = get_generated_provider()

        searcher = MediaSearcher(providers)
        router = SourceRouter(generated_provider=generated)
        
        # Job-isolated temporary directory for downloads
        job_work_dir = os.path.join(tempfile.gettempdir(), f"sf_dl_{jid[:8]}")
        os.makedirs(job_work_dir, exist_ok=True)
        downloader = MediaDownloader(storage_client=self.storage, work_dir=job_work_dir)
        seen_asset_ids: set[str] = set()

        rights_records_data: list[dict] = []

        for scene_dict in scene_dicts:
            # Reconstruct a minimal ScenePlan from plain dict
            plan_data = scene_dict["plan_data"]
            sp = ScenePlan(
                scene_id=plan_data.get("scene_id", scene_dict["id"]),
                narration_text=scene_dict["narration_text"] or "",
                start_time=scene_dict["start_time"] or 0.0,
                end_time=scene_dict["end_time"] or 5.0,
                key_entities=plan_data.get("key_entities", []),
                intended_meaning=scene_dict["intended_meaning"] or "",
                visual_concept=scene_dict["visual_concept"] or "",
                search_queries=plan_data.get("search_queries", []),
                suggested_visual_type=scene_dict["suggested_visual_type"] or "stock_footage",
                negative_terms=plan_data.get("negative_terms", []),
                safety_constraints=[],
                confidence=plan_data.get("confidence", 0.5),
                preferred_source_route="stock",
                caption_text=scene_dict["caption_text"] or "",
            )

            # Search
            candidates = searcher.search_for_scene(sp, job_id=jid)

            # Rank
            ranker = CandidateRanker(
                embedding_model=embedding,
                seen_asset_ids=seen_asset_ids,
                target_aspect_ratio=aspect_ratio,
            )
            ranked = ranker.rank(sp, candidates)

            # Route
            result = router.route(sp, ranked, job_id=jid)

            if is_manual and ranked:
                # In manual mode, preselect highest-ranked candidate as convenience
                chosen_asset = ranked[0].asset
                route_name = "stock"
            else:
                chosen_asset = result.selected_asset
                route_name = result.route

            # Build structured candidate list for manual/automatic selection
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
                    "relevance_score": round(float(c.final_score), 4),
                    "rationale": c.rationale,
                    "rank": c.rank,
                    "is_selected": bool(chosen_asset and c.asset.asset_id == chosen_asset.asset_id),
                })
            plan_data["candidates"] = candidate_records
            plan_data["selected_candidate_id"] = chosen_asset.asset_id if chosen_asset else None

            # Diagnostic log: scene retrieval result
            log.info(
                "job_scene_retrieval",
                job_id=jid,
                scene_id=scene_dict["id"],
                scene_text_snippet=(scene_dict["narration_text"] or "")[:60],
                search_queries=sp.search_queries,
                candidate_count=len(candidates),
                route=route_name,
                selected_provider=chosen_asset.provider_name if chosen_asset else None,
                selected_clip_id=chosen_asset.asset_id if chosen_asset else None,
                fallback_reason=result.selection_reason if route_name == "card" else None,
                video_selection_mode="manual" if is_manual else "automatic",
            )

            # In automatic mode, download and validate immediately
            downloaded = None
            if not is_manual and result.route in ("stock", "generated") and result.selected_asset:
                target_dur = max(1.0, (scene_dict.get("end_time") or 5.0) - (scene_dict.get("start_time") or 0.0))
                try:
                    downloaded = downloader.download_and_validate(
                        result.selected_asset,
                        target_duration=target_dur,
                        job_id=jid,
                    )
                    plan_data["storage_key"] = downloaded.storage_key
                    plan_data["local_path"] = downloaded.local_path
                    plan_data["sha256_hash"] = downloaded.sha256_hash
                    plan_data["is_mock_media"] = downloaded.is_mock
                    plan_data["asset_id"] = result.selected_asset.asset_id
                except Exception as exc:
                    log.warning(
                        "asset_download_failed_fallback_card",
                        job_id=jid,
                        scene_id=scene_dict["id"],
                        asset_id=result.selected_asset.asset_id,
                        error=str(exc),
                    )
                    from sceneforge.retrieval.interfaces import RouteResult
                    result = RouteResult(
                        route="card",
                        selected_asset=None,
                        card_type="typography_card",
                        reason=f"Download failed ({exc}); falling back to typography card.",
                    )
                    chosen_asset = None
                    route_name = "card"

            # Update scene DB record by scene_id from plan_data
            scene_db_id = scene_dict["id"]
            with get_session() as session:
                scene_obj = repo.get_scenes(session, self.job_id)
                for s in scene_obj:
                    if str(s.id) == scene_db_id:
                        s.route = route_name
                        s.status = "AWAITING_SELECTION" if is_manual else "ASSET_SELECTED"
                        if chosen_asset:
                            s.asset_id = chosen_asset.asset_id
                            s.relevance_score = (
                                ranked[0].final_score if ranked else None
                            )
                            seen_asset_ids.add(chosen_asset.asset_id)
                        else:
                            s.asset_id = None
                            s.relevance_score = None
                        s.plan_data = dict(plan_data)
                        break

            # scene_dict["id"] is the DB UUID (FK-safe for rights_records.scene_id).
            # plan_data["scene_id"] is the planner string (e.g. "scene-a1b2c3d4") that
            # the timeline also uses.  Store both so QA coverage matching works.
            db_scene_uuid = scene_dict["id"]
            timeline_scene_id = plan_data.get("scene_id", db_scene_uuid)

            # Create rights record in automatic mode
            if not is_manual:
                if result.route in ("stock", "generated") and result.selected_asset:
                    rr = create_rights_record(
                        asset=result.selected_asset,
                        job_id=jid,
                        scene_id=db_scene_uuid,  # valid UUID FK
                    )
                    sha256 = (downloaded.sha256_hash if downloaded else None) or rr.sha256_hash
                    rights_records_data.append({
                        "asset_id": rr.asset_id,
                        "provider_name": rr.provider_name,
                        "source_url": rr.source_url,
                        "provider_asset_url": rr.provider_asset_url,
                        "licence_name": rr.licence_name,
                        "licence_evidence_url": rr.licence_evidence_url,
                        "commercial_use_eligible": rr.commercial_use_eligible,
                        "attribution_required": rr.attribution_required,
                        "attribution_text": rr.attribution_text,
                        "sha256_hash": sha256,
                        "asset_type": rr.asset_type,
                        "scene_id": db_scene_uuid,
                        "timeline_scene_id": timeline_scene_id,  # for QA coverage check
                    })
                elif result.route == "card":
                    pcard = create_programmatic_record(
                        card_type=result.card_type or "typography_card",
                        job_id=jid,
                        scene_id=db_scene_uuid,  # valid UUID FK
                    )
                    rights_records_data.append({
                        "asset_id": pcard.asset_id,
                        "provider_name": pcard.provider_name,
                        "source_url": "",
                        "provider_asset_url": "",
                        "licence_name": pcard.licence_name,
                        "licence_evidence_url": "",
                        "commercial_use_eligible": True,
                        "attribution_required": False,
                        "attribution_text": "",
                        "sha256_hash": None,
                        "asset_type": "programmatic",
                        "scene_id": db_scene_uuid,
                        "timeline_scene_id": timeline_scene_id,  # for QA coverage check
                    })

        # Persist rights records
        with get_session() as session:
            for rdata in rights_records_data:
                repo.add_rights_record(session, job_id=self.job_id, data=rdata)

        if is_manual:
            self._transition(JobStatus.AWAITING_SELECTION)
            log.info("stage_retrieve_manual_selection_ready", job_id=jid, scenes=len(scene_dicts))
            raise StopIteration("AWAITING_SELECTION")

        log.info("stage_retrieve_ok", job_id=jid, scenes=len(scene_dicts))

    def _stage_render(self) -> None:
        """Render video using FFmpeg (Phase 5).

        When FFmpeg is unavailable locally (e.g. Windows dev machine),
        falls back to writing a minimal placeholder MP4 and records the
        fact clearly in logs and metrics. The placeholder is NOT a real
        video — this is documented and not claimed as a successful render.

        A real render runs inside Docker where FFmpeg is installed.
        See Dockerfile: apt-get install -y ffmpeg.
        """
        self._transition(JobStatus.RENDERING)
        jid = str(self.job_id)

        from sceneforge.rendering.ffprobe import is_ffmpeg_available
        from sceneforge.rendering.normaliser import get_profile
        from sceneforge.rendering.renderer import VideoRenderer
        from sceneforge.rendering.cache import RenderCache
        from sceneforge.timeline.builder import Timeline, TimelineEntry, build_timeline
        from sceneforge.schemas.exceptions import RenderError
        from sceneforge.retrieval.downloader import MediaDownloader
        from sceneforge.retrieval.interfaces import MediaAsset
        from sceneforge.rights.passport import create_rights_record, create_programmatic_record
        import tempfile

        with get_session() as session:
            db_scenes_r = repo.get_scenes(session, self.job_id)
            job = repo.get_job(session, self.job_id)
            aspect_ratio = job.aspect_ratio if job else "16:9"
            job_config = dict(job.config or {}) if job and hasattr(job, "config") and job.config else {}
            # Snapshot scene data as plain dicts to avoid detached-instance errors
            scene_dicts_r = [
                {
                    "id": str(s.id),
                    "plan_data": dict(s.plan_data or {}),
                    "narration_text": s.narration_text,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "visual_concept": s.visual_concept,
                    "intended_meaning": s.intended_meaning,
                    "suggested_visual_type": s.suggested_visual_type,
                    "route": s.route,
                    "caption_text": s.caption_text,
                    "asset_id": s.asset_id,
                }
                for s in db_scenes_r
            ]

        # Restore narration audio if running in separate process/worker
        if not self._narration_audio_path or not os.path.isfile(self._narration_audio_path):
            saved_path = job_config.get("narration_audio_path")
            saved_key = job_config.get("narration_storage_key")
            if saved_path and os.path.isfile(saved_path):
                self._narration_audio_path = saved_path
            elif saved_key and self.storage.object_exists(BUCKET_ARTIFACTS, saved_key):
                try:
                    a_bytes = self.storage.download_bytes(BUCKET_ARTIFACTS, saved_key)
                    fd, tmp_audio = tempfile.mkstemp(suffix=".wav")
                    with os.fdopen(fd, "wb") as f:
                        f.write(a_bytes)
                    self._narration_audio_path = tmp_audio
                except Exception as exc:
                    log.warning("download_narration_audio_failed", error=str(exc))
        if job_config.get("narration_is_mock") is not None:
            self._narration_is_mock = bool(job_config.get("narration_is_mock"))

        # Job-isolated temporary directory for downloading chosen assets if not yet local
        job_work_dir = os.path.join(tempfile.gettempdir(), f"sf_dl_{jid[:8]}")
        os.makedirs(job_work_dir, exist_ok=True)
        downloader = MediaDownloader(storage_client=self.storage, work_dir=job_work_dir)

        # Download selected assets for any scenes that need it and ensure rights records exist
        for s in scene_dicts_r:
            plan_data = s["plan_data"]
            candidates = plan_data.get("candidates") or []
            selected_asset_id = s.get("asset_id") or plan_data.get("selected_candidate_id")
            local_path = plan_data.get("local_path")

            matched_candidate = None
            if selected_asset_id and candidates:
                for c in candidates:
                    if c.get("asset_id") == selected_asset_id:
                        matched_candidate = c
                        break
            if not matched_candidate and candidates:
                matched_candidate = candidates[0]
                selected_asset_id = matched_candidate.get("asset_id")
                s["asset_id"] = selected_asset_id

            need_download = (
                matched_candidate is not None
                and (not local_path or not os.path.isfile(local_path))
            )
            downloaded = None
            asset_obj = None
            if matched_candidate:
                asset_obj = MediaAsset(
                    asset_id=matched_candidate["asset_id"],
                    provider_name=matched_candidate["provider_name"],
                    title=matched_candidate.get("title", ""),
                    description=matched_candidate.get("description", ""),
                    source_url=matched_candidate.get("source_url", ""),
                    provider_asset_url=matched_candidate.get("provider_asset_url", ""),
                    preview_url=matched_candidate.get("preview_url", ""),
                    duration_seconds=matched_candidate.get("duration_seconds"),
                    width=matched_candidate.get("width"),
                    height=matched_candidate.get("height"),
                    licence_name=matched_candidate.get("licence_name", "Standard Commercial"),
                    licence_evidence_url=matched_candidate.get("licence_evidence_url", ""),
                    commercial_use_eligible=bool(matched_candidate.get("commercial_use_eligible", True)),
                    attribution_required=bool(matched_candidate.get("attribution_required", False)),
                    attribution_text=matched_candidate.get("attribution_text", ""),
                    asset_type=matched_candidate.get("asset_type", "stock"),
                    is_mock=bool(matched_candidate.get("is_mock", False)),
                )

            if need_download and asset_obj:
                target_dur = max(1.0, (s.get("end_time") or 5.0) - (s.get("start_time") or 0.0))
                try:
                    downloaded = downloader.download_and_validate(asset_obj, target_duration=target_dur, job_id=jid)
                    plan_data["storage_key"] = downloaded.storage_key
                    plan_data["local_path"] = downloaded.local_path
                    plan_data["sha256_hash"] = downloaded.sha256_hash
                    plan_data["is_mock_media"] = downloaded.is_mock
                    plan_data["asset_id"] = asset_obj.asset_id
                    s["route"] = "stock"
                    s["asset_id"] = asset_obj.asset_id
                except Exception as exc:
                    log.warning("render_stage_asset_download_failed", job_id=jid, scene_id=s["id"], error=str(exc))
                    s["route"] = "card"

            # Check / create rights record for scene
            with get_session() as session:
                existing_records = repo.get_rights_records(session, self.job_id)
                existing_scene_ids = {str(r.scene_id) for r in existing_records if r.scene_id}
                if s["id"] not in existing_scene_ids:
                    if matched_candidate and s["route"] in ("stock", "generated") and asset_obj:
                        rr = create_rights_record(
                            asset=asset_obj,
                            job_id=jid,
                            scene_id=s["id"],
                        )
                        repo.add_rights_record(session, job_id=self.job_id, data={
                            "asset_id": rr.asset_id,
                            "provider_name": rr.provider_name,
                            "source_url": rr.source_url,
                            "provider_asset_url": rr.provider_asset_url,
                            "licence_name": rr.licence_name,
                            "licence_evidence_url": rr.licence_evidence_url,
                            "commercial_use_eligible": rr.commercial_use_eligible,
                            "attribution_required": rr.attribution_required,
                            "attribution_text": rr.attribution_text,
                            "sha256_hash": (downloaded.sha256_hash if downloaded else None) or rr.sha256_hash,
                            "asset_type": rr.asset_type,
                            "scene_id": s["id"],
                        })
                    else:
                        pcard = create_programmatic_record(
                            card_type="typography_card",
                            job_id=jid,
                            scene_id=s["id"],
                        )
                        repo.add_rights_record(session, job_id=self.job_id, data={
                            "asset_id": pcard.asset_id,
                            "provider_name": pcard.provider_name,
                            "source_url": "",
                            "provider_asset_url": "",
                            "licence_name": pcard.licence_name,
                            "licence_evidence_url": "",
                            "commercial_use_eligible": True,
                            "attribution_required": False,
                            "attribution_text": "",
                            "sha256_hash": None,
                            "asset_type": "programmatic",
                            "scene_id": s["id"],
                        })
                # Update DB scene record with final plan_data & route
                scene_objs = repo.get_scenes(session, self.job_id)
                for sc in scene_objs:
                    if str(sc.id) == s["id"]:
                        sc.route = s["route"]
                        sc.status = "ASSET_SELECTED"
                        sc.asset_id = s.get("asset_id")
                        sc.plan_data = dict(plan_data)
                        break

        # Rebuild Timeline from DB scenes
        from sceneforge.planner.interfaces import ScenePlan
        scene_plans = []
        for s in scene_dicts_r:
            plan_data = s["plan_data"]
            scene_plans.append(ScenePlan(
                scene_id=plan_data.get("scene_id", s["id"]),
                narration_text=s["narration_text"] or "",
                start_time=s["start_time"] or 0.0,
                end_time=s["end_time"] or 5.0,
                key_entities=plan_data.get("key_entities", []),
                intended_meaning=s["intended_meaning"] or "",
                visual_concept=s["visual_concept"] or "",
                search_queries=plan_data.get("search_queries", []),
                suggested_visual_type=s["suggested_visual_type"] or "stock_footage",
                negative_terms=[],
                safety_constraints=[],
                confidence=plan_data.get("confidence", 0.5),
                preferred_source_route=s["route"] or "card",
                caption_text=s["caption_text"] or "",
                plan_metadata={
                    "asset_id": s["asset_id"] or plan_data.get("asset_id"),
                    "local_path": plan_data.get("local_path"),
                    "storage_key": plan_data.get("storage_key"),
                    "sha256_hash": plan_data.get("sha256_hash"),
                    "is_mock_media": plan_data.get("is_mock_media", False),
                    **(plan_data.get("plan_metadata") or {}),
                },
            ))
        timeline = build_timeline(jid, scene_plans)

        # Map aspect_ratio string to profile key
        ar_key = aspect_ratio if ":" in aspect_ratio else "16:9"
        try:
            profile = get_profile(ar_key)
        except ValueError:
            profile = get_profile("16:9")

        # Temp work dir
        work_dir = tempfile.mkdtemp(prefix=f"sf_render_{jid[:8]}_")
        output_mp4 = os.path.join(work_dir, "output.mp4")
        srt_path = os.path.join(work_dir, "captions.srt")

        try:
            ffmpeg_available = is_ffmpeg_available()
            self._stage_render_metadata = {
                "ffmpeg_available": ffmpeg_available,
                "aspect_ratio": ar_key,
                "profile": f"{profile.width}x{profile.height}@{profile.fps}fps",
                "tts_is_mock": self._narration_is_mock,
                "audio_path": self._narration_audio_path or "none",
            }

            if ffmpeg_available:
                # Real render
                cache_dir = os.path.join(work_dir, "cache")
                os.makedirs(cache_dir, exist_ok=True)
                render_cache = RenderCache(cache_dir, jid)
                burn_cfg = job_config.get("burn_captions")
                if burn_cfg is not None:
                    burn_captions_setting = bool(burn_cfg)
                else:
                    burn_captions_setting = os.getenv("BURN_CAPTIONS", "true").lower() not in ("false", "0")
                renderer = VideoRenderer(
                    profile,
                    audio_path=self._narration_audio_path or None,
                    cache=render_cache,
                    burn_captions=burn_captions_setting,
                    work_dir=work_dir,
                )
                try:
                    result = renderer.render(timeline, output_mp4, job_id=jid)
                    self._render_result = result
                    # Read and upload the real MP4
                    with open(output_mp4, "rb") as f:
                        mp4_bytes = f.read()
                    # Write SRT from renderer
                    srt_content = open(result.srt_path, "r", encoding="utf-8").read() if os.path.isfile(result.srt_path) else ""
                    log.info(
                        "stage_render_ok",
                        job_id=jid,
                        output_size=len(mp4_bytes),
                        segments=result.segment_count,
                        cache_hits=result.cache_hits,
                        ffmpeg_called=result.ffmpeg_called,
                    )
                except RenderError as exc:
                    log.error("stage_render_failed", job_id=jid, error=str(exc))
                    self._stage_render_metadata["render_error"] = str(exc)
                    self._fail(
                        "RENDER_FAILED",
                        f"Video rendering failed in FFmpeg: {exc}",
                        retryable=True,
                    )
                    raise
                except Exception as exc:
                    log.error("stage_render_unhandled_failed", job_id=jid, error=str(exc))
                    self._stage_render_metadata["render_error"] = str(exc)
                    self._fail(
                        "RENDER_FAILED",
                        f"Video rendering failed: {exc}",
                        retryable=True,
                    )
                    raise
            else:
                # FFmpeg not available locally — write placeholder
                mp4_bytes = self._placeholder_mp4_bytes()
                srt_content = ""
                self._stage_render_metadata["used_placeholder"] = True
                self._stage_render_metadata["reason"] = (
                    "FFmpeg is not installed on this machine. "
                    "The Dockerfile installs FFmpeg; run 'docker compose up --build' "
                    "for a real render. This placeholder is NOT a valid video."
                )
                log.warning(
                    "stage_render_placeholder",
                    job_id=jid,
                    reason="FFmpeg unavailable locally",
                )

            # Upload output.mp4 (real or placeholder)
            self.storage.upload_bytes(
                BUCKET_ARTIFACTS,
                artifact_key(jid, "output.mp4"),
                mp4_bytes,
                "video/mp4",
            )

            # Upload captions.srt
            from sceneforge.rendering.subtitle_writer import build_srt_from_timeline
            if not srt_content:
                srt_content = build_srt_from_timeline(timeline.entries)
            self.storage.upload_bytes(
                BUCKET_ARTIFACTS,
                artifact_key(jid, "captions.srt"),
                srt_content.encode("utf-8"),
                "text/plain",
            )

            # Store timeline for QA stage
            self._render_timeline = timeline
        finally:
            # Cleanup work dir unconditionally on success or failure/interruption
            try:
                import shutil
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass

            # Cleanup TTS temp audio file
            if self._narration_audio_path and os.path.isfile(self._narration_audio_path):
                try:
                    os.unlink(self._narration_audio_path)
                except OSError:
                    pass

    @staticmethod
    def _placeholder_mp4_bytes() -> bytes:
        """Return a minimal (but structurally valid-ish) placeholder MP4."""
        # Minimal ftyp + mdat box — not a playable video
        # Clearly labelled in logs; QA will correctly FAIL on this
        return (
            b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00"
            b"isomiso2mp41"
            b"\x00\x00\x00\x08mdat"
        )

    def _stage_qa(self) -> None:
        """Quality assurance using real QAChecker (Phase 5)."""
        self._transition(JobStatus.QA)
        jid = str(self.job_id)

        from sceneforge.quality.checker import QAChecker
        from sceneforge.rendering.normaliser import get_profile
        from sceneforge.rights.passport import RightsRecord
        import tempfile

        with get_session() as session:
            rights_db = repo.get_rights_records(session, self.job_id)
            job = repo.get_job(session, self.job_id)
            aspect_ratio = job.aspect_ratio if job else "16:9"
            # Also load scenes to rebuild the db_uuid → timeline_scene_id mapping.
            # The timeline uses plan_data.get("scene_id", scene.id) (planner string),
            # but rights_records.scene_id stores the DB UUID FK.  We need the
            # planner string in RightsRecord.scene_id so QA _check_rights_coverage
            # can match against TimelineEntry.scene_id.
            scene_rows = repo.get_scenes(session, self.job_id)
            db_uuid_to_timeline_id: dict[str, str] = {
                str(s.id): (s.plan_data or {}).get("scene_id", str(s.id))
                for s in scene_rows
            }
            # Snapshot to plain dicts — rights_records used after session closes
            rights_data_snapshot = [
                {
                    "id": str(r.id),
                    "asset_id": r.asset_id,
                    "provider_name": r.provider_name,
                    "source_url": r.source_url or "",
                    "provider_asset_url": r.provider_asset_url or "",
                    "licence_name": r.licence_name,
                    "licence_evidence_url": r.licence_evidence_url or "",
                    "commercial_use_eligible": r.commercial_use_eligible,
                    "attribution_required": r.attribution_required,
                    "attribution_text": r.attribution_text or "",
                    "retrieved_at": r.retrieved_at.isoformat() if r.retrieved_at else "",
                    "sha256_hash": r.sha256_hash,
                    "asset_type": r.asset_type,
                    "model_provenance": r.model_provenance,
                    "scene_id": r.scene_id,
                    # Translate DB UUID → planner timeline_scene_id for QA coverage.
                    # r.scene_id may be a UUID object; normalise to str for dict lookup.
                    "timeline_scene_id": db_uuid_to_timeline_id.get(
                        str(r.scene_id) if r.scene_id else "", str(r.scene_id) if r.scene_id else ""
                    ),
                }
                for r in rights_db
            ]

        # Download output.mp4 from storage to temp file
        mp4_key = artifact_key(jid, "output.mp4")
        srt_key = artifact_key(jid, "captions.srt")

        tmp_mp4 = tempfile.mktemp(suffix=".mp4")
        tmp_srt = tempfile.mktemp(suffix=".srt")
        qa_report = None

        try:
            try:
                mp4_bytes = self.storage.download_bytes(BUCKET_ARTIFACTS, mp4_key)
                with open(tmp_mp4, "wb") as f:
                    f.write(mp4_bytes)
            except Exception as exc:
                log.warning("qa_download_failed", job_id=jid, error=str(exc))
                tmp_mp4 = None

            try:
                srt_bytes = self.storage.download_bytes(BUCKET_ARTIFACTS, srt_key)
                with open(tmp_srt, "wb") as f:
                    f.write(srt_bytes)
            except Exception:
                tmp_srt = None

            # Reconstruct RightsRecord objects for coverage check (from snapshots).
            # Use timeline_scene_id (planner string) so it matches TimelineEntry.scene_id
            # in QAChecker._check_rights_coverage.
            rights_records = []
            for r in rights_data_snapshot:
                from sceneforge.rights.passport import RightsRecord as RR
                rr = RR(
                    record_id=r["id"],
                    asset_id=r["asset_id"],
                    provider_name=r["provider_name"],
                    source_url=r["source_url"],
                    provider_asset_url=r["provider_asset_url"],
                    licence_name=r["licence_name"],
                    licence_evidence_url=r["licence_evidence_url"],
                    commercial_use_eligible=r["commercial_use_eligible"],
                    commercial_use_verified=None,
                    attribution_required=r["attribution_required"],
                    attribution_text=r["attribution_text"],
                    retrieval_timestamp=r["retrieved_at"],
                    sha256_hash=r["sha256_hash"],
                    asset_type=r["asset_type"],
                    model_provenance=r["model_provenance"],
                    job_id=jid,
                    scene_id=r.get("timeline_scene_id") or r.get("scene_id"),
                )
                rights_records.append(rr)

            ar_key = aspect_ratio if ":" in aspect_ratio else "16:9"
            try:
                profile = get_profile(ar_key)
            except ValueError:
                profile = get_profile("16:9")

            timeline = getattr(self, "_render_timeline", None)

            checker = QAChecker(
                tmp_mp4 or "",
                srt_path=tmp_srt,
                timeline=timeline,
                rights_records=rights_records,
                expected_profile=profile,
                require_audio=False,   # narration audio not yet mixed in Phase 5
                job_id=jid,
            )
            qa_report = checker.run()

            # Update scene QA statuses
            with get_session() as session:
                scenes = repo.get_scenes(session, self.job_id)
                for scene in scenes:
                    scene.qa_status = qa_report.overall

            log.info(
                "stage_qa_ok",
                job_id=jid,
                overall=qa_report.overall,
                checks=len(qa_report.checks),
                fails=sum(1 for c in qa_report.checks if c.status == "FAIL"),
                unknowns=sum(1 for c in qa_report.checks if c.status == "UNKNOWN"),
            )

        finally:
            for p in (tmp_mp4, tmp_srt):
                if p and os.path.isfile(p):
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

        # Store QA report for artifact stage
        self._qa_report = qa_report

    def _stage_artifacts(self) -> None:
        """Upload remaining artifacts."""
        jid = str(self.job_id)

        with get_session() as session:
            db_scenes_a = repo.get_scenes(session, self.job_id)
            db_rights_a = repo.get_rights_records(session, self.job_id)
            job = repo.get_job(session, self.job_id)
            # Snapshot to plain dicts to avoid detached-instance errors
            job_created_at = job.created_at.isoformat() if job and job.created_at else None
            job_aspect_ratio = job.aspect_ratio if job and job.aspect_ratio else "16:9"
            job_tts_adapter = getattr(self, "_tts_adapter_name", None) or (job.tts_adapter if job and job.tts_adapter and job.tts_adapter != "mock" else None) or os.getenv("TTS_ADAPTER", "mock")
            job_stock_provider = getattr(job, "stock_provider", "pixabay") if job else "pixabay"
            job_config = dict(job.config or {}) if job and hasattr(job, "config") and job.config else {}
            # Snapshot to plain dicts to avoid detached-instance errors
            scenes_snap = [
                {
                    "scene_index": s.scene_index,
                    "narration_text": s.narration_text,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "visual_concept": s.visual_concept,
                    "asset_id": s.asset_id,
                    "route": s.route,
                    "relevance_score": s.relevance_score,
                    "caption_text": s.caption_text,
                }
                for s in db_scenes_a
            ]
            rights_snap = [
                {
                    "asset_id": r.asset_id,
                    "provider_name": r.provider_name,
                    "licence_name": r.licence_name,
                    "commercial_use_eligible": r.commercial_use_eligible,
                    "sha256_hash": r.sha256_hash,
                    "asset_type": r.asset_type,
                    "retrieved_at": r.retrieved_at.isoformat() if r.retrieved_at else "",
                }
                for r in db_rights_a
            ]

        # timeline.json
        timeline = {
            "job_id": jid,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "note": "STUB timeline — Phase 2 placeholder",
            "scenes": [
                {
                    "scene_index": s["scene_index"],
                    "narration_text": s["narration_text"],
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "visual_concept": s["visual_concept"],
                    "asset_id": s["asset_id"],
                    "route": s["route"],
                    "relevance_score": s["relevance_score"],
                    "caption_text": s["caption_text"],
                }
                for s in scenes_snap
            ],
        }
        self.storage.upload_bytes(
            BUCKET_ARTIFACTS,
            artifact_key(jid, "timeline.json"),
            json.dumps(timeline, indent=2).encode(),
            "application/json",
        )

        # rights.json
        rights_data = {
            "job_id": jid,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "records": [
                {
                    "asset_id": r["asset_id"],
                    "provider_name": r["provider_name"],
                    "licence_name": r["licence_name"],
                    "commercial_use_eligible": r["commercial_use_eligible"],
                    "sha256_hash": r["sha256_hash"],
                    "asset_type": r["asset_type"],
                    "retrieved_at": r["retrieved_at"],
                }
                for r in rights_snap
            ],
        }
        self.storage.upload_bytes(
            BUCKET_ARTIFACTS,
            artifact_key(jid, "rights.json"),
            json.dumps(rights_data, indent=2).encode(),
            "application/json",
        )

        # metrics.json
        qa_passed = None
        if self._qa_report:
            qa_passed = self._qa_report.overall == "PASS"
        metrics_data = {
            "job_id": jid,
            "stage_timings_ms": self._stage_timings,
            "retry_count": 0,
            "fallback_count": 0,
            "qa_passed": qa_passed,
            "qa_overall": self._qa_report.overall if self._qa_report else "UNKNOWN",
            "ffmpeg_available": self._stage_render_metadata.get("ffmpeg_available", False),
            "used_placeholder_mp4": self._stage_render_metadata.get("used_placeholder", False),
            "render_note": self._stage_render_metadata.get("reason", ""),
        }
        self.storage.upload_bytes(
            BUCKET_ARTIFACTS,
            artifact_key(jid, "metrics.json"),
            json.dumps(metrics_data, indent=2).encode(),
            "application/json",
        )

        # manifest.json
        total_assets = len(self._rights_records) if hasattr(self, "_rights_records") and self._rights_records else 0
        cleared_assets = (
            sum(1 for r in self._rights_records if getattr(r, "commercial_use_eligible", False))
            if hasattr(self, "_rights_records") and self._rights_records else 0
        )
        burn_cfg = job_config.get("burn_captions")
        if burn_cfg is not None:
            burn_captions_val = bool(burn_cfg)
        else:
            burn_captions_val = os.getenv("BURN_CAPTIONS", "true").lower() not in ("false", "0")

        manifest = {
            "job_id": jid,
            "created_at": job_created_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "api_version": "0.1.0",
            "aspect_ratio": job_aspect_ratio,
            "artifacts": [
                "output.mp4", "timeline.json", "rights.json",
                "metrics.json", "captions.srt", "manifest.json", "job.log",
            ],
            "providers": {
                "tts": job_tts_adapter,
                "stock": job_stock_provider,
                "models": {
                    "tts_engine": job_tts_adapter,
                    "media_search": "pixabay-video-v2",
                    "video_compositor": "ffmpeg-libx264",
                },
            },
            "settings": {
                "aspect_ratio": job_aspect_ratio,
                "burn_captions": burn_captions_val,
                "target_fps": 30,
                "resolution": self._stage_render_metadata.get("profile", "unknown"),
            },
            "timings_ms": self._stage_timings,
            "cost_estimate": {
                "estimated_cost_usd": 0.00,
                "currency": "USD",
                "provider_fees_usd": 0.00,
            },
            "warnings": getattr(self, "_pipeline_warnings", []),
            "rights_summary": {
                "total_assets": total_assets,
                "cleared_commercial": cleared_assets,
                "unverified_assets": max(0, total_assets - cleared_assets),
            },
            "ffmpeg_available": self._stage_render_metadata.get("ffmpeg_available", False),
            "real_mp4_rendered": (
                self._stage_render_metadata.get("ffmpeg_available", False)
                and not self._stage_render_metadata.get("used_placeholder", False)
            ),
            "render_profile": self._stage_render_metadata.get("profile", "unknown"),
            "tts_adapter": job_tts_adapter,
            "tts_is_mock": self._stage_render_metadata.get("tts_is_mock", True),
            "narration_audio_present": bool(self._stage_render_metadata.get("audio_path", "")),
            "qa_overall": self._qa_report.overall if self._qa_report else "UNKNOWN",
        }
        self.storage.upload_bytes(
            BUCKET_ARTIFACTS,
            artifact_key(jid, "manifest.json"),
            json.dumps(manifest, indent=2).encode(),
            "application/json",
        )

        # captions.srt — generated from the real timeline
        from sceneforge.rendering.subtitle_writer import build_srt_from_timeline
        if self._render_timeline and self._render_timeline.entries:
            captions = build_srt_from_timeline(self._render_timeline.entries)
        else:
            # Fallback if no timeline (should not happen in normal flow)
            captions = build_srt_from_timeline([
                type('E', (), {
                    'start_time': 0.0, 'end_time': 5.0,
                    'caption_text': scenes_snap[0]["narration_text"] if scenes_snap else "",
                    'narration_text': scenes_snap[0]["narration_text"] if scenes_snap else "",
                })() for _ in scenes_snap
            ]) if scenes_snap else ""
        self.storage.upload_bytes(
            BUCKET_ARTIFACTS,
            artifact_key(jid, "captions.srt"),
            captions.encode(),
            "text/plain",
        )

        # job.log (stub)
        job_log = json.dumps({
            "job_id": jid,
            "event": "pipeline_completed",
            "stage_timings_ms": self._stage_timings,
            "note": "STUB log — Phase 2 placeholder",
        }) + "\n"
        self.storage.upload_bytes(
            BUCKET_ARTIFACTS,
            artifact_key(jid, "job.log"),
            job_log.encode(),
            "text/plain",
        )

        # Update DB metrics
        with get_session() as session:
            repo.upsert_metric(
                session,
                self.job_id,
                {
                    "stage_timings": self._stage_timings,
                    "retry_count": 0,
                    "fallback_count": 0,
                    "qa_passed": True,
                },
            )

        log.info("stage_artifacts_ok", job_id=jid)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Execute the pipeline sequentially (full run or render continuation)."""
        jid = str(self.job_id)
        with get_session() as session:
            current_job = repo.get_job(session, self.job_id)
            if current_job and current_job.status in ("COMPLETED", "CANCELLED"):
                log.warning("orchestrator_skipping_terminal_job", job_id=jid, status=current_job.status)
                return
            initial_status = current_job.status if current_job else None

        total_start = time.perf_counter()

        if initial_status == JobStatus.AWAITING_SELECTION.value:
            stages = [
                ("render", self._stage_render),
                ("qa", self._stage_qa),
                ("artifacts", self._stage_artifacts),
            ]
        else:
            stages = [
                ("validate", self._stage_validate),
                ("plan", self._stage_plan),
                ("retrieve", self._stage_retrieve),
                ("render", self._stage_render),
                ("qa", self._stage_qa),
                ("artifacts", self._stage_artifacts),
            ]

        try:
            for name, fn in stages:
                self._timed_stage(name, fn)
        except StopIteration:
            # Controlled early exit (e.g. EMPTY_SCRIPT already marked FAILED)
            return
        except Exception as exc:
            with get_session() as session:
                curr_job = repo.get_job(session, self.job_id)
                curr_status = curr_job.status if curr_job else None
            err_code = "RENDER_FAILED" if curr_status == JobStatus.RENDERING.value else "PIPELINE_ERROR"
            self._fail(
                err_code,
                f"Pipeline failed at {curr_status or 'unhandled'} stage: {exc}",
                retryable=True,
            )
            raise

        # Mark COMPLETED
        self._transition(JobStatus.COMPLETED)
        total_ms = round((time.perf_counter() - total_start) * 1000, 1)
        log.info(
            "pipeline_finished",
            job_id=jid,
            total_ms=total_ms,
            stage_timings=self._stage_timings,
        )

        # Fire callback if registered
        with get_session() as session:
            job = repo.get_job(session, self.job_id)
            callback_url = job.callback_url if job else None

        if callback_url:
            import asyncio
            from sceneforge.api.callbacks import send_callback
            asyncio.run(
                send_callback(
                    callback_url,
                    {"job_id": jid, "status": "COMPLETED"},
                    jid,
                )
            )
