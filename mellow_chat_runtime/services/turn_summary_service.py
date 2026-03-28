from __future__ import annotations

import re
from typing import Any, Dict, List

from mellow_chat_runtime.core.domain_lookup_store import DomainLookupStore


class TurnSummaryService:
    FACT_KEYWORDS = ('important', 'remember', 'decided', 'decision', 'promise', '계약', '중요', '결정', '약속', '진실')

    def __init__(self, domain_store: DomainLookupStore) -> None:
        self._domain_store = domain_store

    def record_turn(self, *, session_id: str, speaker_id: str, user_text: str, assistant_text: str, state_changes: Dict[str, Any]) -> Dict[str, Any]:
        cleaned_session_id = str(session_id or '').strip() or 'default'
        cleaned_speaker_id = str(speaker_id or '').strip()
        turn_index = self._next_turn_index(cleaned_session_id)
        summary_id = f'{cleaned_session_id}:{turn_index:04d}'
        item = {
            'id': summary_id,
            'session_id': cleaned_session_id,
            'turn_index': turn_index,
            'speaker_id': cleaned_speaker_id,
            'summary': self._build_summary(user_text, assistant_text),
            'facts': self._extract_facts(user_text, assistant_text, state_changes),
            'state_changes': state_changes if isinstance(state_changes, dict) else {},
        }
        self._domain_store.upsert('turn_summary', summary_id, item)
        return item

    def list_for_session(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        cleaned_session_id = str(session_id or '').strip() or 'default'
        items = [item for item in self._domain_store.list_section('turn_summary').values() if str(item.get('session_id') or '').strip() == cleaned_session_id]
        items.sort(key=lambda item: int(item.get('turn_index') or 0))
        if limit > 0:
            items = items[-limit:]
        return items

    def _next_turn_index(self, session_id: str) -> int:
        existing = self.list_for_session(session_id, limit=0)
        if not existing:
            return 1
        return max(int(item.get('turn_index') or 0) for item in existing) + 1

    def _build_summary(self, user_text: str, assistant_text: str) -> str:
        excerpt = self._first_sentence(assistant_text) or self._first_sentence(user_text)
        return excerpt[:160]

    def _extract_facts(self, user_text: str, assistant_text: str, state_changes: Dict[str, Any]) -> List[str]:
        facts: List[str] = []
        for section_name in ('character', 'session', 'branch'):
            section = state_changes.get(section_name, {}) if isinstance(state_changes, dict) else {}
            if not isinstance(section, dict):
                continue
            for key, value in section.items():
                if isinstance(value, list):
                    for item in value:
                        facts.append(f'{section_name}.{key}:{item}')
                elif isinstance(value, dict):
                    for nested_key, nested_value in value.items():
                        facts.append(f'{section_name}.{key}.{nested_key}:{nested_value}')
                else:
                    facts.append(f'{section_name}.{key}:{value}')
        for candidate in self._candidate_sentences(user_text) + self._candidate_sentences(assistant_text):
            if candidate not in facts:
                facts.append(candidate)
            if len(facts) >= 6:
                break
        return facts[:6]

    def _candidate_sentences(self, text: str) -> List[str]:
        normalized = re.sub(r'\s+', ' ', str(text or '').strip())
        if not normalized:
            return []
        out: List[str] = []
        for part in re.split(r'(?<=[.!?])\s+|\n+', normalized):
            candidate = part.strip(' -:;,')
            lowered = candidate.lower()
            if len(candidate) < 10:
                continue
            if not any(keyword in lowered for keyword in self.FACT_KEYWORDS):
                continue
            out.append(candidate[:140])
            if len(out) >= 2:
                break
        return out

    def _first_sentence(self, text: str) -> str:
        normalized = re.sub(r'\s+', ' ', str(text or '').strip())
        if not normalized:
            return ''
        for part in re.split(r'(?<=[.!?])\s+|\n+', normalized):
            candidate = part.strip(' -:;,"')
            if candidate:
                return candidate
        return normalized[:160]
