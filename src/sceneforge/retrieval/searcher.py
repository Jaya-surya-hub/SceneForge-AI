"""Multi-query media searcher.

Runs multiple search queries against a list of stock providers,
deduplicates results by asset_id, validates metadata, and returns
a consolidated candidate list.

Design notes:
- Each query is tried against each provider; results are merged.
- Failed queries are logged but do not abort the search.
- Providers that time out or error are recorded in SearchResult.error.
- Asset metadata is validated before inclusion (no unverified commercial use
  when require_commercial_licence=True).
- Duplicate asset IDs are suppressed (first occurrence wins).
"""

from __future__ import annotations

import os
from typing import Optional

from sceneforge.observability.logging import get_logger
from sceneforge.planner.interfaces import ScenePlan
from sceneforge.retrieval.interfaces import (
    MediaAsset,
    ProviderError,
    ProviderTimeoutError,
    SearchResult,
    StockProvider,
)

log = get_logger(__name__)

_MAX_RESULTS_PER_QUERY = int(os.getenv("RETRIEVAL_MAX_RESULTS_PER_QUERY", "10"))
_REQUIRE_COMMERCIAL = os.getenv("ROUTER_REQUIRE_VERIFIED_LICENCE", "true").lower() == "true"
_ALLOW_UNVERIFIED = os.getenv("ROUTER_ALLOW_UNVERIFIED_MEDIA", "false").lower() == "true"


class MediaSearcher:
    """Run multi-query search across a list of stock providers.

    Args:
        providers: One or more StockProvider instances.
        require_commercial_licence: Exclude assets where commercial_use_eligible is False.
        allow_unverified: Include assets where commercial_use_eligible is None/unverified.
    """

    def __init__(
        self,
        providers: list[StockProvider],
        *,
        require_commercial_licence: bool = _REQUIRE_COMMERCIAL,
        allow_unverified: bool = _ALLOW_UNVERIFIED,
        max_results_per_query: int = _MAX_RESULTS_PER_QUERY,
    ) -> None:
        if not providers:
            raise ValueError("At least one provider must be supplied.")
        self._providers = providers
        self._require_commercial = require_commercial_licence
        self._allow_unverified = allow_unverified
        self._max_results = max_results_per_query

    def search_for_scene(
        self,
        scene: ScenePlan,
        *,
        job_id: str = "unknown",
    ) -> list[MediaAsset]:
        """Search all providers with all queries from *scene.search_queries*.

        Args:
            scene:   ScenePlan containing search_queries and negative_terms.
            job_id:  For logging.

        Returns:
            Deduplicated, validated list of MediaAsset candidates.
            May be empty if all queries fail or return no usable assets.
        """
        queries = scene.search_queries or []
        if not queries:
            log.info("searcher_no_queries", job_id=job_id, scene_id=scene.scene_id)
            return []

        seen_ids: set[str] = set()
        candidates: list[MediaAsset] = []
        search_results: list[SearchResult] = []

        for query in queries:
            for provider in self._providers:
                result = self._search_one(provider, query, job_id)
                search_results.append(result)
                for asset in result.assets:
                    if asset.asset_id in seen_ids:
                        continue
                    if not self._passes_licence_filter(asset):
                        log.debug(
                            "asset_excluded_licence",
                            asset_id=asset.asset_id,
                            commercial=asset.commercial_use_eligible,
                        )
                        continue
                    if not self._passes_metadata_check(asset):
                        continue
                    seen_ids.add(asset.asset_id)
                    candidates.append(asset)

        # Apply negative term filter
        if scene.negative_terms:
            candidates = self._filter_negative_terms(candidates, scene.negative_terms)

        # Retry with broader query if no candidates found
        if not candidates and queries:
            broader_candidates = []
            for q in queries:
                tokens = q.split()
                if len(tokens) > 1:
                    broader_candidates.append(tokens[0])
            if scene.key_entities:
                broader_candidates.extend(scene.key_entities[:2])

            broader_unique = [b for b in set(broader_candidates) if b and b not in queries]
            if broader_unique:
                log.info(
                    "searcher_retry_broader",
                    job_id=job_id,
                    scene_id=scene.scene_id,
                    broader_queries=broader_unique,
                )
                for b_query in broader_unique:
                    for provider in self._providers:
                        res = self._search_one(provider, b_query, job_id)
                        for asset in res.assets:
                            if asset.asset_id in seen_ids:
                                continue
                            if not self._passes_licence_filter(asset) or not self._passes_metadata_check(asset):
                                continue
                            seen_ids.add(asset.asset_id)
                            candidates.append(asset)
                if scene.negative_terms and candidates:
                    candidates = self._filter_negative_terms(candidates, scene.negative_terms)

        log.info(
            "searcher_done",
            job_id=job_id,
            scene_id=scene.scene_id,
            queries=len(queries),
            providers=len(self._providers),
            candidates=len(candidates),
        )
        return candidates

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _search_one(
        self, provider: StockProvider, query: str, job_id: str
    ) -> SearchResult:
        """Run one query against one provider; catch and record errors."""
        try:
            assets = provider.search(query, max_results=self._max_results)
            return SearchResult(
                provider_name=provider.provider_name,
                query=query,
                assets=assets,
                is_mock=provider.is_mock,
            )
        except ProviderTimeoutError as exc:
            log.warning(
                "provider_timeout",
                job_id=job_id,
                provider=provider.provider_name,
                query=query,
                error=str(exc),
            )
            return SearchResult(
                provider_name=provider.provider_name,
                query=query,
                assets=[],
                error=str(exc),
                timed_out=True,
            )
        except ProviderError as exc:
            log.warning(
                "provider_error",
                job_id=job_id,
                provider=provider.provider_name,
                query=query,
                error=str(exc),
            )
            return SearchResult(
                provider_name=provider.provider_name,
                query=query,
                assets=[],
                error=str(exc),
            )
        except Exception as exc:
            log.error(
                "provider_unexpected_error",
                job_id=job_id,
                provider=provider.provider_name,
                query=query,
                exc_type=type(exc).__name__,
                error=str(exc),
            )
            return SearchResult(
                provider_name=provider.provider_name,
                query=query,
                assets=[],
                error=f"Unexpected error: {exc}",
            )

    def _passes_licence_filter(self, asset: MediaAsset) -> bool:
        """Return True if the asset's licence passes the configured policy."""
        if asset.commercial_use_eligible is True:
            return True
        if asset.commercial_use_eligible is False:
            # Definitely not commercial — always exclude
            return False
        # None = unknown/unverified
        return self._allow_unverified

    def _passes_metadata_check(self, asset: MediaAsset) -> bool:
        """Return True if the asset has the minimum required metadata."""
        if not asset.asset_id:
            return False
        if not asset.source_url:
            return False
        if not asset.licence_name or asset.licence_name.lower() in ("", "unknown"):
            return False
        return True

    def _filter_negative_terms(
        self, assets: list[MediaAsset], negative_terms: list[str]
    ) -> list[MediaAsset]:
        """Remove assets whose title/description/tags contain negative terms."""
        neg_lower = {t.lower() for t in negative_terms}
        filtered = []
        for asset in assets:
            text = (
                asset.title.lower()
                + " "
                + asset.description.lower()
                + " "
                + " ".join(asset.tags).lower()
            )
            if any(term in text for term in neg_lower):
                log.debug(
                    "asset_excluded_negative_term",
                    asset_id=asset.asset_id,
                    negative_terms=negative_terms,
                )
                continue
            filtered.append(asset)
        return filtered
