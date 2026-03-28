from __future__ import annotations

import re
from typing import Any, Dict, List

from mellow_chat_runtime.core.domain_lookup_store import DomainLookupStore


class ConfirmedFactsService:
    def __init__(self, domain_store: DomainLookupStore, max_items: int = 12) -> None:
        self._domain_store = domain_store
        self._max_items = max(1, int(max_items or 12))

    def update_from_turn(self, turn_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(turn_summary, dict):
            return []
        session_id = str(turn_summary.get('session_id') or '').strip() or 'default'
        source_turn_id = str(turn_summary.get('id') or '').strip()
        speaker_id = str(turn_summary.get('speaker_id') or '').strip()
        existing = self.list_for_session(session_id, limit=0)
        existing_by_fact = {str(item.get('fact') or '').strip().lower(): item for item in existing}
        updated: List[Dict[str, Any]] = list(existing)
        changed = False
        for fact in self._normalize_facts(turn_summary.get('facts', [])):
            key = fact.lower()
            confidence = self._estimate_confidence(fact)
            if key in existing_by_fact:
                item = dict(existing_by_fact[key])
                if confidence > float(item.get('confidence') or 0.0):
                    item['confidence'] = confidence
                    item['source_turn_id'] = source_turn_id or str(item.get('source_turn_id') or '')
                    existing_by_fact[key] = item
                    changed = True
                continue
            item_id = f'{session_id}:{self._fact_key(fact)}'
            item = {
                'id': item_id,
                'session_id': session_id,
                'fact': fact,
                'source_turn_id': source_turn_id,
                'confidence': confidence,
                'related_characters': [speaker_id] if speaker_id else [],
                'summary_text': fact,
            }
            existing_by_fact[key] = item
            updated.append(item)
            changed = True
        if changed:
            updated.sort(key=lambda item: (-float(item.get('confidence') or 0.0), str(item.get('id') or '')))
            updated = updated[: self._max_items]
            self._replace_session_facts(session_id, updated)
        return self.list_for_session(session_id)

    def list_for_session(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        cleaned_session_id = str(session_id or '').strip() or 'default'
        items = [
            item for item in self._domain_store.list_section('confirmed_facts').values()
            if str(item.get('session_id') or '').strip() == cleaned_session_id
        ]
        items.sort(key=lambda item: (-float(item.get('confidence') or 0.0), str(item.get('id') or '')))
        if limit > 0:
            items = items[:limit]
        return items

    def _replace_session_facts(self, session_id: str, items: List[Dict[str, Any]]) -> None:
        existing = self.list_for_session(session_id, limit=0)
        existing_ids = {str(item.get('id') or '').strip() for item in existing}
        kept_ids = {str(item.get('id') or '').strip() for item in items}
        for item in items:
            item_id = str(item.get('id') or '').strip()
            if item_id:
                self._domain_store.upsert('confirmed_facts', item_id, item)
        for stale_id in existing_ids - kept_ids:
            self._domain_store.delete('confirmed_facts', stale_id)

    def _normalize_facts(self, values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        out: List[str] = []
        seen = set()
        for value in values:
            cleaned = str(value or '').strip()
            if len(cleaned) < 8:
                continue
            lowered = cleaned.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            out.append(cleaned[:180])
        return out

    def _estimate_confidence(self, fact: str) -> float:
        lowered = str(fact or '').lower()
        if lowered.startswith('character.') or lowered.startswith('session.') or lowered.startswith('branch.'):
            return 0.95
        if any(token in lowered for token in ('important', 'remember', '계약', '중요', '결정', '진실')):
            return 0.82
        return 0.72

    def _fact_key(self, fact: str) -> str:
        lowered = re.sub(r'[^a-z0-9가-힣]+', '_', str(fact or '').lower()).strip('_')
        return lowered[:48] or 'fact'
