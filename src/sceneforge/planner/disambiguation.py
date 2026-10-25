"""Context-based term disambiguation rules.

Resolves ambiguous words to a specific meaning based on surrounding context.
Rules are explicit, documented, and deterministic — no probabilistic models.

Each rule is: (ambiguous_term, context_hints, resolved_meaning, visual_domain).

Context hints are words that, when present near the ambiguous term,
indicate which sense is intended.

This module is imported by the rule-based planner; it never calls external
services and never invents information beyond these rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DisambiguationRule:
    """A single disambiguation rule."""

    term: str                    # The ambiguous word (lowercase)
    context_hints: tuple[str, ...]  # Words that signal this sense
    resolved_meaning: str        # Human-readable resolved meaning
    visual_domain: str           # Domain for visual search queries
    negative_terms: tuple[str, ...] = ()  # Terms to exclude from search


# ---------------------------------------------------------------------------
# Disambiguation table
# ---------------------------------------------------------------------------

DISAMBIGUATION_RULES: list[DisambiguationRule] = [
    # "bank" — financial vs. riverbank
    DisambiguationRule(
        term="bank",
        context_hints=("money", "loan", "interest", "account", "finance",
                       "credit", "deposit", "savings", "investment", "financial",
                       "banking", "currency", "economy", "debt", "mortgage"),
        resolved_meaning="financial institution",
        visual_domain="bank_financial",
        negative_terms=("river", "water", "shore"),
    ),
    DisambiguationRule(
        term="bank",
        context_hints=("river", "stream", "water", "shore", "flood",
                       "erosion", "nature", "landscape", "fish"),
        resolved_meaning="riverbank / natural landform",
        visual_domain="bank_river",
        negative_terms=("money", "finance", "loan"),
    ),

    # "cloud" — computing vs. weather
    DisambiguationRule(
        term="cloud",
        context_hints=("computing", "server", "data", "storage", "service",
                       "technology", "software", "platform", "infrastructure",
                       "digital", "internet", "saas", "aws", "azure"),
        resolved_meaning="cloud computing / digital infrastructure",
        visual_domain="cloud_computing",
        negative_terms=("rain", "sky", "weather", "storm"),
    ),
    DisambiguationRule(
        term="cloud",
        context_hints=("sky", "weather", "rain", "storm", "sun",
                       "atmosphere", "forecast", "humidity", "climate"),
        resolved_meaning="meteorological cloud / weather",
        visual_domain="cloud_weather",
        negative_terms=("server", "data", "computing", "software"),
    ),

    # "plant" — factory vs. vegetation
    DisambiguationRule(
        term="plant",
        context_hints=("factory", "manufacturing", "production", "industrial",
                       "facility", "operations", "workers", "assembly"),
        resolved_meaning="industrial manufacturing plant",
        visual_domain="plant_factory",
        negative_terms=("flower", "tree", "garden", "leaf"),
    ),
    DisambiguationRule(
        term="plant",
        context_hints=("garden", "flower", "tree", "leaf", "grow",
                       "nature", "green", "soil", "seed", "forest"),
        resolved_meaning="plant / vegetation",
        visual_domain="plant_nature",
        negative_terms=("factory", "industrial"),
    ),

    # "spring" — season vs. mechanical spring
    DisambiguationRule(
        term="spring",
        context_hints=("season", "flower", "bloom", "warm", "weather",
                       "nature", "rain", "renewal", "growth"),
        resolved_meaning="spring season / renewal",
        visual_domain="spring_season",
    ),
    DisambiguationRule(
        term="spring",
        context_hints=("coil", "mechanism", "tension", "compression",
                       "engineering", "metal", "elastic", "bounce"),
        resolved_meaning="mechanical spring",
        visual_domain="spring_mechanical",
    ),

    # "pitch" — sports vs. audio/music vs. sales
    DisambiguationRule(
        term="pitch",
        context_hints=("football", "soccer", "cricket", "sports", "field",
                       "grass", "stadium", "game", "match", "play"),
        resolved_meaning="sports field / pitch",
        visual_domain="pitch_sports",
    ),
    DisambiguationRule(
        term="pitch",
        context_hints=("sales", "investor", "startup", "presentation",
                       "business", "deck", "funding", "idea"),
        resolved_meaning="sales or investor pitch presentation",
        visual_domain="pitch_business",
    ),
]


def disambiguate(
    term: str,
    context_words: list[str],
) -> Optional[DisambiguationRule]:
    """Return the best matching DisambiguationRule for *term* given context.

    Args:
        term:          The ambiguous word (case-insensitive).
        context_words: Words surrounding the term in the narration.

    Returns:
        The best matching DisambiguationRule, or None if no rule matches.
        When multiple rules match the same term, the one with the most
        context hint matches wins.
    """
    term_lower = term.lower()
    context_lower = {w.lower() for w in context_words}

    best_rule: Optional[DisambiguationRule] = None
    best_score = 0

    for rule in DISAMBIGUATION_RULES:
        if rule.term != term_lower:
            continue
        score = sum(1 for hint in rule.context_hints if hint in context_lower)
        if score > best_score:
            best_score = score
            best_rule = rule

    return best_rule


def get_context_words(text: str, window: int = 50) -> list[str]:
    """Extract word tokens from text (for context matching)."""
    import re
    return re.findall(r"\b[a-z]+\b", text.lower())


# ---------------------------------------------------------------------------
# Ambiguous term registry (for planner to check before processing)
# ---------------------------------------------------------------------------

AMBIGUOUS_TERMS: frozenset[str] = frozenset(
    rule.term for rule in DISAMBIGUATION_RULES
)
