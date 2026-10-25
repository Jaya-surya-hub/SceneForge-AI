"""Unit tests for Phase 4 retrieval stack.

Covers:
  - MediaSearcher: multi-query, dedup, negative terms, provider errors, timeouts
  - CandidateRanker: scoring components, duplicate penalty, rationale
  - SourceRouter: stock→generated→card→unresolved, thresholds, card types
  - Rights passport: RightsRecord creation, SHA-256, programmatic records
  - Rights validator: commercial use, licence, unverified handling
  - Provider factory: mock defaults, feature-flag behaviour
  - Hard cases: HC-14 (stock unavailable), HC-15 (generated unavailable),
                HC-16 (both unavailable), HC-17 (duplicate assets),
                HC-24 (invalid licence)
"""

from __future__ import annotations

import hashlib
from typing import Optional
from unittest.mock import MagicMock

import pytest

from sceneforge.planner.interfaces import ScenePlan
from sceneforge.retrieval.interfaces import (
    CandidateScore,
    ComponentScores,
    GeneratedProviderUnavailableError,
    MediaAsset,
    ProviderError,
    ProviderHTTPError,
    ProviderMalformedResponseError,
    ProviderTimeoutError,
    RankedCandidate,
    RouteResult,
    StockProvider,
)
from sceneforge.retrieval.adapters.mock_embeddings import MockEmbeddingModel
from sceneforge.retrieval.adapters.mock_generated import MockGeneratedProvider
from sceneforge.retrieval.adapters.mock_stock import MockStockProvider
from sceneforge.retrieval.ranker import CandidateRanker, _jaccard_similarity
from sceneforge.retrieval.router import SourceRouter
from sceneforge.retrieval.searcher import MediaSearcher
from sceneforge.rights.passport import (
    RightsRecord,
    compute_sha256,
    create_programmatic_record,
    create_rights_record,
)
from sceneforge.rights.serialiser import rights_to_dict, validate_rights_coverage
from sceneforge.rights.validator import validate_record
from sceneforge.schemas.exceptions import LicenceVerificationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scene(
    scene_id: str = "s-001",
    visual_concept: str = "People working in a modern office",
    key_entities: Optional[list[str]] = None,
    search_queries: Optional[list[str]] = None,
    visual_type: str = "stock_footage",
    negative_terms: Optional[list[str]] = None,
    start: float = 0.0,
    end: float = 5.0,
) -> ScenePlan:
    # Use sentinel to distinguish "not passed" from "passed as empty list"
    _sq = ["office team", "modern workplace"] if search_queries is None else search_queries
    _ne = [] if negative_terms is None else negative_terms
    _ke = ["office", "people", "work"] if key_entities is None else key_entities
    return ScenePlan(
        scene_id=scene_id,
        narration_text="Test narration.",
        start_time=start,
        end_time=end,
        key_entities=_ke,
        intended_meaning="Professional work environment",
        visual_concept=visual_concept,
        search_queries=_sq,
        suggested_visual_type=visual_type,
        negative_terms=_ne,
        safety_constraints=[],
        confidence=0.8,
        preferred_source_route="stock",
        caption_text="Test narration.",
    )


def _asset(
    asset_id: str = "asset-001",
    commercial: Optional[bool] = True,
    licence: str = "Mock-CC0",
    duration: Optional[float] = 8.0,
    width: int = 1920,
    height: int = 1080,
    tags: Optional[list[str]] = None,
    description: str = "Office professionals working together",
) -> MediaAsset:
    return MediaAsset(
        asset_id=asset_id,
        provider_name="mock_stock",
        title="Office team meeting",
        description=description,
        source_url=f"https://mock.example/{asset_id}",
        provider_asset_url=f"https://mock.example/{asset_id}/download",
        preview_url=f"https://mock.example/{asset_id}/preview.jpg",
        duration_seconds=duration,
        width=width,
        height=height,
        licence_name=licence,
        licence_evidence_url="https://mock.example/licence",
        commercial_use_eligible=commercial,
        attribution_required=False,
        attribution_text="",
        asset_type="stock",
        tags=tags or ["office", "people", "work", "professional"],
        is_mock=True,
    )


