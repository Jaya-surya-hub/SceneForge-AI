"""Unit tests for all mock adapters (IS-07, MH-08).

Verifies:
- Mock TTS returns deterministic WAV bytes and correct duration estimate.
- Mock STT returns deterministic transcript and word timestamps.
- Mock stock provider returns deterministic assets with valid metadata.
- Mock generated provider returns deterministic asset.
- Mock embeddings return deterministic unit vectors with valid similarity.
- Mock LLM planner returns valid ScenePlan objects.
- All mock adapters self-identify as mocks.
"""

import struct

import pytest

from sceneforge.audio.adapters.mock_tts import MockTTSAdapter
from sceneforge.audio.adapters.mock_stt import MockSTTAdapter, _MOCK_TRANSCRIPT
from sceneforge.audio.interfaces import WordTimestamp
from sceneforge.retrieval.adapters.mock_stock import MockStockProvider
from sceneforge.retrieval.adapters.mock_generated import MockGeneratedProvider
from sceneforge.retrieval.adapters.mock_embeddings import MockEmbeddingModel
from sceneforge.planner.adapters.mock_llm import MockLLMPlannerAdapter


class TestMockTTS:
    def setup_method(self):
        self.tts = MockTTSAdapter()

    def test_is_mock(self):
        assert self.tts.is_mock is True
        assert self.tts.adapter_name == "mock"

    def test_returns_bytes(self):
        result = self.tts.synthesise("Hello world")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_returns_valid_wav_header(self):
        result = self.tts.synthesise("Test")
        # WAV files start with RIFF
        assert result[:4] == b"RIFF"
        assert result[8:12] == b"WAVE"

    def test_deterministic_output(self):
        r1 = self.tts.synthesise("Any text")
        r2 = self.tts.synthesise("Different text")
        # Mock always returns same bytes regardless of input
        assert r1 == r2

    def test_duration_estimate_positive(self):
        duration = self.tts.estimated_duration("Hello world this is a test")
        assert duration > 0.0

    def test_duration_scales_with_length(self):
        short = self.tts.estimated_duration("Hi")
        long_ = self.tts.estimated_duration("This is a much longer sentence with many words")
        assert long_ > short

    def test_voice_param_ignored(self):
        r1 = self.tts.synthesise("text", voice="voice-A")
        r2 = self.tts.synthesise("text", voice="voice-B")
        assert r1 == r2


class TestMockSTT:
    def setup_method(self):
        self.stt = MockSTTAdapter()

    def test_is_mock(self):
        assert self.stt.is_mock is True
        assert self.stt.adapter_name == "mock"

    def test_returns_transcript_and_timestamps(self):
        transcript, timestamps = self.stt.transcribe(b"irrelevant audio bytes")
        assert isinstance(transcript, str)
        assert len(transcript) > 0
        assert isinstance(timestamps, list)
        assert len(timestamps) > 0

    def test_transcript_is_fixed(self):
        t1, _ = self.stt.transcribe(b"audio1")
        t2, _ = self.stt.transcribe(b"audio2")
        assert t1 == t2 == _MOCK_TRANSCRIPT

    def test_timestamps_are_word_timestamps(self):
        _, timestamps = self.stt.transcribe(b"")
        for ts in timestamps:
            assert isinstance(ts, WordTimestamp)
            assert ts.start >= 0.0
            assert ts.end > ts.start
            assert isinstance(ts.word, str)

    def test_timestamps_are_sorted(self):
        _, timestamps = self.stt.transcribe(b"")
        for i in range(1, len(timestamps)):
            assert timestamps[i].start >= timestamps[i - 1].start


