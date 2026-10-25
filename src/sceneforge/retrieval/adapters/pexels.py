"""Pexels stock footage adapter.

Uses the official Pexels API (https://www.pexels.com/api/).
Requires a free API key: set PEXELS_API_KEY in .env.

The Pexels Licence permits free commercial use. Attribution is not required
but is encouraged. Full licence: https://www.pexels.com/license/

Feature-flagged: only used when STOCK_PROVIDER=pexels (or pexels is in the
provider list). The mock adapter is used in all tests without API keys.
"""

from __future__ import annotations

import os
import time
import urllib.parse
import urllib.request
import urllib.error
import json
from typing import Optional

from sceneforge.observability.logging import get_logger
from sceneforge.retrieval.interfaces import (
    MediaAsset,
    ProviderAuthError,
    ProviderHTTPError,
    ProviderMalformedResponseError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    StockProvider,
)

log = get_logger(__name__)

_BASE_URL = "https://api.pexels.com/videos/search"
_TIMEOUT_S = int(os.getenv("PEXELS_TIMEOUT", "10"))
_MAX_RETRIES = int(os.getenv("PEXELS_MAX_RETRIES", "2"))
_RETRY_DELAY = float(os.getenv("PEXELS_RETRY_DELAY", "1.0"))

# Pexels licence information (constant — applies to all assets)
_LICENCE_NAME = "Pexels Licence"
_LICENCE_URL = "https://www.pexels.com/license/"


class PexelsAdapter(StockProvider):
    """Stock footage provider backed by the Pexels Videos API.

    Requires PEXELS_API_KEY to be set. Returns 0 results (not an error)
    when no videos match; raises ProviderError on auth/network failures.
    """

    provider_name: str = "pexels"
    is_mock: bool = False

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.getenv("PEXELS_API_KEY", "")
        if not self._api_key:
            raise ProviderAuthError(
                "PEXELS_API_KEY is not set. Configure it in .env to use Pexels.",
                provider="pexels",
                retryable=False,
            )

    def search(self, query: str, *, max_results: int = 10) -> list[MediaAsset]:
        """Search Pexels Videos API and return formatted MediaAsset list.

        Args:
            query:       Search string.
            max_results: Maximum assets to return (capped at 40 by Pexels API).

        Returns:
            List of MediaAsset objects.

        Raises:
            ProviderAuthError:            API key rejected.
            ProviderRateLimitError:       Rate limit exceeded.
            ProviderHTTPError:            Other HTTP error.
            ProviderTimeoutError:         Request timed out.
            ProviderMalformedResponseError: Could not parse response.
        """
        params = urllib.parse.urlencode({
            "query": query,
            "per_page": min(max_results, 40),
            "orientation": "landscape",
        })
        url = f"{_BASE_URL}?{params}"

        for attempt in range(_MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "Authorization": self._api_key,
                        "User-Agent": "SceneForgeAI/0.1",
                    },
                )
                with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
                    raw = resp.read().decode("utf-8")
                    return self._parse_response(raw, query)

            except urllib.error.HTTPError as exc:
                status = exc.code
                if status == 401 or status == 403:
                    raise ProviderAuthError(
                        f"Pexels API key rejected (HTTP {status}).",
                        provider="pexels",
                        retryable=False,
                    )
                if status == 429:
                    raise ProviderRateLimitError(
                        "Pexels rate limit exceeded.", provider="pexels"
                    )
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY * (attempt + 1))
                    continue
                raise ProviderHTTPError(
                    f"Pexels returned HTTP {status}.",
                    provider="pexels",
                    status_code=status,
                )
            except TimeoutError:
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
                    continue
                raise ProviderTimeoutError(
                    f"Pexels timed out after {_TIMEOUT_S}s.", provider="pexels"
                )
            except OSError as exc:
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
                    continue
                raise ProviderHTTPError(
                    f"Pexels network error: {exc}",
                    provider="pexels",
                    retryable=True,
                )

        return []  # unreachable but satisfies type checker

    def _parse_response(self, raw: str, query: str) -> list[MediaAsset]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderMalformedResponseError(
                f"Pexels returned non-JSON response: {exc}", provider="pexels"
            )

        videos = data.get("videos", [])
        assets = []
        for v in videos:
            asset = self._video_to_asset(v)
            if asset:
                assets.append(asset)
        return assets

    def _video_to_asset(self, v: dict) -> Optional[MediaAsset]:
        try:
            video_id = str(v["id"])
            # Find best video file (prefer HD)
            files = v.get("video_files", [])
            best_file = self._best_video_file(files)
            if not best_file:
                return None

            author = v.get("user", {})
            attribution = (
                f"Video by {author.get('name', 'Unknown')} from Pexels"
            )

            return MediaAsset(
                asset_id=f"pexels-{video_id}",
                provider_name="pexels",
                title=v.get("title") or f"Pexels video {video_id}",
                description=v.get("title") or "",
                source_url=v.get("url", ""),
                provider_asset_url=best_file.get("link", ""),
                preview_url=v.get("image", ""),
                duration_seconds=float(v.get("duration", 0)) or None,
                width=best_file.get("width"),
                height=best_file.get("height"),
                licence_name=_LICENCE_NAME,
                licence_evidence_url=_LICENCE_URL,
                commercial_use_eligible=True,
                commercial_use_verified=True,
                attribution_required=False,
                attribution_text=attribution,
                asset_type="stock",
                tags=[tag.get("title", "") for tag in v.get("tags", [])],
                content_type=best_file.get("file_type", "video/mp4"),
            )
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _best_video_file(files: list[dict]) -> Optional[dict]:
        """Pick the best quality video file, preferring HD."""
        hd = [f for f in files if f.get("quality") == "hd"]
        if hd:
            return hd[0]
        sd = [f for f in files if f.get("quality") == "sd"]
        if sd:
            return sd[0]
        return files[0] if files else None
