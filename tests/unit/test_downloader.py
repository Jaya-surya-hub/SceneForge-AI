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