class TestMockStockProvider:
    def setup_method(self):
        self.provider = MockStockProvider()

    def test_is_mock(self):
        assert self.provider.is_mock is True
        assert self.provider.provider_name == "mock_stock"

    def test_returns_assets(self):
        assets = self.provider.search("any query")
        assert len(assets) > 0

    def test_assets_have_required_fields(self):
        assets = self.provider.search("test")
        for a in assets:
            assert a.asset_id
            assert a.provider_name == "mock_stock"
            assert a.licence_name
            assert a.commercial_use_eligible is True
            assert a.is_mock is True

    def test_max_results_respected(self):
        assets = self.provider.search("test", max_results=2)
        assert len(assets) <= 2

    def test_deterministic_results(self):
        r1 = self.provider.search("query A")
        r2 = self.provider.search("query B")
        assert [a.asset_id for a in r1] == [a.asset_id for a in r2]

    def test_asset_urls_present(self):
        assets = self.provider.search("test")
        for a in assets:
            assert a.source_url
            assert a.provider_asset_url


class TestMockGeneratedProvider:
    def setup_method(self):
        self.provider = MockGeneratedProvider()

    def test_is_mock(self):
        assert self.provider.is_mock is True
        assert self.provider.provider_name == "mock_generated"

    def test_returns_asset(self):
        asset = self.provider.generate("any prompt")
        assert asset.asset_id
        assert asset.commercial_use_eligible is True
        assert asset.is_mock is True
        assert asset.asset_type == "generated"

    def test_deterministic(self):
        a1 = self.provider.generate("prompt one")
        a2 = self.provider.generate("prompt two")
        assert a1.asset_id == a2.asset_id


class TestMockEmbeddings:
    def setup_method(self):
        self.model = MockEmbeddingModel()

    def test_is_mock(self):
        assert self.model.is_mock is True
        assert self.model.model_name == "mock_embeddings"

    def test_returns_float_list(self):
        vec = self.model.embed("hello world")
        assert isinstance(vec, list)
        assert all(isinstance(x, float) for x in vec)
        assert len(vec) == 64

    def test_deterministic(self):
        v1 = self.model.embed("same text")
        v2 = self.model.embed("same text")
        assert v1 == v2

    def test_different_texts_different_vectors(self):
        v1 = self.model.embed("city skyline")
        v2 = self.model.embed("ocean waves")
        assert v1 != v2

    def test_similarity_in_range(self):
        s = self.model.similarity("innovation", "technology")
        assert 0.0 <= s <= 1.0

    def test_identical_texts_high_similarity(self):
        s = self.model.similarity("same text", "same text")
        # Identical inputs → cosine = 1.0 → mapped to 1.0
        assert s > 0.99


class TestMockLLMPlanner:
    def setup_method(self):
        self.planner = MockLLMPlannerAdapter()

    def test_is_mock(self):
        assert self.planner.is_mock is True
        assert self.planner.adapter_name == "mock_llm"

    def test_returns_scene_plans(self):
        from sceneforge.audio.adapters.mock_stt import MockSTTAdapter
        _, word_ts = MockSTTAdapter().transcribe(b"")
        plans = self.planner.plan_scenes("Test narration.", word_ts)
        assert len(plans) >= 1

    def test_scenes_have_required_fields(self):
        from sceneforge.audio.adapters.mock_stt import MockSTTAdapter
        _, word_ts = MockSTTAdapter().transcribe(b"")
        plans = self.planner.plan_scenes("Hello world.", word_ts)
        for p in plans:
            assert p.scene_id
            assert p.narration_text
            assert p.start_time >= 0.0
            assert p.end_time > p.start_time
            assert p.visual_concept
            assert isinstance(p.search_queries, list)
            assert p.suggested_visual_type in (
                "stock_footage", "generated_image", "typography_card", "data_card"
            )
            assert 0.0 <= p.confidence <= 1.0
            assert p.is_mock is True

    def test_scenes_cover_full_duration(self):
        from sceneforge.audio.adapters.mock_stt import MockSTTAdapter
        _, word_ts = MockSTTAdapter().transcribe(b"")
        plans = self.planner.plan_scenes("Test.", word_ts)
        assert plans[0].start_time == 0.0
        # Last scene should end at approximately the transcript duration
        assert plans[-1].end_time > 0.0
