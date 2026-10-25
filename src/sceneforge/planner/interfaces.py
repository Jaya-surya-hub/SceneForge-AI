"""Abstract interface for scene planner adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal, Optional

from sceneforge.audio.interfaces import WordTimestamp


@dataclass
class ScenePlan:
    """Structured visual concept for a single narration segment."""

    scene_id: str
    narration_text: str
    start_time: float
    end_time: float
    key_entities: list[str]
    intended_meaning: str
    visual_concept: str
    search_queries: list[str]
    suggested_visual_type: Literal[
        "stock_footage", "generated_image", "typography_card", "data_card"
    ]
    negative_terms: list[str]
    safety_constraints: list[str]
    confidence: float
    preferred_source_route: str
    caption_text: str
    is_mock: bool = False
    plan_metadata: dict = field(default_factory=dict)


class PlannerAdapter(ABC):
    """Interface for scene planning adapters (rule-based or LLM-backed)."""

    adapter_name: str = "base"
    is_mock: bool = False

    @abstractmethod
    def plan_scenes(
        self,
        transcript: str,
        word_timestamps: list[WordTimestamp],
    ) -> list[ScenePlan]:
        """Turn a narration transcript into a list of ScenePlan objects.

        Args:
            transcript:      Full narration text.
            word_timestamps: Word-level timing from STT or TTS.

        Returns:
            Ordered list of ScenePlan objects covering the narration.
        """
