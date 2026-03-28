from __future__ import annotations

import re
from typing import Dict, List

from mellow_chat_runtime.core.domain_lookup_store import DomainLookupStore
from mellow_chat_runtime.services.summary_formatter import prepare_searchable_payload


class MemoryPromotionService:
    """Promote selected short-term turn content into long-term character memories."""

    KEYWORDS = (
        "remember",
        "important",
        "promise",
        "promised",
        "decide",
        "decided",
        "plan",
        "planned",
        "기억",
        "중요",
        "약속",
        "결정",
        "계획",
    )
    NOISE_PATTERNS = (
        "<|",
        "</think>",
        "<think>",
        "assistant",
        "system prompt",
        "there wasn't a complex prompt",
    )

    def __init__(self, domain_store: DomainLookupStore, max_items: int = 20) -> None:
        self._domain_store = domain_store
        self._max_items = max(1, int(max_items or 20))

    def promote_from_text(self, character_id: str, text: str) -> List[str]:
        cleaned_character_id = (character_id or "").strip()
        if not cleaned_character_id:
            return []

        candidates = self._extract_candidates(text)
        if not candidates:
            return []

        memory_state = self._domain_store.get_memory_and_possessions(cleaned_character_id)
        existing_items = self._clean_memory_list(memory_state.get("important_memories", []))
        existing_lower = {item.lower(): item for item in existing_items}

        promoted: List[str] = []
        merged = list(existing_items)
        for candidate in candidates:
            lowered = candidate.lower()
            if lowered in existing_lower:
                continue
            merged.append(candidate)
            existing_lower[lowered] = candidate
            promoted.append(candidate)

        if not promoted:
            return []

        updated_memory: Dict[str, object] = {
            "character_id": cleaned_character_id,
            "important_memories": merged[-self._max_items :],
            "possessions": self._clean_memory_list(memory_state.get("possessions", [])),
            "embedding_status": "dirty",
        }
        self._domain_store.upsert("memories", cleaned_character_id, prepare_searchable_payload("memories", cleaned_character_id, updated_memory))
        return promoted

    def _extract_candidates(self, text: str) -> List[str]:
        normalized = re.sub(r"\s+", " ", (text or "").strip())
        if not normalized:
            return []

        parts = re.split(r"(?<=[.!?])\s+|\n+", normalized)
        candidates: List[str] = []
        seen = set()
        for raw_part in parts:
            candidate = raw_part.strip(" -:;,")
            if len(candidate) < 12 or len(candidate) > 220:
                continue
            if not self._is_promotable_candidate(candidate):
                continue
            lowered = candidate.lower()
            if not any(keyword in lowered for keyword in self.KEYWORDS):
                continue
            if lowered in seen:
                continue
            seen.add(lowered)
            candidates.append(candidate)
            if len(candidates) >= 2:
                break
        return candidates

    def _is_promotable_candidate(self, candidate: str) -> bool:
        lowered = candidate.lower()
        if any(pattern in lowered for pattern in self.NOISE_PATTERNS):
            return False
        if candidate.count('"') >= 2:
            return False
        if "*" in candidate:
            return False
        if re.search(r"[\U0001F300-\U0001FAFF]", candidate):
            return False
        if re.search(r"\b(I'll focus|Turn 1|raw prompt|thinking)\b", candidate, re.IGNORECASE):
            return False
        return True

    def _clean_memory_list(self, values: object) -> List[str]:
        if not isinstance(values, list):
            return []
        out: List[str] = []
        for value in values:
            if isinstance(value, str) and value.strip():
                out.append(value.strip())
        return out
