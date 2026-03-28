from __future__ import annotations

from typing import Any, Dict, List


class BranchVisibilityService:
    def build_branch_context(self, branch_state: Dict[str, Any], session_state: Dict[str, Any]) -> Dict[str, Any]:
        branch_state = branch_state if isinstance(branch_state, dict) else {}
        session_state = session_state if isinstance(session_state, dict) else {}
        route_flags = branch_state.get('route_flags', {}) if isinstance(branch_state.get('route_flags'), dict) else {}
        unlock_conditions = branch_state.get('unlock_conditions', {}) if isinstance(branch_state.get('unlock_conditions'), dict) else {}
        current_branch_id = str(session_state.get('branch_id') or branch_state.get('branch_id') or 'default').strip() or 'default'
        revealed = {str(item).strip() for item in branch_state.get('hidden_facts_revealed', []) if str(item).strip()}
        hidden_facts = branch_state.get('hidden_facts', []) if isinstance(branch_state.get('hidden_facts'), list) else []
        visible_hidden_facts: List[Dict[str, Any]] = []
        hidden_fact_ids: List[str] = []
        for item in hidden_facts:
            if not isinstance(item, dict):
                continue
            fact_id = str(item.get('id') or '').strip()
            if not fact_id:
                continue
            if fact_id not in revealed:
                continue
            related_routes = [str(value).strip() for value in item.get('related_routes', []) if str(value).strip()] if isinstance(item.get('related_routes'), list) else []
            if related_routes and current_branch_id not in related_routes and not any(route_flags.get(route) for route in related_routes):
                continue
            visible_hidden_facts.append({
                'id': fact_id,
                'fact': str(item.get('fact') or '').strip(),
                'unlock_conditions': [str(value).strip() for value in item.get('unlock_conditions', []) if str(value).strip()] if isinstance(item.get('unlock_conditions'), list) else [],
                'related_routes': related_routes,
            })
            hidden_fact_ids.append(fact_id)
        if not hidden_facts and revealed:
            visible_hidden_facts = [{'id': fact_id, 'fact': fact_id, 'unlock_conditions': [], 'related_routes': [current_branch_id]} for fact_id in revealed]
        return {
            'branch_id': current_branch_id,
            'route_flags': {str(key): bool(value) for key, value in route_flags.items()},
            'unlock_conditions': {str(key): bool(value) for key, value in unlock_conditions.items()},
            'active_objectives': [str(item).strip() for item in branch_state.get('active_objectives', []) if str(item).strip()][:5],
            'visible_hidden_facts': visible_hidden_facts[:5],
            'hidden_fact_ids': hidden_fact_ids[:10],
        }
