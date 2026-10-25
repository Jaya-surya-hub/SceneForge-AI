"""Mock stock footage provider — deterministic, no API keys required.

Returns a fixed catalogue of 5 fictional assets for any query.
Assets have known licence metadata, commercial eligibility, and stable IDs.
Asset URLs point to placeholder paths — no real media is fetched.

This adapter MUST NOT be used to claim real footage was retrieved.
It exists solely for the no-key test suite (IS-07, MH-08).
"""

from __future__ import annotations

from sceneforge.retrieval.interfaces import MediaAsset, StockProvider

_MOCK_CATALOGUE: list[MediaAsset] = [
    MediaAsset(
        asset_id="mock-stock-001",
        provider_name="mock_stock",
        title="City skyline timelapse",
        description="A timelapse of a modern city skyline at dusk with lights appearing",
        source_url="https://mock.example/stock/001",
        provider_asset_url="https://mock.example/stock/001/download",
        preview_url="https://mock.example/stock/001/preview.jpg",
        duration_seconds=10.0,
        width=1920,
        height=1080,
        licence_name="Mock-CC0",
        licence_evidence_url="https://mock.example/licence/cc0",
        commercial_use_eligible=True,
        attribution_required=False,
        attribution_text="",
        asset_type="stock",
        tags=["city", "skyline", "timelapse", "urban"],
        is_mock=True,
    ),
    MediaAsset(
        asset_id="mock-stock-002",
        provider_name="mock_stock",
        title="Ocean waves on beach",
        description="Slow motion ocean waves crashing gently on a sandy beach",
        source_url="https://mock.example/stock/002",
        provider_asset_url="https://mock.example/stock/002/download",
        preview_url="https://mock.example/stock/002/preview.jpg",
        duration_seconds=8.0,
        width=1920,
        height=1080,
        licence_name="Mock-CC0",
        licence_evidence_url="https://mock.example/licence/cc0",
        commercial_use_eligible=True,
        attribution_required=False,
        attribution_text="",
        asset_type="stock",
        tags=["ocean", "beach", "waves", "nature"],
        is_mock=True,
    ),
    MediaAsset(
        asset_id="mock-stock-003",
        provider_name="mock_stock",
        title="People walking in office",
        description="Diverse team of professionals walking through a modern open-plan office",
        source_url="https://mock.example/stock/003",
        provider_asset_url="https://mock.example/stock/003/download",
        preview_url="https://mock.example/stock/003/preview.jpg",
        duration_seconds=6.0,
        width=1920,
        height=1080,
        licence_name="Mock-CC0",
        licence_evidence_url="https://mock.example/licence/cc0",
        commercial_use_eligible=True,
        attribution_required=False,
        attribution_text="",
        asset_type="stock",
        tags=["office", "people", "work", "professional"],
        is_mock=True,
    ),
    MediaAsset(
        asset_id="mock-stock-004",
        provider_name="mock_stock",
        title="Green forest path",
        description="A peaceful sunlit path through a lush green forest",
        source_url="https://mock.example/stock/004",
        provider_asset_url="https://mock.example/stock/004/download",
        preview_url="https://mock.example/stock/004/preview.jpg",
        duration_seconds=12.0,
        width=1920,
        height=1080,
        licence_name="Mock-CC0",
        licence_evidence_url="https://mock.example/licence/cc0",
        commercial_use_eligible=True,
        attribution_required=False,
        attribution_text="",
        asset_type="stock",
        tags=["forest", "nature", "path", "trees"],
        is_mock=True,
    ),
    MediaAsset(
        asset_id="mock-stock-005",
        provider_name="mock_stock",
        title="Technology circuit board",
        description="Macro shot of a glowing blue circuit board with data streams",
        source_url="https://mock.example/stock/005",
        provider_asset_url="https://mock.example/stock/005/download",
        preview_url="https://mock.example/stock/005/preview.jpg",
        duration_seconds=7.0,
        width=1920,
        height=1080,
        licence_name="Mock-CC0",
        licence_evidence_url="https://mock.example/licence/cc0",
        commercial_use_eligible=True,
        attribution_required=False,
        attribution_text="",
        asset_type="stock",
        tags=["technology", "circuit", "digital", "innovation"],
        is_mock=True,
    ),
]


class MockStockProvider(StockProvider):
    """[MOCK] Deterministic stock provider for the no-key test suite.

    Returns the same catalogue for any query. Assets have no real media files.
    """

    provider_name: str = "mock_stock"
    is_mock: bool = True

    def search(self, query: str, *, max_results: int = 10) -> list[MediaAsset]:
        """Return up to *max_results* assets from the fixed mock catalogue.

        NOTE: This is a MOCK adapter. No real footage is retrieved.
        """
        return _MOCK_CATALOGUE[:max_results]
