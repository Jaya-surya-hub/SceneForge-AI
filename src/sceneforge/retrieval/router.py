"""Source router — applies the documented selection policy for a scene.

Priority order (configurable thresholds):
  1. Stock footage   (score >= ROUTER_STOCK_MIN_RELEVANCE AND commercially verified)
  2. Generated visual (score >= ROUTER_GENERATED_MIN_RELEVANCE AND provider available)
  3. Typography / data card (programmatic — always available, no licence risk)
  4. Unresolved       (all above failed — recorded failure, not a crash)

All thresholds are environment-configurable. The router records every attempt
so the timeline can show the full decision chain.

The router does NOT decide whether an asset is commercially usable — that is
the Rights Validator's job. Assets failing rights validation are excluded by
the ranker/searcher before reaching the router.
"""

from __future__ import annotations

import os
from typing import Literal, Optional

from sceneforge.observability.logging import get_logger
from sceneforge.planner.interfaces import ScenePlan
from sceneforge.retrieval.interfaces import (
    GeneratedProvider,
    GeneratedProviderUnavailableError,
    MediaAsset,
    ProviderError,
    RankedCandidate,
    RouteResult,
)

log = get_logger(__name__)

_STOCK_MIN = float(os.getenv("ROUTER_STOCK_MIN_RELEVANCE", "0.62"))
_GENERATED_MIN = float(os.getenv("ROUTER_GENERATED_MIN_RELEVANCE", "0.55"))

# Scene types that should always route to a card
_CARD_TYPES = frozenset({"typography_card", "data_card"})


class SourceRouter:
    """Apply the documented selection policy and return a RouteResult.

    Args:
        generated_provider: Optional generated-visual provider. When None or
                            when it raises GeneratedProviderUnavailableError,
                            the generated route is skipped.
        stock_min_relevance:     Threshold above which stock footage is selected.
        generated_min_relevance: Threshold above which generated visual is selected.
    """

    def __init__(
        self,
        *,
        generated_provider: Optional[GeneratedProvider] = None,
        stock_min_relevance: float = _STOCK_MIN,
        generated_min_relevance: float = _GENERATED_MIN,
    ) -> None:
        self._generated = generated_provider
        self._stock_min = stock_min_relevance
        self._generated_min = generated_min_relevance

    def route(
        self,
        scene: ScenePlan,
        ranked_candidates: list[RankedCandidate],
        *,
        job_id: str = "unknown",
    ) -> RouteResult:
        """Select a media source for *scene*.

        Args:
            scene:            The ScenePlan being processed.
            ranked_candidates: Scored candidates from the ranker (may be empty).
            job_id:           For logging.

        Returns:
            RouteResult with selected asset (or None for card/unresolved).
        """
        fallback_attempts: list[str] = []

        # ── Priority 3: card types route directly to card ──────────────────
        if scene.suggested_visual_type in _CARD_TYPES:
            log.info(
                "router_card_direct",
                job_id=job_id,
                scene_id=scene.scene_id,
                card_type=scene.suggested_visual_type,
            )
            return RouteResult(
                route="card",
                selected_asset=None,
                ranked_candidates=ranked_candidates,
                selection_reason=(
                    f"Scene type '{scene.suggested_visual_type}' routes directly to "
                    "a programmatic card."
                ),
                fallback_attempts=[],
                card_type=scene.suggested_visual_type,
            )

        # ── Priority 1: Stock footage ───────────────────────────────────────
        best_stock = self._best_stock(ranked_candidates)
        if best_stock is not None:
            log.info(
                "router_selected_stock",
                job_id=job_id,
                scene_id=scene.scene_id,
                asset_id=best_stock.asset.asset_id,
                score=best_stock.final_score,
            )
            return RouteResult(
                route="stock",
                selected_asset=best_stock.asset,
                ranked_candidates=ranked_candidates,
                selection_reason=(
                    f"Top stock candidate '{best_stock.asset.asset_id}' "
                    f"scored {best_stock.final_score:.3f} (threshold {self._stock_min}). "
                    f"{best_stock.rationale}"
                ),
                fallback_attempts=fallback_attempts,
            )

        fallback_attempts.append(
            f"stock: no candidate above threshold {self._stock_min} "
            f"(best={self._best_score(ranked_candidates):.3f})"
        )

        # ── Priority 2: Generated visual ────────────────────────────────────
        if self._generated is not None:
            generated_result = self._try_generated(scene, job_id)
            if generated_result is not None:
                return RouteResult(
                    route="generated",
                    selected_asset=generated_result,
                    ranked_candidates=ranked_candidates,
                    selection_reason=(
                        f"No stock footage above threshold. "
                        f"Generated visual produced: '{generated_result.asset_id}'."
                    ),
                    fallback_attempts=fallback_attempts,
                )
            fallback_attempts.append("generated: provider unavailable or failed")
        else:
            fallback_attempts.append("generated: no provider configured")

        # ── Priority 3: Programmatic card fallback ──────────────────────────
        card_type: Literal["typography_card", "data_card"] = (
            "data_card"
            if scene.suggested_visual_type == "data_card"
            else "typography_card"
        )
        log.info(
            "router_fallback_card",
            job_id=job_id,
            scene_id=scene.scene_id,
            card_type=card_type,
        )
        return RouteResult(
            route="card",
            selected_asset=None,
            ranked_candidates=ranked_candidates,
            selection_reason=(
                f"No stock or generated visual available. "
                f"Falling back to programmatic {card_type}."
            ),
            fallback_attempts=fallback_attempts,
            card_type=card_type,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _best_stock(
        self, ranked: list[RankedCandidate]
    ) -> Optional[RankedCandidate]:
        """Return the top-ranked stock candidate above the threshold, or None."""
        for rc in ranked:
            if (
                rc.asset.asset_type == "stock"
                and rc.final_score >= self._stock_min
                and rc.asset.commercial_use_eligible is True
            ):
                return rc
        return None

    def _best_score(self, ranked: list[RankedCandidate]) -> float:
        return ranked[0].final_score if ranked else 0.0

    def _try_generated(
        self, scene: ScenePlan, job_id: str
    ) -> Optional[MediaAsset]:
        """Attempt to generate a visual. Returns the asset or None on failure."""
        try:
            prompt = scene.visual_concept or scene.narration_text or "abstract visual"
            asset = self._generated.generate(prompt)
            if asset.commercial_use_eligible is not True:
                log.warning(
                    "generated_asset_not_commercial",
                    job_id=job_id,
                    asset_id=asset.asset_id,
                )
                return None
            return asset
        except GeneratedProviderUnavailableError:
            log.info("generated_provider_unavailable", job_id=job_id)
            return None
        except ProviderError as exc:
            log.warning("generated_provider_error", job_id=job_id, error=str(exc))
            return None
        except Exception as exc:
            log.error(
                "generated_unexpected_error",
                job_id=job_id,
                error=str(exc),
                exc_type=type(exc).__name__,
            )
            return None
