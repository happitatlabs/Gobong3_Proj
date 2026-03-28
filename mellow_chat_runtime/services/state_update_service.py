from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from mellow_chat_runtime.core.domain_lookup_store import DomainLookupStore


class StateUpdateService:
    EMOTION_PATTERNS = (
        ('guarded', (r'guarded', r'경계', r'굳', r'눈을 좁', r'긴장')),
        ('calm', (r'calm', r'차분', r'steady', r'measured', r'숨을 고르')),
        ('confident', (r'confident', r'자신', r'태연', r'여유')),
        ('angry', (r'angry', r'분노', r'날을 세우', r'짜증')),
    )
    LOCATION_PATTERNS = (
        ('VIP booth', (r'vip booth',)),
        ('Astral lounge deck', (r'astral lounge deck',)),
        ('Lounge', (r'\blounge\b', r'라운지')),
    )
    OUTFIT_PATTERNS = (
        ('black suit', (r'black suit',)),
        ('IPC formalwear', (r'ipc formalwear',)),
        ('ceremonial formalwear', (r'ceremonial formalwear',)),
    )
    PHASE_PATTERNS = (
        ('high_alert', (r'high alert', r'보안', r'경계', r'긴장')),
        ('negotiation', (r'negotiat', r'협상', r'딜')),
        ('opening', (r'opening', r'처음 장면', r'시작')),
    )
    BRANCH_PATTERNS = (
        ('confession_route', (r'confession', r'고백')),
    )
    HIDDEN_FACT_PATTERNS = (
        ('ipc_contract_truth', (r'ipc_contract_truth', r'contract truth', r'계약의 진실', r'계약 진실')),
    )

    def __init__(self, domain_store: DomainLookupStore) -> None:
        self._domain_store = domain_store

    def apply_turn(self, *, session_id: str, character_id: str, user_text: str, assistant_text: str, scene_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cleaned_session_id = str(session_id or '').strip() or 'default'
        cleaned_character_id = str(character_id or '').strip()
        scene_state = scene_state if isinstance(scene_state, dict) else {}
        current_character = self._domain_store.get_character_state(cleaned_character_id) if cleaned_character_id else {}
        current_session = self._domain_store.get_session_state(cleaned_session_id)
        current_branch_id = str(current_session.get('branch_id') or 'default').strip() or 'default'
        current_branch = self._domain_store.get_branch_state(current_branch_id)
        combined_text = ' '.join(part for part in [user_text, assistant_text] if str(part or '').strip())
        assistant_focus = str(assistant_text or '').strip() or combined_text
        character_payload = dict(current_character or {})
        session_payload = dict(current_session or {})
        branch_payload = dict(current_branch or {})
        character_changes: Dict[str, Any] = {}
        session_changes: Dict[str, Any] = {}
        branch_changes: Dict[str, Any] = {}

        current_emotion = str(character_payload.get('emotion') or 'neutral').strip() or 'neutral'
        detected_emotion = self._detect_label(assistant_focus, self.EMOTION_PATTERNS)
        if detected_emotion and self._should_replace_emotion(current_emotion, detected_emotion):
            character_payload['emotion'] = detected_emotion
            character_changes['emotion'] = detected_emotion

        detected_location = self._detect_location(combined_text, scene_state=scene_state, current_character=character_payload, current_session=session_payload)
        if detected_location and detected_location != str(character_payload.get('location') or ''):
            character_payload['location'] = detected_location
            character_changes['location'] = detected_location
        if detected_location and detected_location != str(session_payload.get('active_location') or ''):
            session_payload['active_location'] = detected_location
            session_changes['active_location'] = detected_location

        detected_outfit = self._detect_label(assistant_focus, self.OUTFIT_PATTERNS)
        if detected_outfit and detected_outfit != str(character_payload.get('outfit') or ''):
            character_payload['outfit'] = detected_outfit
            character_changes['outfit'] = detected_outfit

        character_flags = dict(character_payload.get('scene_flags') or {}) if isinstance(character_payload.get('scene_flags'), dict) else {}
        session_flags = dict(session_payload.get('scene_flags') or {}) if isinstance(session_payload.get('scene_flags'), dict) else {}
        route_flags = dict(branch_payload.get('route_flags') or {}) if isinstance(branch_payload.get('route_flags'), dict) else {}
        unlock_conditions = dict(branch_payload.get('unlock_conditions') or {}) if isinstance(branch_payload.get('unlock_conditions'), dict) else {}
        hidden_fact_entries = branch_payload.get('hidden_facts', []) if isinstance(branch_payload.get('hidden_facts'), list) else []

        if detected_emotion == 'guarded' and character_flags.get('guarded') is not True:
            character_flags['guarded'] = True
            character_changes.setdefault('scene_flags', {})['guarded'] = True
        if self._contains_any(combined_text, (r'high alert', r'보안', r'경계', r'긴장')) and session_flags.get('high_alert') is not True:
            session_flags['high_alert'] = True
            session_changes.setdefault('scene_flags', {})['high_alert'] = True
            unlock_conditions['high_alert'] = True

        detected_phase = self._detect_label(combined_text, self.PHASE_PATTERNS)
        if detected_phase and detected_phase != str(session_payload.get('active_phase') or ''):
            session_payload['active_phase'] = detected_phase
            session_changes['active_phase'] = detected_phase

        detected_branch_id = self._detect_label(combined_text, self.BRANCH_PATTERNS)
        if detected_branch_id:
            if detected_branch_id != str(session_payload.get('branch_id') or 'default'):
                session_payload['branch_id'] = detected_branch_id
                session_changes['branch_id'] = detected_branch_id
            if detected_branch_id != current_branch_id:
                branch_payload = self._domain_store.get_branch_state(detected_branch_id)
                route_flags = dict(branch_payload.get('route_flags') or {}) if isinstance(branch_payload.get('route_flags'), dict) else {}
                unlock_conditions = dict(branch_payload.get('unlock_conditions') or {}) if isinstance(branch_payload.get('unlock_conditions'), dict) else {}
                hidden_fact_entries = branch_payload.get('hidden_facts', []) if isinstance(branch_payload.get('hidden_facts'), list) else []
            if route_flags.get(detected_branch_id) is not True:
                route_flags[detected_branch_id] = True
                branch_changes.setdefault('route_flags', {})[detected_branch_id] = True
            if unlock_conditions.get(detected_branch_id) is not True:
                unlock_conditions[detected_branch_id] = True
                branch_changes.setdefault('unlock_conditions', {})[detected_branch_id] = True

        hidden_facts = list(branch_payload.get('hidden_facts_revealed', [])) if isinstance(branch_payload.get('hidden_facts_revealed'), list) else []
        newly_revealed: List[str] = []
        for item in hidden_fact_entries:
            if not isinstance(item, dict):
                continue
            fact_id = str(item.get('id') or '').strip()
            if not fact_id or fact_id in hidden_facts:
                continue
            reveal_patterns = [str(value).strip() for value in item.get('reveal_patterns', []) if str(value).strip()] if isinstance(item.get('reveal_patterns'), list) else []
            unlock_refs = [str(value).strip() for value in item.get('unlock_conditions', []) if str(value).strip()] if isinstance(item.get('unlock_conditions'), list) else []
            if reveal_patterns and not self._contains_any(combined_text, tuple(reveal_patterns)):
                continue
            if not self._unlock_conditions_met(unlock_refs, route_flags=route_flags, unlock_conditions=unlock_conditions, session_flags=session_flags):
                continue
            hidden_facts.append(fact_id)
            newly_revealed.append(fact_id)
        for fact_id, patterns in self.HIDDEN_FACT_PATTERNS:
            if hidden_fact_entries and any(str(item.get('id') or '').strip() == fact_id for item in hidden_fact_entries if isinstance(item, dict)):
                continue
            if self._contains_any(combined_text, patterns) and fact_id not in hidden_facts:
                hidden_facts.append(fact_id)
                newly_revealed.append(fact_id)
        if newly_revealed:
            branch_changes['hidden_facts_revealed'] = newly_revealed

        character_notes = self._merge_notes(character_payload.get('status_notes', []), [
            f'emotion={character_changes["emotion"]}' if 'emotion' in character_changes else '',
            f'location={character_changes["location"]}' if 'location' in character_changes else '',
            f'outfit={character_changes["outfit"]}' if 'outfit' in character_changes else '',
        ])
        session_notes = self._merge_notes(session_payload.get('status_notes', []), [
            f'phase={session_changes["active_phase"]}' if 'active_phase' in session_changes else '',
            f'branch={session_changes["branch_id"]}' if 'branch_id' in session_changes else '',
            f'revealed={"|".join(newly_revealed)}' if newly_revealed else '',
        ])

        if character_changes:
            character_payload['character_id'] = cleaned_character_id
            character_payload['scene_flags'] = character_flags
            character_payload['status_notes'] = character_notes
            self._domain_store.upsert_character_state(cleaned_character_id, character_payload)
        if session_changes:
            session_payload['session_id'] = cleaned_session_id
            session_payload['scene_flags'] = session_flags
            session_payload['status_notes'] = session_notes
            self._domain_store.upsert_session_state(cleaned_session_id, session_payload)
        if branch_changes:
            branch_id = str(session_payload.get('branch_id') or current_branch_id or 'default').strip() or 'default'
            branch_payload = dict(branch_payload or {})
            branch_payload['branch_id'] = branch_id
            branch_payload['route_flags'] = route_flags
            branch_payload['unlock_conditions'] = unlock_conditions
            branch_payload['hidden_facts_revealed'] = hidden_facts
            branch_payload.setdefault('hidden_facts', hidden_fact_entries if isinstance(hidden_fact_entries, list) else [])
            branch_payload.setdefault('active_objectives', [])
            self._domain_store.upsert_branch_state(branch_id, branch_payload)

        out: Dict[str, Any] = {}
        if character_changes:
            out['character'] = character_changes
        if session_changes:
            out['session'] = session_changes
        if branch_changes:
            out['branch'] = branch_changes
        return out

    def _should_replace_emotion(self, current_emotion: str, detected_emotion: str) -> bool:
        if detected_emotion == current_emotion:
            return False
        if current_emotion in ('', 'neutral'):
            return True
        if detected_emotion in ('guarded', 'angry'):
            return True
        return False

    def _detect_location(self, text: str, *, scene_state: Dict[str, Any], current_character: Dict[str, Any], current_session: Dict[str, Any]) -> Optional[str]:
        normalized = str(text or '')
        for label, patterns in self.LOCATION_PATTERNS:
            if self._contains_any(normalized, patterns):
                return label
        for candidate in [str(scene_state.get('location') or '').strip(), str(current_session.get('active_location') or '').strip(), str(current_character.get('location') or '').strip()]:
            if candidate and candidate.lower() in normalized.lower():
                return candidate
        return None

    def _detect_label(self, text: str, patterns: Any) -> Optional[str]:
        normalized = str(text or '')
        for label, label_patterns in patterns:
            if self._contains_any(normalized, label_patterns):
                return label
        return None

    def _unlock_conditions_met(self, refs: List[str], *, route_flags: Dict[str, Any], unlock_conditions: Dict[str, Any], session_flags: Dict[str, Any]) -> bool:
        if not refs:
            return True
        for ref in refs:
            cleaned = str(ref or '').strip()
            if not cleaned:
                continue
            if route_flags.get(cleaned) or unlock_conditions.get(cleaned) or session_flags.get(cleaned):
                continue
            return False
        return True

    def _contains_any(self, text: str, patterns: Any) -> bool:
        normalized = str(text or '')
        return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns)

    def _merge_notes(self, existing: Any, candidates: List[str]) -> List[str]:
        values = [str(item).strip() for item in existing if str(item).strip()] if isinstance(existing, list) else []
        seen = {item.lower() for item in values}
        for candidate in candidates:
            cleaned = str(candidate).strip()
            if not cleaned or cleaned.lower() in seen:
                continue
            values.append(cleaned)
            seen.add(cleaned.lower())
        return values[-3:]
