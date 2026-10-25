"""Planner adapter factory — select planner from environment configuration.

LLM_ADAPTER env var: none (default, rule-based) | openai
"""

from __future__ import annotations

import os
from typing import Optional

from sceneforge.planner.interfaces import PlannerAdapter


def get_planner_adapter(override: Optional[str] = None) -> PlannerAdapter:
    """Return the configured scene planner adapter.

    Args:
        override: Adapter name override (ignores env var).

    Returns:
        A PlannerAdapter instance.
    """
    name = (override or os.getenv("LLM_ADAPTER", "none")).lower().strip()

    if name == "openai":
        # Optional LLM adapter — only available when OPENAI_API_KEY is set
        try:
            from sceneforge.planner.adapters.llm_openai import OpenAIPlannerAdapter  # type: ignore
            return OpenAIPlannerAdapter()
        except ImportError:
            pass  # Fall through to rule-based

    if name == "mock":
        from sceneforge.planner.adapters.mock_llm import MockLLMPlannerAdapter
        return MockLLMPlannerAdapter()

    # Default: rule-based (no external dependencies)
    from sceneforge.planner.adapters.rule_based import RuleBasedPlannerAdapter
    return RuleBasedPlannerAdapter()
