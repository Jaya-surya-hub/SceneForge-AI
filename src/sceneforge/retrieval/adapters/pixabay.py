"""Pixabay stock media adapter.

Uses the official Pixabay API (https://pixabay.com/api/docs/).
Requires a free API key: set PIXABAY_API_KEY in .env.

The Pixabay Content Licence permits free commercial use. Full licence:
https://pixabay.com/service/license-summary/

Feature-flagged: only used when STOCK_PROVIDER=pixabay (or pixabay is in the
provider list). The mock adapter is used in all tests without API keys.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
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

_BASE_URL = "https://pixabay.com/api/videos/"
_TIMEOUT_S = int(os.getenv("PIXABAY_TIMEOUT", "10"))
_MAX_RETRIES = int(os.getenv("PIXABAY_MAX_RETRIES", "2"))
_RETRY_DELAY = float(os.getenv("PIXABAY_RETRY_DELAY", "1.0"))

_LICENCE_NAME = "Pixabay Content Licence"
_LICENCE_URL = "https://pixabay.com/service/license-summary/"


class PixabayAdapter(StockProvider):
    """Stock footage provider backed by the Pixabay Videos API."""

    provider_name: str = "pixabay"
    is_mock: bool = False

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.getenv("PIXABAY_API_KEY", "")
        if not self._api_key:
            raise ProviderAuthError(
                "PIXABAY_API_KEY is not set. Configure it in .env to use Pixabay.",
                provider="pixabay",
                retryable=False,
            )

    def search(self, query: str, *, max_results: int = 10) -> list[MediaAsset]:
        clean_q = query.strip()[:100]
        if not clean_q:
            return []

        # Pixabay requires 3 <= per_page <= 200
        fetch_count = min(max(3, max_results), 200)
        params = urllib.parse.urlencode({
            "key": self._api_key,
            "q": clean_q,
            "per_page": fetch_count,
            "video_type": "all",
        })
        url = f"{_BASE_URL}?{params}"

        for attempt in range(_MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "SceneForgeAI/0.1 (IncuBrix-Assessment)",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
                    raw = resp.read().decode("utf-8")
                    assets = self._parse_response(raw)
                    return assets[:max_results]

            except urllib.error.HTTPError as exc:
                status = exc.code
                error_body = ""
                try:
                    error_body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    pass

                # Pixabay returns 400 with "Invalid or missing API key" on bad credentials
                if status in (401, 403) or (status == 400 and "invalid or missing api key" in error_body.lower()):
                    raise ProviderAuthError(
                        f"Pixabay API key rejected (HTTP {status}).",
                        provider="pixabay",
                        retryable=False,
                    )
                if status == 429:
                    raise ProviderRateLimitError(
                        "Pixabay rate limit exceeded.", provider="pixabay"
                    )
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY * (attempt + 1))
                    continue
                raise ProviderHTTPError(
                    f"Pixabay returned HTTP {status}.",
                    provider="pixabay",
                    status_code=status,
                )
            except TimeoutError:
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
                    continue
                raise ProviderTimeoutError(
                    f"Pixabay timed out after {_TIMEOUT_S}s.", provider="pixabay"
                )
            except OSError as exc:
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY)
                    continue
                raise ProviderHTTPError(
                    f"Pixabay network error: {exc}", provider="pixabay"
                )

        return []

    def _parse_response(self, raw: str) -> list[MediaAsset]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderMalformedResponseError(
                f"Pixabay returned non-JSON: {exc}", provider="pixabay"
            )

        hits = data.get("hits", [])
        assets = []
        for hit in hits:
            asset = self._hit_to_asset(hit)
            if asset:
                assets.append(asset)
        return assets

    def _hit_to_asset(self, hit: dict) -> Optional[MediaAsset]:
        try:
            vid_id = str(hit["id"])
            videos = hit.get("videos", {})
            # Pick best quality: large > medium > small > tiny
            best = (
                videos.get("large")
                or videos.get("medium")
                or videos.get("small")
                or videos.get("tiny")
            )
            if not best or not best.get("url"):
                return None

            tags = [t.strip() for t in hit.get("tags", "").split(",") if t.strip()]

            user = hit.get("user")
            attribution = f"Video by {user} from Pixabay" if user else ""

            # Real preview URL: use tiny or small video URL for inline preview
            tiny_url = videos.get("tiny", {}).get("url")
            small_url = videos.get("small", {}).get("url")
            preview_url = tiny_url or small_url or best.get("url", "")

            # Human-readable title from top tags
            title_text = ", ".join(t.title() for t in tags[:4]) if tags else f"Pixabay Video {vid_id}"

            return MediaAsset(
                asset_id=f"pixabay-{vid_id}",
                provider_name="pixabay",
                title=title_text,
                description=hit.get("tags", ""),
                source_url=hit.get("pageURL", ""),
                provider_asset_url=best.get("url", ""),
                preview_url=preview_url,
                duration_seconds=float(hit.get("duration", 0)) or None,
                width=best.get("width"),
                height=best.get("height"),
                licence_name=_LICENCE_NAME,
                licence_evidence_url=_LICENCE_URL,
                commercial_use_eligible=True,
                commercial_use_verified=True,
                attribution_required=False,
                attribution_text=attribution,
                asset_type="stock",
                tags=tags,
                content_type="video/mp4",
                is_mock=False,
            )
        except (KeyError, TypeError, ValueError):
            return None