# ---------------------------------------------------------------------------
# MediaSearcher
# ---------------------------------------------------------------------------

class TestMediaSearcher:
    def test_returns_candidates_from_mock(self):
        searcher = MediaSearcher([MockStockProvider()])
        scene = _scene(search_queries=["office team"])
        results = searcher.search_for_scene(scene)
        assert len(results) > 0

    def test_deduplicates_asset_ids(self):
        # Two providers returning the same asset IDs
        searcher = MediaSearcher([MockStockProvider(), MockStockProvider()])
        scene = _scene(search_queries=["office"])
        results = searcher.search_for_scene(scene)
        ids = [r.asset_id for r in results]
        assert len(ids) == len(set(ids))

    def test_empty_search_queries_returns_empty(self):
        searcher = MediaSearcher([MockStockProvider()])
        scene = _scene(search_queries=[])
        results = searcher.search_for_scene(scene)
        assert results == []

    def test_negative_terms_filter_assets(self):
        """Assets containing negative terms must be excluded."""
        searcher = MediaSearcher([MockStockProvider()])
        # "city" appears in mock-stock-001 title/description/tags
        scene = _scene(search_queries=["any"], negative_terms=["city"])
        results = searcher.search_for_scene(scene)
        for asset in results:
            text = f"{asset.title} {asset.description} {' '.join(asset.tags)}".lower()
            assert "city" not in text

    def test_excludes_non_commercial_assets(self):
        """Assets with commercial_use_eligible=False must be excluded."""
        class NonCommercialProvider(StockProvider):
            provider_name = "noncommercial"
            def search(self, query, *, max_results=10):
                return [_asset(commercial=False)]

        searcher = MediaSearcher(
            [NonCommercialProvider()],
            require_commercial_licence=True,
        )
        scene = _scene(search_queries=["test"])
        results = searcher.search_for_scene(scene)
        assert results == []

    def test_allows_unverified_when_configured(self):
        """Assets with commercial_use_eligible=None allowed if allow_unverified=True."""
        class UnverifiedProvider(StockProvider):
            provider_name = "unverified"
            def search(self, query, *, max_results=10):
                return [_asset(commercial=None)]

        searcher = MediaSearcher(
            [UnverifiedProvider()],
            require_commercial_licence=False,
            allow_unverified=True,
        )
        scene = _scene(search_queries=["test"])
        results = searcher.search_for_scene(scene)
        assert len(results) == 1

    def test_excludes_assets_with_unknown_licence(self):
        """Assets with empty licence_name must be excluded."""
        class BadLicenceProvider(StockProvider):
            provider_name = "badlicence"
            def search(self, query, *, max_results=10):
                return [_asset(licence="")]

        searcher = MediaSearcher([BadLicenceProvider()])
        scene = _scene(search_queries=["test"])
        results = searcher.search_for_scene(scene)
        assert results == []

    # HC-14: Stock provider unavailable (timeout)
    def test_provider_timeout_returns_empty_not_crash(self):
        """HC-14: Provider timeout must not crash the search."""
        class TimeoutProvider(StockProvider):
            provider_name = "timeout_provider"
            def search(self, query, *, max_results=10):
                raise ProviderTimeoutError("Simulated timeout", provider="timeout_provider")

        searcher = MediaSearcher([TimeoutProvider()])
        scene = _scene(search_queries=["test"])
        results = searcher.search_for_scene(scene)
        assert results == []

    def test_provider_http_error_returns_empty_not_crash(self):
        """Provider HTTP error must not crash; other providers continue."""
        class ErrorProvider(StockProvider):
            provider_name = "error_provider"
            def search(self, query, *, max_results=10):
                raise ProviderHTTPError("500 error", provider="error_provider", status_code=500)

        searcher = MediaSearcher([ErrorProvider(), MockStockProvider()])
        scene = _scene(search_queries=["office"])
        results = searcher.search_for_scene(scene)
        # MockStockProvider results should still come through
        assert len(results) > 0

    def test_malformed_response_does_not_crash(self):
        """Provider returning garbage must be caught and logged."""
        class MalformedProvider(StockProvider):
            provider_name = "malformed"
            def search(self, query, *, max_results=10):
                raise ProviderMalformedResponseError("Bad JSON", provider="malformed")

        searcher = MediaSearcher([MalformedProvider()])
        scene = _scene(search_queries=["test"])
        results = searcher.search_for_scene(scene)
        assert results == []

    def test_requires_at_least_one_provider(self):
        with pytest.raises(ValueError):
            MediaSearcher([])


