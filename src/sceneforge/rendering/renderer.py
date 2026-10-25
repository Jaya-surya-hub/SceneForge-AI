"""FFmpeg-based video renderer.

Accepts a Timeline and renders a single output MP4 by:
  1. Generating or preparing each scene's video segment (card or clip).
  2. Concatenating all segments using FFmpeg concat demuxer.
  3. Muxing the narration audio track.
  4. Writing captions.srt and optionally burning captions into the video.

All subprocess calls use argument arrays (never shell=True), have explicit
timeouts, and clean up temporary files unconditionally.

If FFmpeg is unavailable, RenderError is raised immediately with a clear
message — no partial output is written, and no success is claimed.

Architecture note:
  - Renderer is stateless; create a new instance per job.
  - RenderCache is optional; pass cache=None to disable.
  - The renderer does not fetch media — assets are already on disk or
    handled as cards. Phase 5 uses placeholder bytes for mock assets
    (since we have no real download yet); real downloads come in Phase 6.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Optional

from sceneforge.observability.logging import get_logger
from sceneforge.rendering.cache import CacheKey, RenderCache, build_cache_key
from sceneforge.rendering.card_generator import generate_card
from sceneforge.rendering.normaliser import OutputProfile, build_audio_filter, build_video_filter
from sceneforge.rendering.reframer import compute_reframe, needs_reframe
from sceneforge.rendering.subtitle_writer import build_srt_from_timeline, validate_srt
from sceneforge.schemas.exceptions import RenderError
from sceneforge.timeline.builder import Timeline, TimelineEntry

log = get_logger(__name__)

_FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
_FFMPEG_TIMEOUT = int(os.getenv("FFMPEG_TIMEOUT", "300"))
_SEGMENT_TIMEOUT = int(os.getenv("FFMPEG_SEGMENT_TIMEOUT", "120"))
_FFMPEG_THREADS = os.getenv("FFMPEG_THREADS", "1")


@dataclass
class RenderResult:
    """Output of a successful render."""
    output_path: str
    srt_path: str
    duration_seconds: float
    segment_count: int
    cache_hits: int
    cache_misses: int
    warnings: list[str] = field(default_factory=list)
    # True = FFmpeg was actually called; False = all segments came from cache
    ffmpeg_called: bool = True


class VideoRenderer:
    """Render a Timeline to an MP4 file.

    Args:
        profile:       OutputProfile specifying codec, dimensions, fps.
        audio_path:    Path to the narration audio file (WAV/MP3).
                       None = render silent video.
        cache:         Optional RenderCache for incremental rendering.
        burn_captions: If True, burn captions into the video with drawtext.
        work_dir:      Temporary working directory. Created if not supplied.
    """

    def __init__(
        self,
        profile: OutputProfile,
        *,
        audio_path: Optional[str] = None,
        cache: Optional[RenderCache] = None,
        burn_captions: bool = True,
        work_dir: Optional[str] = None,
    ) -> None:
        self._profile = profile
        self._audio_path = audio_path
        self._cache = cache
        self._burn_captions = burn_captions
        self._work_dir = work_dir
        self._owns_work_dir = work_dir is None

    def render(
        self,
        timeline: Timeline,
        output_path: str,
        *,
        job_id: str = "unknown",
    ) -> RenderResult:
        """Render *timeline* to *output_path*.

        Args:
            timeline:    Validated timeline from Phase 3.
            output_path: Where to write the final MP4.
            job_id:      For logging and cache namespacing.

        Returns:
            RenderResult with paths and statistics.

        Raises:
            RenderError: On any FFmpeg failure or configuration error.
        """
        if not timeline.entries:
            raise RenderError("Cannot render an empty timeline.")

        work_dir = self._work_dir or tempfile.mkdtemp(prefix="sf_render_")
        try:
            return self._render_inner(timeline, output_path, job_id, work_dir)
        finally:
            if self._owns_work_dir:
                shutil.rmtree(work_dir, ignore_errors=True)

    def _render_inner(
        self,
        timeline: Timeline,
        output_path: str,
        job_id: str,
        work_dir: str,
    ) -> RenderResult:
        warnings: list[str] = []
        cache_hits = 0
        cache_misses = 0
        segment_paths: list[str] = []
        aspect_ratio = f"{self._profile.width}:{self._profile.height}"

        # ── Step 1: Generate / retrieve each scene segment ─────────────────
        for i, entry in enumerate(timeline.entries):
            seg_path, hit = self._get_segment(
                entry, i, work_dir, job_id, aspect_ratio
            )
            if hit:
                cache_hits += 1
            else:
                cache_misses += 1
            segment_paths.append(seg_path)
            if not os.path.isfile(seg_path):
                warnings.append(f"Scene {i}: segment not produced — skipped.")

        valid_segments = [p for p in segment_paths if os.path.isfile(p)]
        if not valid_segments:
            raise RenderError(
                "All scene segments failed to render. Cannot produce output."
            )

        # ── Step 2: Write concat list ───────────────────────────────────────
        concat_list = os.path.join(work_dir, "concat.txt")
        with open(concat_list, "w") as f:
            for path in valid_segments:
                # FFmpeg concat uses forward slashes even on Windows
                safe = path.replace("\\", "/")
                f.write(f"file '{safe}'\n")

        # ── Step 3: Concatenate segments ────────────────────────────────────
        concat_tmp = os.path.join(work_dir, "concat_out.mp4")
        self._ffmpeg_concat(concat_list, concat_tmp)

        # ── Step 4: Mix narration audio ─────────────────────────────────────
        mixed_tmp = os.path.join(work_dir, "mixed.mp4")
        self._ffmpeg_mix_audio(concat_tmp, mixed_tmp)

        # ── Step 5: Write SRT ───────────────────────────────────────────────
        srt_content = build_srt_from_timeline(timeline.entries)
        srt_tmp = os.path.join(work_dir, "captions.srt")
        with open(srt_tmp, "w", encoding="utf-8") as f:
            f.write(srt_content)
        srt_errors = validate_srt(srt_content)
        for err in srt_errors:
            warnings.append(f"SRT validation: {err}")

        # ── Step 6: Burn captions ──────────────────────────────────────────
        if self._burn_captions and srt_content:
            burned_tmp = os.path.join(work_dir, "burned.mp4")
            try:
                self._ffmpeg_burn_captions(mixed_tmp, srt_tmp, burned_tmp)
                if os.path.isfile(burned_tmp) and os.path.getsize(burned_tmp) > 0:
                    final_video = burned_tmp
                else:
                    final_video = mixed_tmp
            except Exception as exc:
                log.warning("burn_captions_failed_fallback_to_mixed", error=str(exc))
                warnings.append(f"Caption burning warning: {exc}")
                final_video = mixed_tmp
        else:
            final_video = mixed_tmp

        # ── Step 7: Copy to final output path ──────────────────────────────
        shutil.copy2(final_video, output_path)
        log.info(
            "render_complete",
            job_id=job_id,
            output=output_path,
            segments=len(valid_segments),
            cache_hits=cache_hits,
        )

        # Estimate duration from timeline
        duration = timeline.total_duration

        return RenderResult(
            output_path=output_path,
            srt_path=srt_tmp,
            duration_seconds=duration,
            segment_count=len(valid_segments),
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            warnings=warnings,
            ffmpeg_called=True,
        )

    # ------------------------------------------------------------------
    # Segment preparation
    # ------------------------------------------------------------------

    def _get_segment(
        self,
        entry: TimelineEntry,
        index: int,
        work_dir: str,
        job_id: str,
        aspect_ratio: str,
    ) -> tuple[str, bool]:
        """Return (segment_path, cache_hit)."""
        seg_out = os.path.join(work_dir, f"seg_{index:04d}.mp4")

        # Check whether this entry has downloaded video footage available
        has_media = bool(
            entry.plan_metadata.get("local_path")
            or entry.plan_metadata.get("storage_key")
        )
        is_card = (
            entry.route == "card"
            or entry.suggested_visual_type in ("typography_card", "data_card")
        ) and not has_media

        if is_card:
            card_type = (
                entry.suggested_visual_type
                if entry.suggested_visual_type in ("typography_card", "data_card")
                else "typography_card"
            )
            try:
                generate_card(
                    card_type=card_type,
                    text=entry.caption_text or entry.narration_text or entry.visual_concept or "Scene",
                    duration_seconds=entry.duration or 5.0,
                    width=self._profile.width,
                    height=self._profile.height,
                    output_path=seg_out,
                )
            except RuntimeError as exc:
                log.warning("card_generation_failed", scene=entry.scene_id, error=str(exc))
                # Fallback: create a placeholder (black frame) for this scene
                self._create_black_segment(seg_out, entry.duration or 5.0)
            return seg_out, False

        # For stock/generated assets check cache
        cache_key = build_cache_key(
            asset_id=entry.asset_id or entry.scene_id,
            trim_start=entry.start_time,
            trim_end=entry.end_time,
            aspect_ratio=aspect_ratio,
            caption_text=entry.caption_text or "",
            profile=self._profile,
        )
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                shutil.copy2(cached, seg_out)
                return seg_out, True

        # Render from source video (or fallback)
        self._render_scene_segment(entry, seg_out)

        if self._cache:
            self._cache.put(cache_key, seg_out)

        return seg_out, False

    def _render_scene_segment(self, entry: TimelineEntry, output_path: str) -> None:
        """Render a single scene segment from source video or fallback card."""
        local_path = entry.plan_metadata.get("local_path")
        storage_key = entry.plan_metadata.get("storage_key")

        # If local_path is missing or not on disk, attempt retrieval from object storage
        if not (local_path and os.path.isfile(local_path)) and storage_key:
            try:
                from sceneforge.storage.client import get_storage_client
                from sceneforge.storage.paths import BUCKET_UPLOADS
                storage = get_storage_client()
                if storage.object_exists(BUCKET_UPLOADS, storage_key):
                    raw_bytes = storage.download_bytes(BUCKET_UPLOADS, storage_key)
                    cached_src = os.path.join(
                        self._work_dir or tempfile.gettempdir(),
                        f"src_{entry.scene_id}.mp4",
                    )
                    with open(cached_src, "wb") as f:
                        f.write(raw_bytes)
                    local_path = cached_src
            except Exception as exc:
                log.warning("storage_download_segment_failed", key=storage_key, error=str(exc))
                local_path = None

        if local_path and os.path.isfile(local_path):
            log.info(
                "render_segment_video",
                scene_id=entry.scene_id,
                asset_id=entry.asset_id,
                local_path=local_path,
                duration=entry.duration,
            )
            duration = max(1.0, float(entry.duration or 5.0))
            duration_str = str(duration)
            vf = build_video_filter(self._profile)
            args = [
                _FFMPEG_BIN,
                "-y",
                "-threads", _FFMPEG_THREADS,
                "-stream_loop", "-1",
                "-i", local_path,
                "-f", "lavfi",
                "-t", duration_str,
                "-i", "anullsrc=r=44100:cl=stereo",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-t", duration_str,
                "-vf", vf,
                "-c:v", self._profile.video_codec,
                "-preset", self._profile.preset,
                "-crf", str(self._profile.crf),
                "-c:a", "aac",
                "-b:a", self._profile.audio_bitrate,
                "-pix_fmt", self._profile.pix_fmt,
                "-shortest",
                output_path,
            ]
            try:
                self._run_ffmpeg(args, _SEGMENT_TIMEOUT, context=f"render_video_{entry.scene_id}")
                return
            except Exception as exc:
                log.warning(
                    "render_segment_video_failed_fallback_card",
                    scene_id=entry.scene_id,
                    error=str(exc),
                )

        # Fallback to typography card if no video or FFmpeg video render failed
        try:
            generate_card(
                card_type="typography_card",
                text=entry.visual_concept or entry.narration_text or "Scene",
                duration_seconds=entry.duration or 5.0,
                width=self._profile.width,
                height=self._profile.height,
                output_path=output_path,
            )
        except RuntimeError:
            self._create_black_segment(output_path, entry.duration or 5.0)

    def _create_black_segment(self, output_path: str, duration: float) -> None:
        """Create a black silent segment as a last-resort fallback."""
        args = [
            _FFMPEG_BIN, "-y",
            "-threads", _FFMPEG_THREADS,
            "-f", "lavfi", "-i", f"color=c=black:s={self._profile.width}x{self._profile.height}:r={self._profile.fps}",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration),
            "-c:v", "libx264", "-preset", self._profile.preset, "-crf", "28",
            "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p", "-shortest",
            output_path,
        ]
        self._run_ffmpeg(args, _SEGMENT_TIMEOUT, context="black_fallback")

    # ------------------------------------------------------------------
    # FFmpeg assembly steps
    # ------------------------------------------------------------------

    def _ffmpeg_concat(self, concat_list: str, output: str) -> None:
        """Concatenate segments using the concat demuxer.
        
        Attempts fast stream copy first since all segments are normalised
        to the identical codec, resolution, and fps. Falls back to re-encode
        if demux copy fails.
        """
        copy_args = [
            _FFMPEG_BIN, "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list,
            "-c:v", "copy",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output,
        ]
        try:
            self._run_ffmpeg(copy_args, _FFMPEG_TIMEOUT, context="concat_copy")
            return
        except RenderError as copy_err:
            log.warning("concat_stream_copy_failed_falling_back_to_encode", error=str(copy_err))

        reencode_args = [
            _FFMPEG_BIN, "-y",
            "-threads", _FFMPEG_THREADS,
            "-f", "concat", "-safe", "0",
            "-i", concat_list,
            "-c:v", self._profile.video_codec,
            "-preset", self._profile.preset,
            "-crf", str(self._profile.crf),
            "-c:a", "copy",
            "-pix_fmt", self._profile.pix_fmt,
            "-movflags", "+faststart",
            output,
        ]
        self._run_ffmpeg(reencode_args, _FFMPEG_TIMEOUT, context="concat_reencode")

    def _ffmpeg_mix_audio(self, video_path: str, output: str) -> None:
        """Mix narration audio into the video, or copy if no audio provided."""
        if not self._audio_path or not os.path.isfile(self._audio_path):
            shutil.copy2(video_path, output)
            return

        af = build_audio_filter(normalise_loudness=True)
        args = [
            _FFMPEG_BIN, "-y",
            "-i", video_path,
            "-i", self._audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", self._profile.audio_codec,
            "-b:a", self._profile.audio_bitrate,
            "-af", f"{af},apad",
            "-shortest",
            "-movflags", "+faststart",
            output,
        ]
        try:
            self._run_ffmpeg(args, _FFMPEG_TIMEOUT, context="mix_audio")
        except RenderError as exc:
            log.warning("mix_audio_loudnorm_failed_retrying_simple", error=str(exc))
            simple_af = f"aresample={self._profile.audio_sample_rate},apad"
            args_simple = [
                _FFMPEG_BIN, "-y",
                "-i", video_path,
                "-i", self._audio_path,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", self._profile.audio_codec,
                "-b:a", self._profile.audio_bitrate,
                "-af", simple_af,
                "-shortest",
                "-movflags", "+faststart",
                output,
            ]
            self._run_ffmpeg(args_simple, _FFMPEG_TIMEOUT, context="mix_audio_simple")

    def _ffmpeg_burn_captions(
        self, video_path: str, srt_path: str, output: str
    ) -> None:
        """Burn SRT captions directly into the video with bold, high-contrast styling."""
        safe_srt = srt_path.replace("\\", "/").replace(":", "\\:")
        is_vertical = self._profile.width < self._profile.height
        font_size = 34 if is_vertical else 30
        margin_v = 130 if is_vertical else 65
        style = (
            f"FontName=DejaVu Sans,FontSize={font_size},Bold=1,"
            f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            f"BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV={margin_v}"
        )
        vf = f"subtitles='{safe_srt}':force_style='{style}'"
        args = [
            _FFMPEG_BIN, "-y",
            "-threads", _FFMPEG_THREADS,
            "-i", video_path,
            "-vf", vf,
            "-c:v", self._profile.video_codec,
            "-preset", self._profile.preset,
            "-crf", str(self._profile.crf),
            "-c:a", "copy",
            "-pix_fmt", self._profile.pix_fmt,
            "-movflags", "+faststart",
            output,
        ]
        try:
            self._run_ffmpeg(args, _FFMPEG_TIMEOUT, context="burn_captions")
        except RenderError as exc:
            log.warning("burn_captions_styled_failed_trying_simple", error=str(exc))
            simple_vf = f"subtitles='{safe_srt}'"
            simple_args = [
                _FFMPEG_BIN, "-y",
                "-threads", _FFMPEG_THREADS,
                "-i", video_path,
                "-vf", simple_vf,
                "-c:v", self._profile.video_codec,
                "-preset", self._profile.preset,
                "-crf", str(self._profile.crf),
                "-c:a", "copy",
                "-pix_fmt", self._profile.pix_fmt,
                "-movflags", "+faststart",
                output,
            ]
            self._run_ffmpeg(simple_args, _FFMPEG_TIMEOUT, context="burn_captions_simple")

    def _run_ffmpeg(self, args: list[str], timeout: int, context: str) -> None:
        """Run an FFmpeg command; raise RenderError on failure."""
        log.debug("ffmpeg_cmd", context=context, args=args[:6])
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            raise RenderError(
                f"ffmpeg not found at '{_FFMPEG_BIN}'. "
                "FFmpeg must be installed for rendering. "
                "In Docker: use the provided Dockerfile which installs FFmpeg."
            )
        except subprocess.TimeoutExpired as exc:
            stderr_output = getattr(exc, "stderr", None) or ""
            if isinstance(stderr_output, bytes):
                stderr_output = stderr_output.decode(errors="replace")
            stderr_snippet = stderr_output[-600:]
            raise RenderError(
                f"FFmpeg timed out after {timeout}s during '{context}'. {stderr_snippet}".strip()
            )
        if result.returncode != 0:
            raise RenderError(
                f"FFmpeg failed during '{context}' (exit {result.returncode}): "
                f"{result.stderr[-600:]}"
            )
        log.debug("ffmpeg_ok", context=context)
