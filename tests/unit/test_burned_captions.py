"""Tests for burned-in captions in VideoRenderer (Requirement 10)."""

import os
from unittest.mock import MagicMock, patch
import pytest

from sceneforge.rendering.normaliser import OutputProfile
from sceneforge.rendering.renderer import VideoRenderer
from sceneforge.timeline.builder import Timeline, TimelineEntry


@pytest.fixture
def sample_profile_16x9() -> OutputProfile:
    return OutputProfile(
        width=1920,
        height=1080,
        fps=30,
        video_codec="libx264",
        audio_codec="aac",
        pix_fmt="yuv420p",
        preset="fast",
        crf=23,
        audio_sample_rate=48000,
        audio_bitrate="192k",
    )


@pytest.fixture
def sample_profile_9x16() -> OutputProfile:
    return OutputProfile(
        width=1080,
        height=1920,
        fps=30,
        video_codec="libx264",
        audio_codec="aac",
        pix_fmt="yuv420p",
        preset="fast",
        crf=23,
        audio_sample_rate=48000,
        audio_bitrate="192k",
    )


def test_renderer_burns_captions_default(sample_profile_16x9):
    """VideoRenderer defaults to burn_captions=True."""
    renderer = VideoRenderer(sample_profile_16x9)
    assert renderer._burn_captions is True


def test_burn_captions_command_formatting_16x9(sample_profile_16x9, tmp_path):
    """FFmpeg burn_captions command contains bold, high-contrast subtitles filter."""
    renderer = VideoRenderer(sample_profile_16x9, burn_captions=True)
    video_path = str(tmp_path / "input.mp4")
    srt_path = str(tmp_path / "captions.srt")
    output_path = str(tmp_path / "output.mp4")

    with patch.object(renderer, "_run_ffmpeg") as mock_run:
        renderer._ffmpeg_burn_captions(video_path, srt_path, output_path)
        assert mock_run.called
        args = mock_run.call_args[0][0]
        assert "-vf" in args
        vf_idx = args.index("-vf")
        vf_val = args[vf_idx + 1]
        assert "subtitles=" in vf_val
        assert "Bold=1" in vf_val
        assert "Outline=3" in vf_val
        assert "MarginV=65" in vf_val
        assert "PrimaryColour=&H00FFFFFF" in vf_val
        assert "Alignment=2" in vf_val


def test_burn_captions_command_formatting_9x16_safe_area(sample_profile_9x16, tmp_path):
    """Vertical 9:16 videos position captions higher for social media safe area."""
    renderer = VideoRenderer(sample_profile_9x16, burn_captions=True)
    video_path = str(tmp_path / "input.mp4")
    srt_path = str(tmp_path / "captions.srt")
    output_path = str(tmp_path / "output.mp4")

    with patch.object(renderer, "_run_ffmpeg") as mock_run:
        renderer._ffmpeg_burn_captions(video_path, srt_path, output_path)
        assert mock_run.called
        args = mock_run.call_args[0][0]
        vf_idx = args.index("-vf")
        vf_val = args[vf_idx + 1]
        assert "MarginV=130" in vf_val
        assert "FontSize=34" in vf_val