# ---------------------------------------------------------------------------
# CandidateRanker
# ---------------------------------------------------------------------------

class TestCandidateRanker:
    def test_returns_ranked_candidates(self):
        ranker = CandidateRanker()
        scene = _scene()
        assets = [_asset("a-001"), _asset("a-002")]
        ranked = ranker.rank(scene, assets)
        assert len(ranked) == 2
        assert all(isinstance(r, RankedCandidate) for r in ranked)

    def test_sorted_descending_by_score(self):
        ranker = CandidateRanker()
        scene = _scene()
        assets = [_asset(f"a-{i:03d}") for i in range(5)]
        ranked = ranker.rank(scene, assets)
        scores = [r.final_score for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_scores_in_valid_range(self):
        ranker = CandidateRanker()
        scene = _scene()
        ranked = ranker.rank(scene, [_asset()])
        for r in ranked:
            assert 0.0 <= r.final_score <= 1.0

    def test_rank_field_assigned(self):
        ranker = CandidateRanker()
        ranked = ranker.rank(_scene(), [_asset("a-001"), _asset("a-002")])
        assert ranked[0].rank == 1
        assert ranked[1].rank == 2

    def test_empty_candidates_returns_empty(self):
        ranker = CandidateRanker()
        assert ranker.rank(_scene(), []) == []

    def test_rationale_is_non_empty_string(self):
        ranker = CandidateRanker()
        ranked = ranker.rank(_scene(), [_asset()])
        assert isinstance(ranked[0].rationale, str)
        assert len(ranked[0].rationale) > 10

    def test_rationale_mentions_asset_id(self):
        ranker = CandidateRanker()
        ranked = ranker.rank(_scene(), [_asset("unique-id-xyz")])
        assert "unique-id-xyz" in ranked[0].rationale

    # HC-17: Duplicate asset penalty
    def test_duplicate_penalty_applied(self):
        """HC-17: Already-seen asset must score lower."""
        seen = {"asset-dup"}
        ranker_with = CandidateRanker(seen_asset_ids=seen)
        ranker_without = CandidateRanker(seen_asset_ids=set())
        scene = _scene()
        asset = _asset("asset-dup")
        score_with = ranker_with.rank(scene, [asset])[0].final_score
        score_without = ranker_without.rank(scene, [asset])[0].final_score
        assert score_with < score_without

    def test_duplicate_penalty_in_components(self):
        """Components must record the duplicate penalty explicitly."""
        seen = {"dup-asset"}
        ranker = CandidateRanker(seen_asset_ids=seen)
        ranked = ranker.rank(_scene(), [_asset("dup-asset")])
        assert ranked[0].components.duplicate_penalty > 0

    def test_with_embedding_model(self):
        """Ranker works with mock embedding model."""
        ranker = CandidateRanker(embedding_model=MockEmbeddingModel())
        ranked = ranker.rank(_scene(), [_asset()])
        assert ranked[0].components.embedding_used is True
        assert ranked[0].components.text_similarity is not None

    def test_without_embedding_uses_lexical(self):
        """Without embedding model, text_similarity uses lexical Jaccard."""
        ranker = CandidateRanker(embedding_model=None)
        ranked = ranker.rank(_scene(), [_asset()])
        assert ranked[0].components.embedding_used is False

    def test_duration_fit_penalises_mismatch(self):
        """Asset with very different duration gets lower duration_fit."""
        ranker = CandidateRanker()
        scene = _scene(start=0.0, end=5.0)           # 5s scene
        asset_close = _asset("close", duration=5.0)  # perfect
        asset_far = _asset("far", duration=60.0)     # 12× too long
        r_close = ranker.rank(scene, [asset_close])[0]
        r_far = ranker.rank(scene, [asset_far])[0]
        assert r_close.components.duration_fit > r_far.components.duration_fit

    def test_still_image_duration_fit_is_none(self):
        """Still images (duration=None) have no duration_fit score."""
        ranker = CandidateRanker()
        asset = _asset(duration=None)
        ranked = ranker.rank(_scene(), [asset])
        assert ranked[0].components.duration_fit is None

    def test_low_resolution_penalised(self):
        """Low-resolution asset scores lower on resolution_fit."""
        ranker = CandidateRanker()
        scene = _scene()
        hd = _asset("hd", height=1080)
        sd = _asset("sd", height=240)
        r_hd = ranker.rank(scene, [hd])[0]
        r_sd = ranker.rank(scene, [sd])[0]
        assert r_hd.components.resolution_fit > r_sd.components.resolution_fit


class TestJaccardSimilarity:
    def test_identical_texts(self):
        assert _jaccard_similarity("hello world", "hello world") == 1.0

    def test_no_overlap(self):
        assert _jaccard_similarity("apple orange", "car truck") == 0.0

    def test_partial_overlap(self):
        s = _jaccard_similarity("office team collaboration", "team meeting")
        assert 0.0 < s < 1.0

    def test_empty_texts(self):
        assert _jaccard_similarity("", "") == 0.0

    def test_result_in_range(self):
        s = _jaccard_similarity("some text here", "other words there")
        assert 0.0 <= s <= 1.0


# ---------------------------------------------------------------------------
# SourceRouter
# ---------------------------------------------------------------------------

class TestSourceRouter:
    def _ranked(self, score: float = 0.70, asset_id: str = "a-001") -> list[RankedCandidate]:
        return [RankedCandidate(
            asset=_asset(asset_id),
            final_score=score,
            components=ComponentScores(
                text_similarity=score, tag_overlap=None,
                duration_fit=None, resolution_fit=None, aspect_ratio_fit=None,
            ),
            rationale="Test rationale.",
        )]

    def test_stock_selected_above_threshold(self):
        router = SourceRouter(stock_min_relevance=0.62)
        result = router.route(_scene(), self._ranked(0.70))
        assert result.route == "stock"
        assert result.selected_asset is not None

    def test_stock_not_selected_below_threshold(self):
        router = SourceRouter(stock_min_relevance=0.62, generated_provider=None)
        result = router.route(_scene(), self._ranked(0.40))
        # Falls through to card (no generated provider)
        assert result.route in ("card", "unresolved")

    def test_card_scenes_route_directly(self):
        router = SourceRouter()
        for vtype in ("typography_card", "data_card"):
            scene = _scene(visual_type=vtype)
            result = router.route(scene, [])
            assert result.route == "card"
            assert result.card_type == vtype

    def test_fallback_to_card_when_no_stock_no_generated(self):
        """HC-16: Both providers unavailable → card fallback."""
        router = SourceRouter(generated_provider=None, stock_min_relevance=0.99)
        result = router.route(_scene(), self._ranked(0.10))
        assert result.route == "card"

    def test_fallback_attempts_recorded(self):
        """Router must record every tried route."""
        router = SourceRouter(generated_provider=None, stock_min_relevance=0.99)
        result = router.route(_scene(), self._ranked(0.10))
        assert len(result.fallback_attempts) >= 1
        assert any("stock" in a.lower() for a in result.fallback_attempts)

    # HC-14: Stock provider unavailable
    def test_empty_candidates_no_stock_falls_back(self):
        """HC-14: No candidates → no stock → card fallback."""
        router = SourceRouter(generated_provider=None)
        result = router.route(_scene(), [])
        assert result.route == "card"

    # HC-15: Generated provider unavailable
    def test_generated_provider_unavailable_falls_to_card(self):
        """HC-15: GeneratedProviderUnavailableError → card fallback."""
        class UnavailableGenerated(MockGeneratedProvider):
            def generate(self, prompt):
                raise GeneratedProviderUnavailableError("Not configured.")

        router = SourceRouter(
            generated_provider=UnavailableGenerated(),
            stock_min_relevance=0.99,
        )
        result = router.route(_scene(), self._ranked(0.10))
        assert result.route == "card"
        assert any("generated" in a.lower() for a in result.fallback_attempts)

    def test_generated_provider_error_falls_to_card(self):
        """Generic provider error on generation → card fallback."""
        class ErrorGenerated(MockGeneratedProvider):
            def generate(self, prompt):
                raise ProviderError("Server error.")

        router = SourceRouter(
            generated_provider=ErrorGenerated(),
            stock_min_relevance=0.99,
        )
        result = router.route(_scene(), self._ranked(0.10))
        assert result.route == "card"

    def test_selection_reason_present(self):
        router = SourceRouter(stock_min_relevance=0.62)
        result = router.route(_scene(), self._ranked(0.70))
        assert isinstance(result.selection_reason, str)
        assert len(result.selection_reason) > 5

    def test_non_commercial_asset_not_selected(self):
        """Router must not select an asset with commercial_use_eligible=False."""
        ranked = [RankedCandidate(
            asset=_asset("nc-001", commercial=False),
            final_score=0.90,
            components=ComponentScores(
                text_similarity=0.9, tag_overlap=None,
                duration_fit=None, resolution_fit=None, aspect_ratio_fit=None,
            ),
            rationale="High score but non-commercial.",
        )]
        router = SourceRouter(stock_min_relevance=0.62, generated_provider=None)
        result = router.route(_scene(), ranked)
        # Non-commercial asset must not be selected as stock
        assert result.route != "stock" or (
            result.selected_asset and result.selected_asset.asset_id != "nc-001"
        )


# ---------------------------------------------------------------------------
# Rights passport
# ---------------------------------------------------------------------------

class TestRightsPassport:
    def test_create_rights_record_basic(self):
        asset = _asset()
        record = create_rights_record(asset=asset, job_id="job-001")
        assert record.asset_id == asset.asset_id
        assert record.provider_name == asset.provider_name
        assert record.licence_name == asset.licence_name
        assert record.commercial_use_eligible is True
        assert record.job_id == "job-001"

    def test_sha256_computed_when_bytes_provided(self):
        asset = _asset()
        data = b"fake video bytes for testing"
        record = create_rights_record(asset=asset, job_id="j-001", asset_bytes=data)
        expected = hashlib.sha256(data).hexdigest()
        assert record.sha256_hash == expected

    def test_sha256_none_when_no_bytes(self):
        record = create_rights_record(asset=_asset(), job_id="j-001")
        assert record.sha256_hash is None

    def test_sha256_is_identity_not_licence_proof(self):
        """SHA-256 identifies file contents — the record must not claim licence."""
        record = create_rights_record(asset=_asset(), job_id="j-001", asset_bytes=b"data")
        # sha256_hash field exists but licence fields are separate
        assert record.licence_name != record.sha256_hash
        assert record.licence_evidence_url != ""

    def test_record_id_is_unique(self):
        asset = _asset()
        r1 = create_rights_record(asset=asset, job_id="j-001")
        r2 = create_rights_record(asset=asset, job_id="j-001")
        assert r1.record_id != r2.record_id

    def test_scene_id_recorded(self):
        record = create_rights_record(
            asset=_asset(), job_id="j-001", scene_id="scene-001"
        )
        assert record.scene_id == "scene-001"

    def test_review_flags_for_unknown_licence(self):
        """Assets with unknown commercial eligibility get a review flag."""
        asset = _asset(commercial=None)
        record = create_rights_record(asset=asset, job_id="j-001")
        assert any("COMMERCIAL_USE_UNKNOWN" in f for f in record.review_flags)

    def test_review_flags_for_missing_licence_name(self):
        asset = _asset(licence="")
        record = create_rights_record(asset=asset, job_id="j-001")
        assert any("LICENCE" in f for f in record.review_flags)

    def test_programmatic_record_commercial_true(self):
        record = create_programmatic_record(
            card_type="typography_card", job_id="j-001"
        )
        assert record.commercial_use_eligible is True
        assert record.asset_type == "programmatic"
        assert record.attribution_required is False

    def test_compute_sha256(self):
        data = b"hello world"
        h = compute_sha256(data)
        assert h == hashlib.sha256(b"hello world").hexdigest()
        assert len(h) == 64

    def test_to_dict_has_required_keys(self):
        record = create_rights_record(asset=_asset(), job_id="j-001")
        d = record.to_dict()
        for key in (
            "record_id", "asset_id", "provider_name", "licence_name",
            "commercial_use_eligible", "sha256_hash", "retrieval_timestamp",
            "job_id",
        ):
            assert key in d, f"Missing key: {key}"

    def test_is_commercially_cleared_true(self):
        record = create_rights_record(asset=_asset(commercial=True), job_id="j")
        assert record.is_commercially_cleared is True

    def test_is_commercially_cleared_false_for_none(self):
        """Unknown eligibility must NOT be treated as cleared."""
        record = create_rights_record(asset=_asset(commercial=None), job_id="j")
        assert record.is_commercially_cleared is False


# ---------------------------------------------------------------------------
# Rights validator
# ---------------------------------------------------------------------------

class TestRightsValidator:
    def _record(self, **kwargs) -> RightsRecord:
        """Build a valid record and override fields via kwargs."""
        asset = _asset(**{
            k: v for k, v in kwargs.items()
            if k in ("commercial", "licence")
        })
        r = create_rights_record(asset=asset, job_id="j-001")
        for k, v in kwargs.items():
            if hasattr(r, k):
                object.__setattr__(r, k, v)
        return r

    def test_valid_record_no_errors(self):
        record = create_rights_record(asset=_asset(), job_id="j-001")
        warnings = validate_record(record, require_verified=True, allow_unverified=False)
        assert warnings == []

    # HC-24: Invalid/missing licence
    def test_missing_licence_raises_when_required(self):
        """HC-24: Missing licence with require_verified=True → LicenceVerificationError."""
        asset = _asset(licence="")
        record = create_rights_record(asset=asset, job_id="j-001")
        with pytest.raises(LicenceVerificationError):
            validate_record(record, require_verified=True, allow_unverified=False)

    def test_non_commercial_always_raises(self):
        """Commercial-use-eligible=False must always raise regardless of policy."""
        asset = _asset(commercial=False)
        record = create_rights_record(asset=asset, job_id="j-001")
        with pytest.raises(LicenceVerificationError):
            validate_record(record, require_verified=False, allow_unverified=True)

    def test_unknown_commercial_raises_when_strict(self):
        """Unknown commercial eligibility raises when require_verified=True."""
        asset = _asset(commercial=None)
        record = create_rights_record(asset=asset, job_id="j-001")
        with pytest.raises(LicenceVerificationError):
            validate_record(record, require_verified=True, allow_unverified=False)

    def test_unknown_commercial_warns_when_permissive(self):
        """Unknown eligibility produces a warning (not exception) when allowed."""
        asset = _asset(commercial=None)
        record = create_rights_record(asset=asset, job_id="j-001")
        # Patch licence_name to avoid that check triggering first
        record = RightsRecord(
            **{**record.to_dict(),
               "licence_name": "ValidLicence",
               "commercial_use_eligible": None,
               "commercial_use_verified": None,
               "restrictions": [],
               "review_flags": [],
               "record_id": record.record_id,
               "retrieval_timestamp": record.retrieval_timestamp,
               "asset_type": record.asset_type,
               "model_provenance": record.model_provenance}
        )
        warnings = validate_record(record, require_verified=False, allow_unverified=True)
        assert any("COMMERCIAL_USE_UNKNOWN" in w for w in warnings)

    def test_programmatic_record_always_valid(self):
        """Programmatic cards always pass validation."""
        record = create_programmatic_record(card_type="typography_card", job_id="j-001")
        warnings = validate_record(record, require_verified=True, allow_unverified=False)
        assert warnings == []


# ---------------------------------------------------------------------------
# Rights serialiser
# ---------------------------------------------------------------------------

class TestRightsSerialiser:
    def test_rights_to_dict_has_job_id(self):
        records = [create_rights_record(asset=_asset(), job_id="j-xyz")]
        d = rights_to_dict(records, job_id="j-xyz")
        assert d["job_id"] == "j-xyz"
        assert d["record_count"] == 1

    def test_rights_to_dict_has_records(self):
        records = [create_rights_record(asset=_asset(f"a-{i}"), job_id="j-001")
                   for i in range(3)]
        d = rights_to_dict(records, job_id="j-001")
        assert len(d["records"]) == 3

    def test_coverage_check_passes_when_all_scenes_covered(self):
        scene_ids = ["s-001", "s-002"]
        records = [
            create_rights_record(asset=_asset(), job_id="j", scene_id="s-001"),
            create_rights_record(asset=_asset("a-002"), job_id="j", scene_id="s-002"),
        ]
        errors = validate_rights_coverage(records, scene_ids)
        assert errors == []

    def test_coverage_check_fails_when_scene_missing(self):
        records = [create_rights_record(asset=_asset(), job_id="j", scene_id="s-001")]
        errors = validate_rights_coverage(records, ["s-001", "s-002"])
        assert len(errors) == 1
        assert "s-002" in errors[0]


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

class TestProviderFactory:
    def test_default_stock_is_mock(self, monkeypatch):
        monkeypatch.setenv("STOCK_PROVIDER", "mock")
        from sceneforge.retrieval.factory import get_stock_providers
        providers = get_stock_providers()
        assert len(providers) == 1
        assert providers[0].is_mock is True

    def test_pexels_without_key_falls_back_to_mock(self, monkeypatch):
        monkeypatch.setenv("PEXELS_API_KEY", "")
        from sceneforge.retrieval.factory import get_stock_providers
        providers = get_stock_providers(override="pexels")
        assert all(p.is_mock for p in providers)

    def test_pixabay_without_key_falls_back_to_mock(self, monkeypatch):
        monkeypatch.setenv("PIXABAY_API_KEY", "")
        from sceneforge.retrieval.factory import get_stock_providers
        providers = get_stock_providers(override="pixabay")
        assert all(p.is_mock for p in providers)

    def test_generated_provider_none_by_default(self, monkeypatch):
        monkeypatch.setenv("GENERATED_PROVIDER", "none")
        from sceneforge.retrieval.factory import get_generated_provider
        assert get_generated_provider() is None

    def test_generated_provider_mock_when_requested(self):
        from sceneforge.retrieval.factory import get_generated_provider
        provider = get_generated_provider(override="mock")
        assert provider is not None
        assert provider.is_mock is True

    def test_embedding_model_mock_by_default(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL", "mock")
        from sceneforge.retrieval.factory import get_embedding_model
        model = get_embedding_model()
        assert model is not None
        assert model.is_mock is True

    def test_embedding_model_none_when_configured(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL", "none")
        from sceneforge.retrieval.factory import get_embedding_model
        model = get_embedding_model()
        assert model is None

    def test_generated_provider_not_operational_without_real_key(self):
        """
        IMPORTANT: No production generative video provider is implemented.
        The mock is the only available implementation.
        This test asserts that fact explicitly.
        """
        from sceneforge.retrieval.factory import get_generated_provider
        # With override="mock", returns mock — is_mock must be True
        provider = get_generated_provider(override="mock")
        assert provider.is_mock is True, (
            "Generative provider is mock only — no real provider is implemented."
        )
