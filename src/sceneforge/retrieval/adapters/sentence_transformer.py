"""Sentence-Transformers embedding adapter.

Uses the 'all-MiniLM-L6-v2' model (Apache 2.0, ~80 MB) for local
semantic text similarity. No API key required.

Feature-flagged: only loaded when EMBEDDING_MODEL=sentence_transformers.
Mock embeddings are the default for all tests.

Install: pip install sentence-transformers
Model is downloaded on first use (~80 MB).
"""

from __future__ import annotations

import os
from typing import Optional

from sceneforge.retrieval.interfaces import EmbeddingModel

_MODEL_NAME = os.getenv("ST_MODEL_NAME", "all-MiniLM-L6-v2")

_cached_model: Optional[object] = None


def _get_model():
    global _cached_model
    if _cached_model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            )
        _cached_model = SentenceTransformer(_MODEL_NAME)
    return _cached_model


class SentenceTransformerEmbeddingModel(EmbeddingModel):
    """Local embedding model using sentence-transformers (Apache 2.0).

    No API key required. Model downloaded on first call (~80 MB).
    Results are semantically meaningful (unlike the mock).
    """

    model_name: str = "sentence_transformers"
    is_mock: bool = False

    def embed(self, text: str) -> list[float]:
        model = _get_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def similarity(self, text_a: str, text_b: str) -> float:
        import math
        vec_a = self.embed(text_a)
        vec_b = self.embed(text_b)
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        # Both vectors are normalised so cosine = dot product
        return max(0.0, min(1.0, (dot + 1.0) / 2.0))
