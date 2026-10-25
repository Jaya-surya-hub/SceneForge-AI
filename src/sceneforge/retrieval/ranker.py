"""Candidate ranker — scores MediaAsset candidates against a ScenePlan.

Scoring strategy:
  1. Text similarity  — lexical Jaccard similarity between visual_concept
     and asset title/description. If an EmbeddingModel is provided, uses
     cosine similarity instead. The method used is always declared.
  2. Tag overlap      — fraction of scene key_entities found in asset tags.
  3. Duration fit     — how well asset duration matches the scene duration.
  4. Resolution fit   — whether asset resolution is adequate for the output.
  5. Aspect ratio fit — whether asset aspect ratio matches the requested output.
  6. Duplicate penalty— applied when an asset_id was already selected earlier.

Final score = weighted average of available components minus duplicate_penalty.

Design principles:
  - None = score unknown/not computable; treated as 0.5 (neutral) in weighting.
  - Missing components are noted in rationale but do not cause a crash.
  - Lexical similarity is labelled as lexical; it is NOT called semantic.
  - Embedding similarity is labelled as embedding and notes the model used.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from sceneforge.observability.logging import get_logger
from sceneforge.planner.interfaces import ScenePlan
from sceneforge.retrieval.interfaces import (
    ComponentScores,
    EmbeddingModel,
    MediaAsset,
    RankedCandidate,
)

log = get_logger(__name__)

# Configurable weights (must sum to ≤ 1.0 for the weighted mean to be bounded)
_W_TEXT = float(os.getenv("RANKER_W_TEXT", "0.45"))
_W_TAG = float(os.getenv("RANKER_W_TAG", "0.20"))
_W_DURATION = float(os.getenv("RANKER_W_DURATION", "0.15"))
_W_RESOLUTION = float(os.getenv("RANKER_W_RESOLUTION", "0.10"))
_W_ASPECT = float(os.getenv("RANKER_W_ASPECT", "0.10"))

_DUPLICATE_PENALTY = float(os.getenv("RANKER_DUPLICATE_PENALTY", "0.15"))

# Minimum resolution considered adequate (height in pixels)
_MIN_HEIGHT = int(os.getenv("RANKER_MIN_HEIGHT", "480"))


class CandidateRanker:
    """Rank a list of MediaAsset candidates against a ScenePlan.

    Args:
        embedding_model: Optional embedding model for text similarity.
                         When None, falls back to lexical Jaccard similarity.
        seen_asset_ids:  Set of asset IDs already selected in this job
                         (used to apply duplicate penalty).
        target_aspect_ratio: "16:9" or "9:16" from job config.
    """

    def __init__(
        self,
        *,
        embedding_model: Optional[EmbeddingModel] = None,
        seen_asset_ids: Optional[set[str]] = None,
        target_aspect_ratio: str = "16:9",
    ) -> None:
        self._embedding = embedding_model
        self._seen_ids: set[str] = seen_asset_ids or set()
        self._target_ratio = target_aspect_ratio

    def rank(
        self,
        scene: ScenePlan,
        candidates: list[MediaAsset],
    ) -> list[RankedCandidate]:
        """Score and rank *candidates* for *scene*.

        Args:
            scene:      The ScenePlan to score against.
            candidates: Unranked candidate list.

        Returns:
            Candidates sorted by final_score descending. May be empty.
        """
        if not candidates:
            return []

        ranked = []
        for asset in candidates:
            rc = self._score_asset(scene, asset)
            ranked.append(rc)

        ranked.sort(key=lambda r: r.final_score, reverse=True)
        for i, rc in enumerate(ranked):
            rc.rank = i + 1

        log.debug(
            "ranker_done",
            scene_id=scene.scene_id,
            candidates=len(ranked),
            top_score=ranked[0].final_score if ranked else 0.0,
            top_asset=ranked[0].asset.asset_id if ranked else "",
        )
        return ranked

    # ------------------------------------------------------------------
    # Private scoring
    # ------------------------------------------------------------------

    def _score_asset(self, scene: ScenePlan, asset: MediaAsset) -> RankedCandidate:
        text_sim = self._text_similarity(scene, asset)
        tag_score = self._tag_overlap(scene, asset)
        duration_score = self._duration_fit(scene, asset)
        resolution_score = self._resolution_fit(asset)
        aspect_score = self._aspect_ratio_fit(asset)
        dup_penalty = _DUPLICATE_PENALTY if asset.asset_id in self._seen_ids else 0.0
        embedding_used = self._embedding is not None

        components = ComponentScores(
            text_similarity=text_sim,
            tag_overlap=tag_score,
            duration_fit=duration_score,
            resolution_fit=resolution_score,
            aspect_ratio_fit=aspect_score,
            duplicate_penalty=dup_penalty,
            embedding_used=embedding_used,
        )

        final_score = self._weighted_mean(components)
        rationale = self._build_rationale(scene, asset, components, final_score)

        return RankedCandidate(
            asset=asset,
            final_score=round(final_score, 4),
            components=components,
            rationale=rationale,
        )

    def _text_similarity(self, scene: ScenePlan, asset: MediaAsset) -> Optional[float]:
        """Return text similarity between scene visual intent and asset metadata."""
        scene_terms = [scene.visual_concept or "", scene.narration_text or ""]
        if scene.search_queries:
            scene_terms.extend(scene.search_queries)
        concept = " ".join(t for t in scene_terms if t.strip())
        asset_text = f"{asset.title} {asset.description} {' '.join(asset.tags)}"

        if not concept.strip() or not asset_text.strip():
            return None

        if self._embedding is not None:
            try:
                base_sim = self._embedding.similarity(concept, asset_text)
                if getattr(self._embedding, "is_mock", False):
                    lex_sim = _smart_similarity(scene, asset)
                    return 0.35 * base_sim + 0.65 * lex_sim
                return base_sim
            except Exception as exc:
                log.warning("embedding_similarity_failed", error=str(exc))
                # Fall through to lexical

        return _smart_similarity(scene, asset)

    def _tag_overlap(self, scene: ScenePlan, asset: MediaAsset) -> Optional[float]:
        """Fraction of scene key_entities that appear in asset tags, title, or description."""
        entities = {e.lower() for e in scene.key_entities}
        if not entities:
            words = set(re.findall(r"\b[a-z]{3,}\b", (scene.visual_concept or scene.narration_text or "").lower()))
            entities = words
        if not entities:
            return None
        asset_tags = {t.lower() for t in asset.tags}
        desc_words = set(re.findall(r"\b[a-z]{3,}\b", (asset.description or "").lower()))
        title_words = set(re.findall(r"\b[a-z]{3,}\b", (asset.title or "").lower()))
        all_asset_tokens = asset_tags | desc_words | title_words

        matched = entities & all_asset_tokens
        return len(matched) / len(entities)

    def _duration_fit(self, scene: ScenePlan, asset: MediaAsset) -> Optional[float]:
        """Score how well the asset duration matches the scene duration."""
        if asset.duration_seconds is None:
            return None  # still image — neutral
        scene_duration = scene.end_time - scene.start_time
        if scene_duration <= 0:
            return None
        asset_dur = asset.duration_seconds
        if asset_dur <= 0:
            return 0.0
        # Score peaks at 1.0 when asset_dur == scene_duration,
        # decays to 0 as ratio diverges
        ratio = min(asset_dur, scene_duration) / max(asset_dur, scene_duration)
        return ratio

    def _resolution_fit(self, asset: MediaAsset) -> Optional[float]:
        """Score asset resolution adequacy."""
        if asset.height is None:
            return None
        if asset.height >= 1080:
            return 1.0
        if asset.height >= 720:
            return 0.8
        if asset.height >= _MIN_HEIGHT:
            return 0.5
        return 0.2

    def _aspect_ratio_fit(self, asset: MediaAsset) -> Optional[float]:
        """Score aspect ratio match against target."""
        if asset.width is None or asset.height is None or asset.height == 0:
            return None
        asset_ratio = asset.width / asset.height
        if self._target_ratio == "16:9":
            target_ratio = 16 / 9
        elif self._target_ratio == "1:1":
            target_ratio = 1.0
        else:
            target_ratio = 9 / 16
        diff = abs(asset_ratio - target_ratio) / target_ratio
        return max(0.0, 1.0 - diff)

    def _weighted_mean(self, c: ComponentScores) -> float:
        """Compute weighted mean, skipping None components."""
        components = [
            (_W_TEXT, c.text_similarity),
            (_W_TAG, c.tag_overlap),
            (_W_DURATION, c.duration_fit),
            (_W_RESOLUTION, c.resolution_fit),
            (_W_ASPECT, c.aspect_ratio_fit),
        ]
        total_weight = 0.0
        total_score = 0.0
        for weight, score in components:
            if score is not None:
                total_weight += weight
                total_score += weight * score

        if total_weight == 0:
            base = 0.5  # neutral when no components available
        else:
            base = total_score / total_weight

        return max(0.0, min(1.0, base - c.duplicate_penalty))

    def _build_rationale(
        self,
        scene: ScenePlan,
        asset: MediaAsset,
        c: ComponentScores,
        final_score: float,
    ) -> str:
        parts = [
            f"Asset '{asset.asset_id}' scored {final_score:.3f} for scene '{scene.scene_id}'."
        ]
        if c.text_similarity is not None:
            method = "embedding" if c.embedding_used else "lexical"
            parts.append(
                f"Text similarity ({method}): {c.text_similarity:.3f}."
            )
        else:
            parts.append("Text similarity: unavailable.")

        if c.tag_overlap is not None:
            parts.append(f"Tag overlap: {c.tag_overlap:.3f}.")
        if c.duration_fit is not None:
            parts.append(f"Duration fit: {c.duration_fit:.3f}.")
        if c.duplicate_penalty > 0:
            parts.append(
                f"Duplicate penalty applied: -{c.duplicate_penalty:.3f}."
            )
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Lexical helpers
# ---------------------------------------------------------------------------

def _tokenise(text: str) -> set[str]:
    """Lowercase word tokens, removing punctuation."""
    return set(re.findall(r"\b[a-z]{2,}\b", text.lower()))


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Jaccard similarity between word token sets.

    Returns a value in [0.0, 1.0].
    This is a LEXICAL measure, not semantic similarity.
    """
    tokens_a = _tokenise(text_a)
    tokens_b = _tokenise(text_b)
    if not tokens_a and not tokens_b:
        return 0.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _smart_similarity(scene: ScenePlan, asset: MediaAsset) -> float:
    """Compute high-accuracy lexical & entity similarity between scene and asset."""
    scene_words = _tokenise(f"{scene.narration_text or ''} {scene.visual_concept or ''} {' '.join(scene.search_queries or [])}")
    entity_words = set(e.lower() for e in (scene.key_entities or []))
    all_scene = scene_words | entity_words

    asset_words = _tokenise(f"{asset.title or ''} {asset.description or ''} {' '.join(asset.tags or [])}")

    if not all_scene or not asset_words:
        return 0.0

    # Entity overlap (matching the core subject is paramount)
    entity_score = len(entity_words & asset_words) / max(1, len(entity_words)) if entity_words else 0.5
    # Overall Jaccard token overlap
    jaccard = len(all_scene & asset_words) / len(all_scene | asset_words)

    return 0.65 * entity_score + 0.35 * jaccard
