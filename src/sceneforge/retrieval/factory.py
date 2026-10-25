"""Retrieval provider factory.

Selects concrete implementations from environment configuration.

Environment variables:
  STOCK_PROVIDER   = mock (default) | pexels | pixabay | pexels,pixabay
  GENERATED_PROVIDER = none (default) | mock
  EMBEDDING_MODEL  = mock (default)

The generated-visual provider is reported as NOT genuinely implemented —
no production generative video provider is integrated. The mock is used for
testing the routing logic. Any claim of a real generative provider would
require an end-to-end test with actual image/video output.
"""

from __future__ import annotations

import os
from typing import Optional

from sceneforge.retrieval.interfaces import (
    EmbeddingModel,
    GeneratedProvider,
    StockProvider,
)


def get_stock_providers(override: Optional[str] = None) -> list[StockProvider]:
    """Return configured stock provider(s).

    Returns a list so multiple providers can be queried in parallel.
    Falls back to mock when no API key is configured for a named provider.
    """
    names_str = (override or os.getenv("STOCK_PROVIDER", "mock")).lower().strip()
    names = [n.strip() for n in names_str.split(",")]

    providers: list[StockProvider] = []
    for name in names:
        provider = _make_stock_provider(name)
        if provider is not None:
            providers.append(provider)

    if not providers:
        from sceneforge.retrieval.adapters.mock_stock import MockStockProvider
        providers.append(MockStockProvider())

    return providers


def _make_stock_provider(name: str) -> Optional[StockProvider]:
    if name == "pexels":
        key = os.getenv("PEXELS_API_KEY", "")
        if not key:
            from sceneforge.retrieval.adapters.mock_stock import MockStockProvider
            return MockStockProvider()
        try:
            from sceneforge.retrieval.adapters.pexels import PexelsAdapter
            return PexelsAdapter(api_key=key)
        except Exception:
            return None

    if name == "pixabay":
        key = os.getenv("PIXABAY_API_KEY", "")
        if not key:
            from sceneforge.retrieval.adapters.mock_stock import MockStockProvider
            return MockStockProvider()
        try:
            from sceneforge.retrieval.adapters.pixabay import PixabayAdapter
            return PixabayAdapter(api_key=key)
        except Exception:
            return None

    # Default / "mock"
    from sceneforge.retrieval.adapters.mock_stock import MockStockProvider
    return MockStockProvider()


def get_generated_provider(override: Optional[str] = None) -> Optional[GeneratedProvider]:
    """Return the configured generated-visual provider, or None.

    IMPORTANT: No production generative video provider is implemented.
    The mock provider is the only available implementation. This is
    explicitly documented — do not claim a real provider is operational.
    """
    name = (override or os.getenv("GENERATED_PROVIDER", "none")).lower().strip()

    if name == "mock":
        from sceneforge.retrieval.adapters.mock_generated import MockGeneratedProvider
        return MockGeneratedProvider()

    # "none" or any unrecognised name → no generated provider
    return None


def get_embedding_model(override: Optional[str] = None) -> Optional[EmbeddingModel]:
    """Return the configured embedding model, or None.

    None triggers lexical fallback in the ranker (Jaccard similarity).
    'mock' returns the deterministic hash-based mock model.
    'sentence_transformers' loads the local all-MiniLM-L6-v2 model (Apache 2.0).
    """
    name = (override or os.getenv("EMBEDDING_MODEL", "mock")).lower().strip()

    if name in ("none", ""):
        return None

    if name == "mock":
        from sceneforge.retrieval.adapters.mock_embeddings import MockEmbeddingModel
        return MockEmbeddingModel()

    if name in ("sentence_transformers", "sentence-transformers", "all-minilm-l6-v2"):
        try:
            from sceneforge.retrieval.adapters.sentence_transformer import (
                SentenceTransformerEmbeddingModel,
            )
            return SentenceTransformerEmbeddingModel()
        except ImportError:
            return None

    return None
