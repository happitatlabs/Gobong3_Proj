from __future__ import annotations

import re
from typing import Any, Dict, List


class ContradictionCheckService:
    NEGATION_PATTERNS = (r"\bnot\b", r"\bnever\b", r"없", r"아니", r"못", r"no ")

    def detect(self, text: str, confirmed_facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = str(text or '').strip()
        if not normalized or not isinstance(confirmed_facts, list):
            return []
        candidates = self._candidate_sentences(normalized)
        findings: List[Dict[str, Any]] = []
        for candidate in candidates:
            candidate_tokens = self._tokens(candidate)
            candidate_negated = self._is_negated(candidate)
            for fact in confirmed_facts:
                fact_text = str(fact.get('fact') or '').strip()
                if not fact_text:
                    continue
                overlap = candidate_tokens & self._tokens(fact_text)
                if len(overlap) < 2:
                    continue
                fact_negated = self._is_negated(fact_text)
                if candidate_negated == fact_negated:
                    continue
                findings.append({
                    'candidate': candidate,
                    'fact': fact_text,
                    'source_turn_id': str(fact.get('source_turn_id') or '').strip() or None,
                    'overlap_tokens': sorted(overlap),
                })
                if len(findings) >= 5:
                    return findings
        return findings

    def _candidate_sentences(self, text: str) -> List[str]:
        parts = re.split(r'(?<=[.!?])\s+|\n+', text)
        return [part.strip(' -:;,"')[:180] for part in parts if len(part.strip()) >= 8]

    def _tokens(self, text: str) -> set[str]:
        return {token for token in re.findall(r'[a-z0-9가-힣_]+', str(text or '').lower()) if len(token) >= 2}

    def _is_negated(self, text: str) -> bool:
        lowered = str(text or '').lower()
        return any(re.search(pattern, lowered) for pattern in self.NEGATION_PATTERNS)
