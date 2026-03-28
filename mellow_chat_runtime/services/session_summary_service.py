from __future__ import annotations

from typing import Any, Dict, List

from mellow_chat_runtime.core.domain_lookup_store import DomainLookupStore
from mellow_chat_runtime.services.turn_summary_service import TurnSummaryService


class SessionSummaryService:
    def __init__(self, domain_store: DomainLookupStore, max_turns: int = 6) -> None:
        self._domain_store = domain_store
        self._turn_summary_service = TurnSummaryService(domain_store)
        self._max_turns = max(1, int(max_turns or 6))

    def rebuild_for_session(self, session_id: str) -> Dict[str, Any]:
        cleaned_session_id = str(session_id or '').strip() or 'default'
        turns = self._turn_summary_service.list_for_session(cleaned_session_id, limit=self._max_turns)
        summary_lines: List[str] = []
        recent_turn_ids: List[str] = []
        for item in turns:
            summary = str(item.get('summary') or '').strip()
            if not summary:
                continue
            recent_turn_ids.append(str(item.get('id') or '').strip())
            speaker_id = str(item.get('speaker_id') or '').strip()
            prefix = f'[{speaker_id}] ' if speaker_id else ''
            summary_lines.append(prefix + summary)
        summary_text = ' | '.join(summary_lines[: self._max_turns])
        payload = {
            'session_id': cleaned_session_id,
            'turn_count': len(turns),
            'summary': summary_text,
            'recent_turn_ids': recent_turn_ids,
            'summary_text': summary_text,
        }
        self._domain_store.upsert('session_summary', cleaned_session_id, payload)
        return payload

    def get_for_session(self, session_id: str) -> Dict[str, Any]:
        cleaned_session_id = str(session_id or '').strip() or 'default'
        item = self._domain_store.get_section_item('session_summary', cleaned_session_id)
        if item:
            return item
        return {
            'session_id': cleaned_session_id,
            'turn_count': 0,
            'summary': '',
            'recent_turn_ids': [],
            'summary_text': '',
        }
