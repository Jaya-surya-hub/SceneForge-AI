"""Mock generated-visual provider — deterministic, no API keys required.

Returns a single fixed still-image asset for any prompt.
This adapter MUST NOT be used to claim real image generation occurred.
"""

from __future__ import annotations

from sceneforge.retrieval.interfaces import GeneratedProvider, MediaAsset

_MOCK_GENERATED_ASSET = MediaAsset(
    asset_id="mock-gen-001",
    provider_name="mock_generated",
    title="Abstract gradient background",
    description="A smooth abstract gradient of blues and purples",
    source_url="https://mock.example/generated/001",
    provider_asset_url="https://mock.example/generated/001/download",
    preview_url="https://mock.example/generated/001/preview.jpg",
    duration_seconds=None,   # still image
    width=1920,
    height=1080,
    licence_name="Mock-CC0",
    licence_evidence_url="https://mock.example/licence/cc0",
    commercial_use_eligible=True,
    attribution_required=False,
    attribution_text="",
    asset_type="generated",
    tags=["abstract", "gradient", "background"],
    model_provenance="mock_generated_v0.1",
    is_mock=True,
)


class MockGeneratedProvider(GeneratedProvider):
    """[MOCK] Deterministic generated-visual provider for the no-key test suite.

    Returns the same abstract image asset for any prompt.
    NOTE: No image generation is performed.
    """

    provider_name: str = "mock_generated"
    is_mock: bool = True

    def generate(self, prompt: str) -> MediaAsset:
        """Return the fixed mock generated asset. Prompt is ignored.

        NOTE: This is a MOCK adapter. No image is generated.
        """
        return _MOCK_GENERATED_ASSET
