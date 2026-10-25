"""Unit tests for MediaDownloader (src/sceneforge/retrieval/downloader.py)."""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from sceneforge.retrieval.downloader import DownloadedMedia, MediaDownloader
from sceneforge.retrieval.interfaces import (
    MediaAsset,
    MediaDownloadError,
    MediaValidationError,
)


def _make_mock_asset(
    asset_id: str = "mock-stock-001",
    provider: str = "mock_stock",
    url: str = "https://mock.example/stock/001/download",
    is_mock: bool = True,
) -> MediaAsset:
    return MediaAsset(
        asset_id=asset_id,
        provider_name=provider,
        title="Mock Test Clip",
        description="A test video clip for unit testing",
        source_url="https://mock.example/stock/001",
        provider_asset_url=url,
        preview_url="https://mock.example/stock/001/preview.jpg",
        duration_seconds=5.0,
        width=1920,
        height=1080,
        licence_name="Mock-CC0",
        licence_evidence_url="https://mock.example/licence/cc0",
        commercial_use_eligible=True,
        attribution_required=False,
        attribution_text="",
        asset_type="stock",
        tags=["mock", "test"],
        is_mock=is_mock,
    )


class TestMediaDownloader:
    def test_mock_asset_download_and_validate(self, tmp_path):
        """Mock asset triggers mock motion synthesis and produces valid DownloadedMedia."""
        mock_storage = MagicMock()
        downloader = MediaDownloader(storage_client=mock_storage, work_dir=str(tmp_path))
        asset = _make_mock_asset()

        result = downloader.download_and_validate(asset, target_duration=5.0, job_id="test-job-1")

        assert isinstance(result, DownloadedMedia)
        assert result.asset_id == "mock-stock-001"
        assert result.is_mock is True
        assert os.path.isfile(result.local_path)
        assert result.size_bytes > 0
        assert len(result.sha256_hash) == 64
        assert result.storage_key == "raw_assets/mock-stock-001.mp4"
        assert mock_storage.upload_bytes.called

    def test_compute_sha256(self, tmp_path):
        """SHA-256 calculation matches hashlib on actual file bytes."""
        downloader = MediaDownloader()
        f = tmp_path / "test.bin"
        content = b"hello world test content"
        f.write_bytes(content)
        expected_hash = hashlib.sha256(content).hexdigest()

        assert downloader._compute_file_sha256(str(f)) == expected_hash

    def test_http_download_success(self, tmp_path):
        """Valid HTTP response streams to disk and produces DownloadedMedia."""
        mock_storage = MagicMock()
        downloader = MediaDownloader(storage_client=mock_storage, work_dir=str(tmp_path))
        asset = _make_mock_asset(
            asset_id="pexels-12345",
            provider="pexels",
            url="https://example.com/real_video.mp4",
            is_mock=False,
        )

        dummy_mp4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41\x00\x00\x00\x08free" + (b"\x00" * 2048)
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.side_effect = [dummy_mp4, b""]
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = downloader.download_and_validate(asset, target_duration=6.0, job_id="http-job")

        assert result.asset_id == "pexels-12345"
        assert result.is_mock is False
        assert os.path.isfile(result.local_path)
        assert result.size_bytes == len(dummy_mp4)

    def test_http_download_http_error(self, tmp_path):
        """HTTP error raises MediaDownloadError."""
        mock_storage = MagicMock()
        downloader = MediaDownloader(
            storage_client=mock_storage,
            work_dir=str(tmp_path),
            max_retries=0,
        )
        asset = _make_mock_asset(
            asset_id="pexels-bad",
            provider="pexels",
            url="https://example.com/404.mp4",
            is_mock=False,
        )

        mock_err = urllib.error.HTTPError(
            url="https://example.com/404.mp4",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=io.BytesIO(b""),
        )
        with patch("urllib.request.urlopen", side_effect=mock_err):
            with pytest.raises(MediaDownloadError, match="Failed to download media"):
                downloader.download_and_validate(asset, job_id="err-job")

    def test_file_too_small_raises_validation_error(self, tmp_path):
        """File smaller than minimum threshold raises MediaValidationError."""
        mock_storage = MagicMock()
        downloader = MediaDownloader(
            storage_client=mock_storage,
            work_dir=str(tmp_path),
            max_retries=0,
        )
        asset = _make_mock_asset(
            asset_id="pexels-tiny",
            provider="pexels",
            url="https://example.com/tiny.mp4",
            is_mock=False,
        )

        tiny_content = b"toosmall"  # 8 bytes (< 1024)
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.side_effect = [tiny_content, b""]
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            with pytest.raises(MediaValidationError, match="too small"):
                downloader.download_and_validate(asset, job_id="tiny-job")

    def test_storage_failure_does_not_abort_pipeline(self, tmp_path):
        """If storage upload fails, download_and_validate still returns DownloadedMedia."""
        failing_storage = MagicMock()
        failing_storage.upload_bytes.side_effect = RuntimeError("S3 connection refused")

        downloader = MediaDownloader(storage_client=failing_storage, work_dir=str(tmp_path))
        asset = _make_mock_asset()

        result = downloader.download_and_validate(asset, job_id="storage-fail-job")
        assert result.asset_id == asset.asset_id
        assert os.path.isfile(result.local_path)

    def test_mock_motion_configurable_timeout(self, tmp_path):
        """Downloader respects MOCK_MOTION_TIMEOUT env var and constructor param."""
        with patch.dict(os.environ, {"MOCK_MOTION_TIMEOUT": "110"}):
            import importlib
            import sceneforge.retrieval.downloader as dl_module
            importlib.reload(dl_module)
            try:
                dl = dl_module.MediaDownloader()
                assert dl._mock_motion_timeout == 110

                dl_custom = dl_module.MediaDownloader(mock_motion_timeout=125)
                assert dl_custom._mock_motion_timeout == 125
            finally:
                # restore default
                os.environ.pop("MOCK_MOTION_TIMEOUT", None)
                importlib.reload(dl_module)

    def test_mock_motion_timeout_triggers_fallback_and_cleans_up_partial_file(self, tmp_path):
        """When primary FFmpeg generation times out, partial files are removed and fallback clip is used."""
        import subprocess
        mock_storage = MagicMock()
        downloader = MediaDownloader(
            storage_client=mock_storage,
            work_dir=str(tmp_path),
            mock_motion_timeout=90,
        )
        asset = _make_mock_asset(asset_id="mock-timeout-001")

        # Simulate timeout on the first subprocess.run (primary motion generation),
        # but let fallback generator succeed with a valid mock clip.
        timeout_err = subprocess.TimeoutExpired(
            cmd=["ffmpeg", "mock"],
            timeout=90,
            stderr="frame=12 fps=2 q=28.0 size=256kB time=00:00:00.80 bitrate=2621.4kbits/s",
        )

        def mock_generate_fallback(target_path, width, height, duration):
            # Write a valid dummy file > 1024 bytes representing fallback clip
            with open(target_path, "wb") as f:
                f.write(b"\x00" * 2048)
            return True

        with patch("sceneforge.retrieval.downloader.is_ffmpeg_available", return_value=True), \
             patch("subprocess.run", side_effect=timeout_err), \
             patch.object(downloader, "_generate_fallback_clip", side_effect=mock_generate_fallback) as mock_fb, \
             patch("sceneforge.retrieval.downloader.is_ffprobe_available", return_value=False):
            result = downloader.download_and_validate(asset, target_duration=5.0, job_id="timeout-job")

        assert mock_fb.called
        assert result.asset_id == "mock-timeout-001"
        assert os.path.isfile(result.local_path)
        assert os.path.getsize(result.local_path) == 2048

    def test_mock_motion_double_failure_raises_media_download_error_no_corrupt_file(self, tmp_path):
        """When both primary FFmpeg generation and fallback fail, raises MediaDownloadError without leaving partial/corrupt file."""
        import subprocess
        mock_storage = MagicMock()
        downloader = MediaDownloader(
            storage_client=mock_storage,
            work_dir=str(tmp_path),
            mock_motion_timeout=90,
        )
        asset = _make_mock_asset(asset_id="mock-fail-002")

        timeout_err = subprocess.TimeoutExpired(
            cmd=["ffmpeg", "mock"],
            timeout=90,
            stderr="Timed out generating 1080p stream",
        )

        with patch("sceneforge.retrieval.downloader.is_ffmpeg_available", return_value=True), \
             patch("subprocess.run", side_effect=timeout_err), \
             patch.object(downloader, "_generate_fallback_clip", return_value=False):
            with pytest.raises(MediaDownloadError, match="FFmpeg generation and fallback both failed"):
                downloader.download_and_validate(asset, target_duration=5.0, job_id="double-fail-job")

        # Verify no corrupt file was left at the destination
        expected_dest = os.path.join(str(tmp_path), "asset_mock-fail-002.mp4")
        assert not os.path.exists(expected_dest)
