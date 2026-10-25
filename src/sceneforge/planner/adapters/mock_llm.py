"""Mock LLM planner adapter — deterministic, no API keys required.

Returns a fixed two-scene plan for any input. Clearly labelled as mock.
This adapter MUST NOT be used to claim real LLM planning was performed.
"""

from __future__ import annotations

import uuid

from sceneforge.audio.interfaces import WordTimestamp
from sceneforge.planner.interfaces import PlannerAdapter, ScenePlan


class MockLLMPlannerAdapter(PlannerAdapter):
    """[MOCK] Deterministic planner adapter for the no-key test suite.

    Returns a two-scene plan regardless of input.
    NOTE: No LLM inference is performed.
    """

    adapter_name: str = "mock_llm"
    is_mock: bool = True

    def plan_scenes(
        self,
        transcript: str,
        word_timestamps: list[WordTimestamp],
    ) -> list[ScenePlan]:
        """Return a fixed two-scene plan. Inputs are used only for timing.

        NOTE: This is a MOCK adapter. No real planning is performed.
        """
        # Derive approximate mid-point from word timestamps
        if word_timestamps:
            total_duration = word_timestamps[-1].end
            mid = total_duration / 2
        else:
            total_duration = 10.0
            mid = 5.0

        words_first_half = transcript[: len(transcript) // 2]
        words_second_half = transcript[len(transcript) // 2:]

        return [
            ScenePlan(
                scene_id=f"mock-scene-{uuid.uuid4().hex[:8]}",
                narration_text=words_first_half.strip() or "Mock narration part 1.",
                start_time=0.0,
                end_time=mid,
                key_entities=["innovation", "progress"],
                intended_meaning="Convey the concept of forward momentum and innovation.",
                visual_concept="People working on technology in a bright modern space",
                search_queries=[
                    "technology innovation workplace",
                    "modern office team collaboration",
                ],
                suggested_visual_type="stock_footage",
                negative_terms=[],
                safety_constraints=[],
                confidence=0.85,
                preferred_source_route="stock",
                caption_text=words_first_half.strip() or "Mock narration part 1.",
                is_mock=True,
            ),
            ScenePlan(
                scene_id=f"mock-scene-{uuid.uuid4().hex[:8]}",
                narration_text=words_second_half.strip() or "Mock narration part 2.",
                start_time=mid,
                end_time=total_duration,
                key_entities=["future", "idea"],
                intended_meaning="Inspire with a sense of possibility and new beginnings.",
                visual_concept="Abstract sunrise or horizon representing new beginnings",
                search_queries=[
                    "sunrise horizon future",
                    "abstract light concept",
                ],
                suggested_visual_type="stock_footage",
                negative_terms=[],
                safety_constraints=[],
                confidence=0.80,
                preferred_source_route="stock",
                caption_text=words_second_half.strip() or "Mock narration part 2.",
                is_mock=True,
            ),
        ]
