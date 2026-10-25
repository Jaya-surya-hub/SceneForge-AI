"""Retrieval interfaces — typed contracts for all retrieval components.

MediaAsset:         A single candidate returned by a provider.
SearchResult:       Output of a provider search call (candidates + metadata).
ComponentScores:    Breakdown of relevance score components.
RankedCandidate:    An asset with its full score breakdown and rationale.
RouteResult:        Output of the source router for a single scene.
ProviderError:      Typed error hierarchy for provider failures.
StockProvider:      Abstract interface for stock footage providers.
GeneratedProvider:  Abstract interface for AI-generated visual providers.
EmbeddingModel:     Abstract interface for text embedding models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

@dataclass
class MediaAsset:
    """A candidate media asset returned by a provider."""

    asset_id: str
    provider_name: str
    title: str
    description: str
    source_url: str
    provider_asset_url: str
    preview_url: str
    duration_seconds: Optional[float]        # None for still images
    width: Optional[int]
    height: Optional[int]
    licence_name: str
    licence_evidence_url: str
    commercial_use_eligible: bool
    attribution_required: bool
    attribution_text: str
    asset_type: str = "stock"               # "stock" | "generated" | "programmatic"
    tags: list[str] = field(default_factory=list)
    model_provenance: Optional[str] = None
    is_mock: bool = False
    sha256_hash: Optional[str] = None       # set after download/verification
    content_type: Optional[str] = None      # e.g. "video/mp4", "image/jpeg"
    # Licence flags — None = unknown/unverified
    commercial_use_verified: Optional[bool] = None


@dataclass
class SearchResult:
    """Output of a single provider search call."""

    provider_name: str
    query: str
    assets: list[MediaAsset]
    error: Optional[str] = None            # non-None = partial failure
    timed_out: bool = False
    is_mock: bool = False


@dataclass
class ComponentScores:
    """Breakdown of a candidate's relevance score.

    Each component is in [0.0, 1.0] or None when not computable.
    None means the score is missing/uncertain — never substitute 0.
    """

    text_similarity: Optional[float]       # lexical or embedding similarity
    tag_overlap: Optional[float]           # fraction of scene tags matched
    duration_fit: Optional[float]          # how well duration fits the scene
    resolution_fit: Optional[float]        # resolution adequacy
    aspect_ratio_fit: Optional[float]      # aspect ratio match
    duplicate_penalty: float = 0.0         # subtracted for repeated asset IDs
    # True = score came from a real embedding model; False = lexical heuristic
    embedding_used: bool = False


@dataclass
class RankedCandidate:
    """An asset with its full score breakdown and human-readable rationale."""

    asset: MediaAsset
    final_score: float                      # composite, in [0.0, 1.0]
    components: ComponentScores
    rationale: str                          # human-readable explanation
    rank: int = 0


@dataclass
class RouteResult:
    """Output of the source router for a single scene."""

    route: Literal["stock", "generated", "card", "unresolved"]
    selected_asset: Optional[MediaAsset]   # None when route == "card" or "unresolved"
    ranked_candidates: list[RankedCandidate]
    selection_reason: str
    fallback_attempts: list[str]           # ordered list of routes tried
    # "card" details — only when route == "card"
    card_type: Optional[Literal["typography_card", "data_card"]] = None
    # Error detail — only when route == "unresolved"
    error_code: Optional[str] = None


# ---------------------------------------------------------------------------
# Provider errors
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Base class for all retrieval provider errors."""

    retryable: bool = True

    def __init__(self, message: str, *, provider: str = "", retryable: bool = True) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.retryable = retryable


class ProviderTimeoutError(ProviderError):
    """Provider did not respond within the configured timeout."""
    retryable: bool = True


class ProviderHTTPError(ProviderError):
    """Provider returned an unexpected HTTP status code."""

    def __init__(
        self, message: str, *, provider: str = "", status_code: int = 0, retryable: bool = True
    ) -> None:
        super().__init__(message, provider=provider, retryable=retryable)
        self.status_code = status_code


class ProviderAuthError(ProviderError):
    """Provider returned an auth/credentials error (401/403)."""
    retryable: bool = False


class ProviderRateLimitError(ProviderError):
    """Provider rate limit exceeded (429)."""
    retryable: bool = True


class ProviderMalformedResponseError(ProviderError):
    """Provider returned a response that could not be parsed."""
    retryable: bool = False


class GeneratedProviderUnavailableError(ProviderError):
    """Generated-visual provider is not configured or unavailable."""
    retryable: bool = False


class MediaDownloadError(ProviderError):
    """Failed to download media file from provider URL."""
    retryable: bool = True


class MediaValidationError(ProviderError):
    """Downloaded file is empty, corrupt, or lacks a valid video stream."""
    retryable: bool = False


# ---------------------------------------------------------------------------
# CandidateScore (kept for backwards compatibility with Phase 2 mock_stock)
# ---------------------------------------------------------------------------

@dataclass
class CandidateScore:
    asset_id: str
    score: float
    reason: str


# ---------------------------------------------------------------------------
# Abstract interfaces
# ---------------------------------------------------------------------------

class StockProvider(ABC):
    """Interface for stock footage / image providers."""

    provider_name: str = "base"
    is_mock: bool = False

    @abstractmethod
    def search(self, query: str, *, max_results: int = 10) -> list[MediaAsset]:
        """Search and return up to *max_results* assets.

        Raises:
            ProviderError subclass on any failure.
        """


class GeneratedProvider(ABC):
    """Interface for AI-generated visual providers."""

    provider_name: str = "base"
    is_mock: bool = False

    @abstractmethod
    def generate(self, prompt: str) -> MediaAsset:
        """Generate a single asset from *prompt*.

        Raises:
            GeneratedProviderUnavailableError when not configured.
            ProviderError subclass on other failures.
        """


class EmbeddingModel(ABC):
    """Interface for text embedding models used in semantic ranking."""

    model_name: str = "base"
    is_mock: bool = False

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return a normalised embedding vector for *text*."""

    @abstractmethod
    def similarity(self, text_a: str, text_b: str) -> float:
        """Return cosine similarity in [0.0, 1.0] between two texts."""
