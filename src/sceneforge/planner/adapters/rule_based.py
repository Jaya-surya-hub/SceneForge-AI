"""Rule-based scene planner — deterministic, no LLM, no API keys.

Converts narration segments into ScenePlan objects using explicit rules:

  1. Sentence segmentation (via planner.segmenter)
  2. Disambiguation for known ambiguous terms (via planner.disambiguation)
  3. Abstract concept detection → typography_card
  4. Numeric/statistic detection → data_card
  5. Named person/brand detection → safety handling
  6. Default → stock_footage with search queries derived from key nouns

Every decision is documented in plan_metadata for traceability.
No statistics, testimonials, or facts are invented.

Rules are explicit and version-controlled. If a rule set is updated, the
RULES_VERSION constant must be incremented to invalidate the render cache.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict
from typing import Literal, Optional

from sceneforge.audio.interfaces import WordTimestamp
from sceneforge.planner.disambiguation import (
    AMBIGUOUS_TERMS,
    disambiguate,
    get_context_words,
)
from sceneforge.planner.interfaces import PlannerAdapter, ScenePlan
from sceneforge.planner.segmenter import Segment, segment_transcript
from sceneforge.observability.logging import get_logger

log = get_logger(__name__)

RULES_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Abstract concept vocabulary
# These terms indicate the narration is about ideas rather than visible objects.
# They trigger a typography card rather than forcing a literal search.
# ---------------------------------------------------------------------------
_ABSTRACT_TERMS: frozenset[str] = frozenset({
    "trust", "hope", "faith", "love", "freedom", "justice", "equality",
    "democracy", "peace", "courage", "integrity", "vision", "mission",
    "values", "culture", "purpose", "meaning", "inspiration", "passion",
    "resilience", "perseverance", "dedication", "commitment", "excellence",
    "transparency", "accountability", "authenticity", "empathy", "kindness",
    "gratitude", "mindfulness", "wisdom", "creativity", "imagination",
    "innovation", "transformation", "revolution", "change", "progress",
    "potential", "opportunity", "growth", "journey", "story", "legacy",
    "impact", "difference", "future", "tomorrow", "destiny", "possibility",
})

# ---------------------------------------------------------------------------
# Safety patterns: named people and brands
# We do NOT generate images of named individuals or brand endorsements.
# ---------------------------------------------------------------------------
_TITLE_PATTERN = re.compile(
    r"\b(mr|mrs|ms|dr|prof|president|ceo|founder|director)\b",
    re.IGNORECASE,
)
# Simple heuristic: two consecutive Title Case words not at start of sentence
_NAMED_PERSON_PATTERN = re.compile(
    r"(?<![.!?]\s)\b([A-Z][a-z]{1,20})\s+([A-Z][a-z]{1,20})\b"
)
# Brand indicators: ® ™ or all-caps words 3+ chars (heuristic, not perfect)
_BRAND_PATTERN = re.compile(r"[®™]|\b[A-Z]{3,}\b")

# ---------------------------------------------------------------------------
# Numeric/statistic detection
# ---------------------------------------------------------------------------
_NUMERIC_PATTERN = re.compile(
    r"""
    \b
    (?:
        \d[\d,]*(?:\.\d+)?   # integer or decimal
        (?:\s*[%$€£¥])?      # optional currency/percent suffix
        |
        [€$£¥]\d[\d,]*       # currency prefix
    )
    \b
    """,
    re.VERBOSE,
)
_DATE_PATTERN = re.compile(
    r"\b(?:19|20)\d{2}\b"   # four-digit year
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?\b",
    re.IGNORECASE,
)


class RuleBasedPlannerAdapter(PlannerAdapter):
    """Deterministic rule-based scene planner.

    Requires no LLM, no API keys, no network access.
    Implements PlannerAdapter interface so it can be swapped for an LLM adapter.
    """

    adapter_name: str = "rule_based"
    is_mock: bool = False   # This is a REAL planner (not mock), just no LLM

    def __init__(
        self,
        *,
        min_chars: int = 20,
        max_chars: int = 300,
        min_duration: float = 1.5,
    ) -> None:
        self._min_chars = min_chars
        self._max_chars = max_chars
        self._min_duration = min_duration

    def plan_scenes(
        self,
        transcript: str,
        word_timestamps: list[WordTimestamp],
    ) -> list[ScenePlan]:
        """Convert narration into ScenePlan objects.

        Args:
            transcript:      Full narration text.
            word_timestamps: Word-level timing from audio pipeline.

        Returns:
            Ordered list of ScenePlan objects.
        """
        if not transcript.strip():
            return []

        segments = segment_transcript(
            transcript,
            word_timestamps,
            min_chars=self._min_chars,
            max_chars=self._max_chars,
            min_duration=self._min_duration,
        )

        plans = []
        seen_asset_types: list[str] = []

        for seg in segments:
            plan = self._plan_segment(seg, transcript)
            plans.append(plan)
            seen_asset_types.append(plan.suggested_visual_type)

        log.info(
            "rule_based_planner_done",
            segment_count=len(plans),
            types={t: seen_asset_types.count(t) for t in set(seen_asset_types)},
        )
        return plans

    # ------------------------------------------------------------------
    # Per-segment planning
    # ------------------------------------------------------------------

    def _plan_segment(self, seg: Segment, full_transcript: str) -> ScenePlan:
        """Apply rules to a single segment and return a ScenePlan."""
        text = seg.text
        # Use segment-level context for abstract/concrete detection
        # Use full transcript context only for disambiguation (needs wider context)
        context = get_context_words(full_transcript)

        metadata: dict = {
            "rules_version": RULES_VERSION,
            "timing_method": seg.timing_method,
            "segment_index": seg.index,
        }

        # ── Rule 1: Named person detection ──────────────────────────────────
        named_persons = self._detect_named_persons(text)
        if named_persons:
            return self._plan_with_named_person(seg, named_persons, metadata)

        # ── Rule 2: Brand/product mention ───────────────────────────────────
        brands = self._detect_brands(text)
        if brands:
            metadata["brands_detected"] = brands

        # ── Rule 3: Numeric / statistical claim → data card ─────────────────
        if self._has_numeric_claim(text):
            return self._plan_data_card(seg, metadata)

        # ── Rule 4: Abstract concept → typography card ───────────────────────
        abstract_matches = self._detect_abstract_terms(text)
        if abstract_matches and not self._has_concrete_visual(text):
            return self._plan_typography_card(seg, abstract_matches, metadata)

        # ── Rule 5: Ambiguous term disambiguation ────────────────────────────
        disambiguation = self._disambiguate_terms(text, context)
        if disambiguation:
            metadata["disambiguation"] = {
                "term": disambiguation["term"],
                "resolved_meaning": disambiguation["resolved_meaning"],
                "visual_domain": disambiguation["visual_domain"],
            }
            return self._plan_stock_with_disambiguation(seg, disambiguation, brands, metadata)

        # ── Default: stock footage ───────────────────────────────────────────
        return self._plan_stock_default(seg, brands, metadata)

    # ------------------------------------------------------------------
    # Plan constructors for each rule
    # ------------------------------------------------------------------

    def _plan_with_named_person(
        self, seg: Segment, persons: list[str], metadata: dict
    ) -> ScenePlan:
        """Named person → stock footage that excludes the person's name.

        We NEVER search for a named individual's image. We search for
        the concept around them (e.g. 'leadership', 'innovation') with
        the person's name in negative_terms.
        """
        text = seg.text
        concept = self._extract_concept_without_names(text, persons)
        negative_terms = list(persons)

        metadata["named_persons"] = persons
        metadata["safety_rule"] = "named_person_excluded_from_search"

        return ScenePlan(
            scene_id=self._new_id(),
            narration_text=text,
            start_time=seg.start_time,
            end_time=seg.end_time,
            key_entities=[c for c in concept.split() if len(c) > 3],
            intended_meaning=f"Concept related to: {concept}",
            visual_concept=f"Professional concept imagery representing {concept}",
            search_queries=[
                concept,
                f"{concept} abstract professional",
            ],
            suggested_visual_type="stock_footage",
            negative_terms=negative_terms,
            safety_constraints=[
                f"Do not depict named individuals: {', '.join(persons)}",
                "Do not imply endorsement by named persons",
            ],
            confidence=0.6,
            preferred_source_route="stock",
            caption_text=text,
            is_mock=False,
            plan_metadata=metadata,
        )

    def _plan_data_card(self, seg: Segment, metadata: dict) -> ScenePlan:
        """Numeric/statistical claim → data card.

        Uses only numbers explicitly present in the text.
        Never invents statistics.
        """
        text = seg.text
        numbers = _NUMERIC_PATTERN.findall(text)
        dates = _DATE_PATTERN.findall(text)

        metadata["numbers_found"] = numbers
        metadata["dates_found"] = dates
        metadata["data_card_rule"] = "numeric_claim_detected"

        return ScenePlan(
            scene_id=self._new_id(),
            narration_text=text,
            start_time=seg.start_time,
            end_time=seg.end_time,
            key_entities=numbers + dates,
            intended_meaning="Statistical or numerical claim from narration",
            visual_concept=(
                f"Data card showing: {text[:80]}{'...' if len(text) > 80 else ''}"
            ),
            search_queries=[],  # Data cards are programmatically generated
            suggested_visual_type="data_card",
            negative_terms=[],
            safety_constraints=["Only display numbers from the supplied narration"],
            confidence=0.9,
            preferred_source_route="card",
            caption_text=text,
            is_mock=False,
            plan_metadata=metadata,
        )

    def _plan_typography_card(
        self, seg: Segment, abstract_terms: list[str], metadata: dict
    ) -> ScenePlan:
        """Abstract concept → typography card with the key phrase displayed."""
        text = seg.text
        key_phrase = self._extract_key_phrase(text, abstract_terms)

        metadata["abstract_terms"] = abstract_terms
        metadata["typography_rule"] = "abstract_concept_no_literal_visual"

        return ScenePlan(
            scene_id=self._new_id(),
            narration_text=text,
            start_time=seg.start_time,
            end_time=seg.end_time,
            key_entities=abstract_terms,
            intended_meaning=f"Abstract concept: {', '.join(abstract_terms)}",
            visual_concept=f"Typography card displaying: '{key_phrase}'",
            search_queries=[],  # Typography cards are programmatically generated
            suggested_visual_type="typography_card",
            negative_terms=[],
            safety_constraints=[],
            confidence=0.85,
            preferred_source_route="card",
            caption_text=text,
            is_mock=False,
            plan_metadata=metadata,
        )

    def _plan_stock_with_disambiguation(
        self,
        seg: Segment,
        disambiguation: dict,
        brands: list[str],
        metadata: dict,
    ) -> ScenePlan:
        """Disambiguated term → stock footage in the resolved visual domain."""
        text = seg.text
        domain = disambiguation["visual_domain"]
        meaning = disambiguation["resolved_meaning"]
        negative = list(disambiguation.get("negative_terms", []))

        queries = [
            domain.replace("_", " "),
            f"{meaning} concept",
        ]
        if brands:
            metadata["brands"] = brands
            negative.extend(brands)

        return ScenePlan(
            scene_id=self._new_id(),
            narration_text=text,
            start_time=seg.start_time,
            end_time=seg.end_time,
            key_entities=[disambiguation["term"], meaning],
            intended_meaning=meaning,
            visual_concept=f"Imagery representing {meaning}",
            search_queries=queries,
            suggested_visual_type="stock_footage",
            negative_terms=negative,
            safety_constraints=[],
            confidence=0.75,
            preferred_source_route="stock",
            caption_text=text,
            is_mock=False,
            plan_metadata=metadata,
        )

    def _plan_stock_default(
        self, seg: Segment, brands: list[str], metadata: dict
    ) -> ScenePlan:
        """Default: stock footage derived from key nouns in the text."""
        text = seg.text
        key_nouns = self._extract_key_nouns(text)
        queries = self._build_search_queries(text, key_nouns)
        negative = list(brands) if brands else []

        if brands:
            metadata["brands"] = brands
            metadata["brand_safety"] = "brand_names_excluded_from_search"

        return ScenePlan(
            scene_id=self._new_id(),
            narration_text=text,
            start_time=seg.start_time,
            end_time=seg.end_time,
            key_entities=key_nouns[:5],
            intended_meaning=self._infer_meaning(text),
            visual_concept=self._infer_visual_concept(text, key_nouns),
            search_queries=queries,
            suggested_visual_type="stock_footage",
            negative_terms=negative,
            safety_constraints=[],
            confidence=0.65,
            preferred_source_route="stock",
            caption_text=text,
            is_mock=False,
            plan_metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def _detect_named_persons(self, text: str) -> list[str]:
        """Detect named individuals (heuristic: two consecutive Title Case words)."""
        persons = []
        # Title + name pattern
        title_matches = _TITLE_PATTERN.findall(text)
        if title_matches:
            # Find the word following the title
            for m in re.finditer(
                r"\b(?:Mr|Mrs|Ms|Dr|Prof|President|CEO|Founder|Director)\b\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                text
            ):
                persons.append(m.group(1))

        # Two consecutive Title Case words not at sentence start
        for m in _NAMED_PERSON_PATTERN.finditer(text):
            name = f"{m.group(1)} {m.group(2)}"
            if name not in persons:
                persons.append(name)

        return persons

    def _detect_brands(self, text: str) -> list[str]:
        """Detect potential brand mentions (® ™ symbols or ALL-CAPS words)."""
        brands = []
        # Registered/trademark symbols
        for m in re.finditer(r"([A-Za-z]+(?:\s+[A-Za-z]+)?)\s*[®™]", text):
            brands.append(m.group(1))
        # ALL-CAPS words 3+ characters (exclude common acronyms like "GDP", "CEO")
        common_acronyms = {"CEO", "CFO", "CTO", "GDP", "ROI", "AI", "API", "ML",
                           "IT", "HR", "PR", "USA", "UK", "EU", "UN", "WHO"}
        for m in re.finditer(r"\b([A-Z]{3,})\b", text):
            word = m.group(1)
            if word not in common_acronyms:
                brands.append(word)
        return list(set(brands))

    def _has_numeric_claim(self, text: str) -> bool:
        """Return True if text contains a numeric or statistical claim."""
        return bool(_NUMERIC_PATTERN.search(text) or _DATE_PATTERN.search(text))

    def _detect_abstract_terms(self, text: str) -> list[str]:
        """Return abstract terms found in text."""
        words = set(re.findall(r"\b[a-z]+\b", text.lower()))
        return sorted(words & _ABSTRACT_TERMS)

    def _has_concrete_visual(self, text: str) -> bool:
        """Return True if text also contains concrete visual nouns.

        If abstract and concrete terms coexist, prefer stock footage.
        """
        concrete_nouns = {
            "person", "people", "team", "office", "building", "city",
            "nature", "mountain", "ocean", "technology", "computer",
            "product", "business", "factory", "field", "road",
            "beach", "waves", "sea", "water", "sunset", "sunrise", "sky",
            "sun", "leaves", "tree", "trees", "forest", "path", "street",
            "car", "cars", "traffic", "lights", "night", "stars", "space",
            "earth", "robot", "machine", "screen", "data", "hands", "worker",
            "walking", "running", "house", "room", "table", "book", "food",
            "animal", "animals", "dog", "dogs", "puppy", "puppies", "cat", "cats",
            "kitten", "kittens", "pet", "pets", "bird", "fish", "plant",
            "art", "music", "code", "software", "phone", "mobile", "glass",
            "light", "dark", "fire", "ice", "snow", "rain", "cloud", "clouds",
            "step", "build", "idea",
        }
        words = set(re.findall(r"\b[a-z]+\b", text.lower()))
        return bool(words & concrete_nouns)

    def _disambiguate_terms(
        self, text: str, context: list[str]
    ) -> Optional[dict]:
        """Check text for ambiguous terms and return disambiguation result."""
        words = text.lower().split()
        for word in words:
            clean = re.sub(r"[^\w]", "", word)
            if clean in AMBIGUOUS_TERMS:
                rule = disambiguate(clean, context)
                if rule:
                    return {
                        "term": clean,
                        "resolved_meaning": rule.resolved_meaning,
                        "visual_domain": rule.visual_domain,
                        "negative_terms": list(rule.negative_terms),
                    }
        return None

    def _extract_key_nouns(self, text: str) -> list[str]:
        """Extract likely key nouns (3+ char words, not stopwords)."""
        _STOPWORDS = {
            "this", "that", "with", "from", "they", "have", "been", "will",
            "were", "when", "what", "which", "their", "there", "about",
            "into", "more", "than", "also", "just", "each", "them", "then",
            "very", "some", "make", "than", "time", "only", "over", "such",
            "even", "most", "your", "these", "those", "like", "well", "back",
            "good", "much", "look", "come", "could", "would", "should",
            "the", "and", "for", "are", "but", "not", "you", "all", "any",
            "can", "her", "was", "one", "our", "out", "day", "get", "has",
            "him", "his", "how", "man", "new", "now", "old", "see", "two",
            "way", "who", "boy", "did", "its", "let", "put", "say", "she",
            "too", "use",
            # Meta-prompt instruction & filler words
            "create", "creating", "video", "videos", "show", "showing", "shows",
            "generate", "generating", "make", "making", "realistic", "high",
            "quality", "stock", "footage", "clip", "clips", "cinematic",
            "around", "seconds", "english", "voiceover", "audio", "engaging",
            "scene", "scenes", "image", "images", "prompt", "broll", "please",
            "using", "giving", "takes", "taking", "bring", "brings",
        }
        words = re.findall(r"\b[a-z]{3,}\b", text.lower())
        return [w for w in words if w not in _STOPWORDS][:8]

    def _build_search_queries(self, text: str, key_nouns: list[str]) -> list[str]:
        """Build 2-3 focused search queries from key visual nouns."""
        queries = []
        if key_nouns:
            # Primary: top 2-3 visual nouns combined
            queries.append(" ".join(key_nouns[:min(3, len(key_nouns))]))
            if len(key_nouns) >= 2:
                queries.append(f"{key_nouns[0]} {key_nouns[1]}")
                # Fallback to key subject alone (guarantees provider matches)
                queries.append(key_nouns[0])
            else:
                queries.append(key_nouns[0])
        if not queries:
            # Fallback: first meaningful words from text
            words = [w for w in re.findall(r"\b[a-z]{3,}\b", text.lower()) if len(w) > 3][:3]
            if words:
                queries.append(" ".join(words))
                queries.append(words[0])
            else:
                words = text.split()[:3]
                queries.append(" ".join(words))
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for q in queries:
            c = q.strip()
            if c and c not in seen:
                seen.add(c)
                unique.append(c)
        return unique[:3]

    def _extract_key_phrase(self, text: str, abstract_terms: list[str]) -> str:
        """Extract the most prominent abstract phrase for a typography card."""
        if not abstract_terms:
            return text[:50].strip()
        # Use the first abstract term and its immediate neighbours
        term = abstract_terms[0]
        match = re.search(
            rf"\b\w+\s+{re.escape(term)}\s+\w+\b|\b{re.escape(term)}\s+\w+\b|\b\w+\s+{re.escape(term)}\b",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(0).strip()
        return term.capitalize()

    def _extract_concept_without_names(
        self, text: str, persons: list[str]
    ) -> str:
        """Extract the conceptual meaning from text, removing named persons."""
        cleaned = text
        for person in persons:
            cleaned = re.sub(re.escape(person), "", cleaned, flags=re.IGNORECASE)
        # Get key nouns from cleaned text
        nouns = self._extract_key_nouns(cleaned)
        return " ".join(nouns[:3]) if nouns else "professional achievement"

    def _infer_meaning(self, text: str) -> str:
        """Infer a brief meaning statement from the narration text."""
        # Use first 80 chars as the meaning; strip trailing incomplete words
        short = text[:80].rsplit(" ", 1)[0] if len(text) > 80 else text
        return short.strip().rstrip(".,;:")

    def _infer_visual_concept(self, text: str, key_nouns: list[str]) -> str:
        """Infer a visual concept description from key nouns."""
        if key_nouns:
            return f"Imagery depicting {', '.join(key_nouns[:3])}"
        return f"Visual concept for: {text[:60].strip()}"

    @staticmethod
    def _new_id() -> str:
        return f"scene-{uuid.uuid4().hex[:8]}"
