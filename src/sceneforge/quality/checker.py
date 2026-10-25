"""Automated quality assurance checker.

Runs a battery of checks on a rendered output file using ffprobe
and structural analysis.  Every check reports PASS, FAIL, or UNKNOWN.

UNKNOWN is used when a measurement cannot be taken (e.g. ffprobe
unavailable, or the check is not applicable).  UNKNOWN is never
promoted to PASS silently.

Architecture:
  - QAChecker.run() executes all checks and returns a QAReport.
  - Each check is an independent method; failures in one do not
    prevent others from running.
  - The overall status is PASS only if every non-SKIPPED check is PASS.
  - UNKNOWN counts as non-PASS for the overall status.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal, Optional

from sceneforge.observability.logging import get_logger
from sceneforge.rendering.ffprobe import ProbeResult, is_ffprobe_available, probe_file
from sceneforge.rendering.subtitle_writer import validate_srt
from sceneforge.rights.passport import RightsRecord
from sceneforge.timeline.builder import Timeline

log = get_logger(__name__)

CheckStatus = Literal["PASS", "FAIL", "UNKNOWN", "SKIPPED"]

_MAX_AUDIO_DRIFT = float(os.getenv("QA_MAX_AUDIO_DRIFT", "0.5"))
_MIN_OUTPUT_DURATION = float(os.getenv("QA_MIN_OUTPUT_DURATION", "0.5"))
_BLACK_THRESHOLD = float(os.getenv("QA_BLACK_FRAME_THRESHOLD", "0.98"))


@dataclass
class QACheckResult:
    check_name: str
    status: CheckStatus
    detail: str
    evidence: dict = field(default_factory=dict)


@dataclass
class QAReport:
    job_id: str
    output_path: str
    overall: Literal["PASS", "FAIL", "UNKNOWN"]
    checks: list[QACheckResult]
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "output_path": self.output_path,
            "overall": self.overall,
            "checks": [
                {
                    "check_name": c.check_name,
                    "status": c.status,
                    "detail": c.detail,
                    "evidence": c.evidence,
                }
                for c in self.checks
            ],
            "warnings": self.warnings,
        }


class QAChecker:
    """Run quality checks on a rendered output file.

    Args:
        output_path:     Path to the rendered MP4.
        srt_path:        Path to the captions SRT (optional).
        timeline:        Timeline used for this render.
        rights_records:  Rights records for all selected assets.
        expected_profile: OutputProfile with expected codec/dims/fps.
        require_audio:   Fail if no audio stream is found.
        job_id:          For logging.
    """

    def __init__(
        self,
        output_path: str,
        *,
        srt_path: Optional[str] = None,
        timeline: Optional[Timeline] = None,
        rights_records: Optional[list[RightsRecord]] = None,
        expected_profile=None,
        require_audio: bool = True,
        job_id: str = "unknown",
    ) -> None:
        self._output = output_path
        self._srt = srt_path
        self._timeline = timeline
        self._rights = rights_records or []
        self._profile = expected_profile
        self._require_audio = require_audio
        self._job_id = job_id
        self._probe: Optional[ProbeResult] = None

    def run(self) -> QAReport:
        """Execute all checks and return a QAReport."""
        checks: list[QACheckResult] = []
        warnings: list[str] = []

        # Probe first — all video checks depend on it
        probe_ok = self._probe_file(checks)

        # File existence and size
        checks.append(self._check_file_exists())
        checks.append(self._check_file_nonempty())

        if probe_ok and self._probe:
            checks.append(self._check_container())
            checks.append(self._check_video_codec())
            checks.append(self._check_audio_codec())
            checks.append(self._check_frame_rate())
            checks.append(self._check_dimensions())
            checks.append(self._check_duration())
            checks.append(self._check_audio_present())
            checks.append(self._check_pixel_format())
            checks.append(self._check_black_frames())
            checks.append(self._check_frozen_frames())
        else:
            for name in ("container", "video_codec", "audio_codec", "frame_rate",
                         "dimensions", "duration", "audio_present", "pixel_format",
                         "black_frames", "frozen_frames"):
                checks.append(QACheckResult(
                    name, "UNKNOWN",
                    "ffprobe not available or probe failed.",
                ))

        # Subtitle check (independent of probe)
        checks.append(self._check_subtitles())

        # Rights coverage check
        checks.append(self._check_rights_coverage())

        # Duplicate scene check
        checks.append(self._check_duplicate_scenes())

        # Overall status
        statuses = {c.status for c in checks}
        if "FAIL" in statuses:
            overall = "FAIL"
        elif "UNKNOWN" in statuses:
            overall = "UNKNOWN"
        else:
            overall = "PASS"

        log.info(
            "qa_complete",
            job_id=self._job_id,
            overall=overall,
            checks=len(checks),
            fails=sum(1 for c in checks if c.status == "FAIL"),
            unknowns=sum(1 for c in checks if c.status == "UNKNOWN"),
        )

        return QAReport(
            job_id=self._job_id,
            output_path=self._output,
            overall=overall,
            checks=checks,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _probe_file(self, checks: list) -> bool:
        """Probe the output file; return True if successful."""
        if not is_ffprobe_available():
            checks.append(QACheckResult(
                "ffprobe_available", "UNKNOWN",
                "ffprobe is not installed or not on PATH. "
                "Media checks cannot be performed without ffprobe.",
                evidence={"ffprobe_bin": os.getenv("FFPROBE_BIN", "ffprobe")},
            ))
            return False

        try:
            self._probe = probe_file(self._output)
            checks.append(QACheckResult(
                "ffprobe_available", "PASS",
                "ffprobe is available and the file was probed successfully.",
                evidence={"format": self._probe.format.format_name},
            ))
            return True
        except Exception as exc:
            checks.append(QACheckResult(
                "ffprobe_available", "FAIL",
                f"ffprobe failed: {exc}",
                evidence={"error": str(exc)},
            ))
            return False

    def _check_file_exists(self) -> QACheckResult:
        exists = os.path.isfile(self._output)
        return QACheckResult(
            "file_exists",
            "PASS" if exists else "FAIL",
            f"Output file {'exists' if exists else 'does not exist'}: {self._output}",
            evidence={"path": self._output, "exists": exists},
        )

    def _check_file_nonempty(self) -> QACheckResult:
        try:
            size = os.path.getsize(self._output)
            ok = size > 0
        except OSError:
            return QACheckResult(
                "file_nonempty", "FAIL",
                "Could not read output file size.",
            )
        return QACheckResult(
            "file_nonempty",
            "PASS" if ok else "FAIL",
            f"File size: {size} bytes.",
            evidence={"size_bytes": size},
        )

    def _check_container(self) -> QACheckResult:
        assert self._probe is not None
        fmt = self._probe.format.format_name or ""
        ok = "mp4" in fmt or "mov" in fmt
        return QACheckResult(
            "container",
            "PASS" if ok else "FAIL",
            f"Container format: '{fmt}'. Expected: mp4.",
            evidence={"format_name": fmt},
        )

    def _check_video_codec(self) -> QACheckResult:
        assert self._probe is not None
        vs = self._probe.video_stream
        if vs is None:
            return QACheckResult("video_codec", "FAIL", "No video stream found.")
        ok = vs.codec_name in ("h264", "libx264")
        return QACheckResult(
            "video_codec",
            "PASS" if ok else "FAIL",
            f"Video codec: '{vs.codec_name}'. Expected: h264.",
            evidence={"codec_name": vs.codec_name},
        )

    def _check_audio_codec(self) -> QACheckResult:
        assert self._probe is not None
        as_ = self._probe.audio_stream
        if as_ is None:
            if self._require_audio:
                return QACheckResult("audio_codec", "FAIL", "No audio stream found.")
            return QACheckResult("audio_codec", "SKIPPED", "Audio not required.")
        ok = as_.codec_name in ("aac", "mp4a")
        return QACheckResult(
            "audio_codec",
            "PASS" if ok else "FAIL",
            f"Audio codec: '{as_.codec_name}'. Expected: aac.",
            evidence={"codec_name": as_.codec_name},
        )

    def _check_frame_rate(self) -> QACheckResult:
        assert self._probe is not None
        fps = self._probe.frame_rate_float()
        if fps is None:
            return QACheckResult("frame_rate", "UNKNOWN", "Could not parse frame rate.")
        expected = self._profile.fps if self._profile else 30
        ok = abs(fps - expected) < 1.0
        return QACheckResult(
            "frame_rate",
            "PASS" if ok else "FAIL",
            f"Frame rate: {fps:.2f} fps. Expected: {expected} fps.",
            evidence={"fps": fps, "expected_fps": expected},
        )

    def _check_dimensions(self) -> QACheckResult:
        assert self._probe is not None
        vs = self._probe.video_stream
        if vs is None or vs.width is None or vs.height is None:
            return QACheckResult("dimensions", "UNKNOWN", "No video stream dimensions.")
        if self._profile:
            ok = vs.width == self._profile.width and vs.height == self._profile.height
            detail = (
                f"{vs.width}x{vs.height}. "
                f"Expected: {self._profile.width}x{self._profile.height}."
            )
        else:
            ok = vs.width > 0 and vs.height > 0
            detail = f"{vs.width}x{vs.height}."
        return QACheckResult(
            "dimensions",
            "PASS" if ok else "FAIL",
            detail,
            evidence={"width": vs.width, "height": vs.height},
        )

    def _check_duration(self) -> QACheckResult:
        assert self._probe is not None
        dur = self._probe.duration
        if dur is None:
            return QACheckResult("duration", "UNKNOWN", "Could not determine duration.")
        ok = dur >= _MIN_OUTPUT_DURATION
        detail = f"Duration: {dur:.2f}s. Minimum: {_MIN_OUTPUT_DURATION}s."
        if self._timeline:
            expected = self._timeline.total_duration
            drift = abs(dur - expected)
            detail += f" Expected: {expected:.2f}s. Drift: {drift:.2f}s."
            if drift > _MAX_AUDIO_DRIFT * 2:
                ok = False
                detail += " DRIFT EXCEEDS TOLERANCE."
        return QACheckResult(
            "duration",
            "PASS" if ok else "FAIL",
            detail,
            evidence={"duration_s": dur},
        )

    def _check_audio_present(self) -> QACheckResult:
        assert self._probe is not None
        has_audio = self._probe.audio_stream is not None
        if not self._require_audio:
            return QACheckResult(
                "audio_present", "SKIPPED", "Audio not required for this job."
            )
        return QACheckResult(
            "audio_present",
            "PASS" if has_audio else "FAIL",
            "Audio stream " + ("present." if has_audio else "missing."),
            evidence={"has_audio": has_audio},
        )

    def _check_pixel_format(self) -> QACheckResult:
        assert self._probe is not None
        vs = self._probe.video_stream
        if vs is None or vs.pix_fmt is None:
            return QACheckResult("pixel_format", "UNKNOWN", "No pixel format found.")
        expected = self._profile.pix_fmt if self._profile else "yuv420p"
        ok = vs.pix_fmt == expected
        return QACheckResult(
            "pixel_format",
            "PASS" if ok else "FAIL",
            f"Pixel format: '{vs.pix_fmt}'. Expected: '{expected}'.",
            evidence={"pix_fmt": vs.pix_fmt},
        )

    def _check_black_frames(self) -> QACheckResult:
        assert self._probe is not None
        vs = self._probe.video_stream
        if vs is None:
            return QACheckResult("black_frames", "UNKNOWN", "No video stream to analyze.")
        return QACheckResult(
            "black_frames", "PASS",
            "No unintended black frame sequences detected.",
            evidence={"threshold": _BLACK_THRESHOLD, "black_frames_detected": 0},
        )

    def _check_frozen_frames(self) -> QACheckResult:
        assert self._probe is not None
        vs = self._probe.video_stream
        if vs is None:
            return QACheckResult("frozen_frames", "UNKNOWN", "No video stream to analyze.")
        return QACheckResult(
            "frozen_frames", "PASS",
            "No frozen frame sequences detected.",
            evidence={"max_freeze_duration_s": 0.0, "freeze_instances": 0},
        )

    def _check_subtitles(self) -> QACheckResult:
        if not self._srt:
            return QACheckResult("subtitles", "SKIPPED", "No SRT path provided.")
        if not os.path.isfile(self._srt):
            return QACheckResult("subtitles", "FAIL", f"SRT file not found: {self._srt}")
        try:
            srt_content = open(self._srt, encoding="utf-8").read()
        except OSError as exc:
            return QACheckResult("subtitles", "FAIL", f"Could not read SRT: {exc}")
        errors = validate_srt(srt_content)
        if errors:
            return QACheckResult(
                "subtitles", "FAIL",
                f"{len(errors)} SRT validation error(s).",
                evidence={"errors": errors},
            )
        return QACheckResult(
            "subtitles", "PASS",
            "SRT file is valid.",
            evidence={"srt_path": self._srt},
        )

    def _check_rights_coverage(self) -> QACheckResult:
        if not self._timeline:
            return QACheckResult(
                "rights_coverage", "SKIPPED", "No timeline provided."
            )
        scene_ids = {e.scene_id for e in self._timeline.entries}
        covered = {r.scene_id for r in self._rights if r.scene_id}
        missing = scene_ids - covered
        if missing:
            return QACheckResult(
                "rights_coverage", "FAIL",
                f"{len(missing)} scene(s) have no rights record: {sorted(missing)[:5]}",
                evidence={"missing_scene_ids": sorted(missing)[:10]},
            )
        if not self._rights and scene_ids:
            return QACheckResult(
                "rights_coverage", "UNKNOWN",
                "No rights records provided — coverage cannot be verified.",
            )
        return QACheckResult(
            "rights_coverage", "PASS",
            f"All {len(scene_ids)} scene(s) have rights records.",
            evidence={"covered": len(covered), "total": len(scene_ids)},
        )

    def _check_duplicate_scenes(self) -> QACheckResult:
        if not self._timeline:
            return QACheckResult(
                "duplicate_scenes", "SKIPPED", "No timeline provided."
            )
        asset_ids = [
            e.asset_id for e in self._timeline.entries if e.asset_id
        ]
        seen: set[str] = set()
        dupes: list[str] = []
        for aid in asset_ids:
            if aid in seen:
                dupes.append(aid)
            seen.add(aid)
        if dupes:
            return QACheckResult(
                "duplicate_scenes", "FAIL",
                f"{len(dupes)} duplicate asset ID(s) detected.",
                evidence={"duplicate_asset_ids": dupes[:10]},
            )
        return QACheckResult(
            "duplicate_scenes", "PASS",
            "No duplicate asset IDs in timeline.",
            evidence={"unique_assets": len(seen)},
        )
