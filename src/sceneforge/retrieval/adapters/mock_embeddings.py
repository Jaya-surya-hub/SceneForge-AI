"""Mock embedding model — deterministic cosine similarity, no ML dependency.

Returns a fixed-dimension vector derived from a simple hash of the input text.
Similarity scores are deterministic but not semantically meaningful.
This adapter exists for the no-key test suite (IS-07, MH-08).
"""

from __future__ import annotations

import hashlib
import math

from sceneforge.retrieval.interfaces import EmbeddingModel

_DIM = 64  # embedding dimension for mock


def _hash_embed(text: str) -> list[float]:
    """Generate a deterministic unit vector from text via SHA-256."""
    digest = hashlib.sha256(text.encode()).digest()
    # Repeat digest bytes to fill _DIM floats
    raw = []
    for i in range(_DIM):
        raw.append(float(digest[i % len(digest)]) / 255.0 - 0.5)
    # Normalise to unit vector
    norm = math.sqrt(sum(x * x for x in raw))
    if norm == 0.0:
        return [0.0] * _DIM
    return [x / norm for x in raw]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    # Both vectors are already normalised, so cosine = dot product
    return max(0.0, min(1.0, (dot + 1.0) / 2.0))  # map [-1,1] → [0,1]


class MockEmbeddingModel(EmbeddingModel):
    """[MOCK] Deterministic embedding model for the no-key test suite.

    Embeddings are hash-derived and NOT semantically meaningful.
    Use only for testing the pipeline mechanics, not ranking quality.
    """

    model_name: str = "mock_embeddings"
    is_mock: bool = True

    def embed(self, text: str) -> list[float]:
        """Return a deterministic hash-derived unit vector.

        NOTE: This is a MOCK adapter. Vectors are not semantically meaningful.
        """
        return _hash_embed(text)

    def similarity(self, text_a: str, text_b: str) -> float:
        """Return deterministic cosine similarity in [0, 1].

        NOTE: This is a MOCK adapter. Scores are not semantically meaningful.
        """
        return _cosine(_hash_embed(text_a), _hash_embed(text_b))
