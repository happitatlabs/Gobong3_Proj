from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from mellow_chat_runtime.core.domain_lookup_store import DomainLookupStore


@dataclass
class LookupResult:
    name: str
    payload: Dict[str, Any] | List[Dict[str, Any]]


class DomainLookupDispatcher:
    """Lookup-only dispatcher. No filesystem/system/web tooling."""

    ALLOWED_LOOKUPS = {
        "lookup_persona",
        "lookup_user_profile",
        "lookup_user_character",
        "lookup_bot_character",
        "lookup_lorebook",
        "lookup_memories_possessions",
        "lookup_relationships",
        "lookup_world_state",
        "lookup_scene_state",
        "lookup_character_state",
        "lookup_session_state",
        "lookup_branch_state",
        "lookup_session_summary",
        "lookup_confirmed_facts",
        "lookup_user_note",
        "lookup_session_note",
        "lookup_dialogue_priority",
    }

    def __init__(self, store: DomainLookupStore) -> None:
        self._store = store

    def get_lookup_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "lookup_persona",
                "args": ["persona_id"],
            },
            {
                "name": "lookup_user_profile",
                "args": ["profile_id"],
            },
            {
                "name": "lookup_user_character",
                "args": ["character_id"],
            },
            {
                "name": "lookup_bot_character",
                "args": ["character_id"],
            },
            {
                "name": "lookup_lorebook",
                "args": ["topic"],
            },
            {
                "name": "lookup_memories_possessions",
                "args": ["character_id"],
            },
            {
                "name": "lookup_relationships",
                "args": ["character_id", "counterpart_ids"],
            },
            {
                "name": "lookup_world_state",
                "args": ["world_id"],
            },
            {
                "name": "lookup_scene_state",
                "args": ["scene_id"],
            },
            {
                "name": "lookup_character_state",
                "args": ["character_id"],
            },
            {
                "name": "lookup_session_state",
                "args": ["session_id"],
            },
            {
                "name": "lookup_branch_state",
                "args": ["branch_id"],
            },
            {
                "name": "lookup_session_summary",
                "args": ["session_id"],
            },
            {
                "name": "lookup_confirmed_facts",
                "args": ["session_id", "limit"],
            },
            {
                "name": "lookup_user_note",
                "args": ["profile_id"],
            },
            {
                "name": "lookup_session_note",
                "args": ["session_id"],
            },
            {
                "name": "lookup_dialogue_priority",
                "args": ["scene_id"],
            },
        ]

    def execute(self, name: str, args: Optional[Dict[str, Any]] = None) -> LookupResult:
        if name not in self.ALLOWED_LOOKUPS:
            raise ValueError(f"Unknown lookup: {name}")

        args = args or {}
        if name == "lookup_persona":
            return LookupResult(name=name, payload=self._store.get_persona(str(args.get("persona_id", "default"))))
        if name == "lookup_user_profile":
            return LookupResult(name=name, payload=self._store.get_user_profile(str(args.get("profile_id", ""))))
        if name == "lookup_user_character":
            return LookupResult(name=name, payload=self._store.get_user_character(str(args.get("character_id", ""))))
        if name == "lookup_bot_character":
            return LookupResult(name=name, payload=self._store.get_bot_character(str(args.get("character_id", ""))))
        if name == "lookup_lorebook":
            return LookupResult(name=name, payload=self._store.get_lore(str(args.get("topic", ""))))
        if name == "lookup_memories_possessions":
            return LookupResult(name=name, payload=self._store.get_memory_and_possessions(str(args.get("character_id", ""))))
        if name == "lookup_relationships":
            counterpart_ids = args.get("counterpart_ids")
            if not isinstance(counterpart_ids, list):
                counterpart_ids = []
            return LookupResult(
                name=name,
                payload=self._store.get_relationships(
                    str(args.get("character_id", "")),
                    counterpart_ids=[str(item) for item in counterpart_ids if str(item).strip()],
                ),
            )
        if name == "lookup_world_state":
            return LookupResult(name=name, payload=self._store.get_world_state(str(args.get("world_id", "default"))))
        if name == "lookup_scene_state":
            return LookupResult(name=name, payload=self._store.get_scene_state(str(args.get("scene_id", "scene_default"))))
        if name == "lookup_character_state":
            return LookupResult(name=name, payload=self._store.get_character_state(str(args.get("character_id", ""))))
        if name == "lookup_session_state":
            return LookupResult(name=name, payload=self._store.get_session_state(str(args.get("session_id", "default"))))
        if name == "lookup_branch_state":
            return LookupResult(name=name, payload=self._store.get_branch_state(str(args.get("branch_id", "default"))))
        if name == "lookup_session_summary":
            return LookupResult(name=name, payload=self._store.get_session_summary(str(args.get("session_id", "default"))))
        if name == "lookup_confirmed_facts":
            return LookupResult(name=name, payload=self._store.list_confirmed_facts(str(args.get("session_id", "default")), limit=int(args.get("limit", 8) or 8)))
        if name == "lookup_user_note":
            return LookupResult(name=name, payload=self._store.get_user_note(str(args.get("profile_id", "default"))))
        if name == "lookup_session_note":
            return LookupResult(name=name, payload=self._store.get_session_note(str(args.get("session_id", "default"))))
        return LookupResult(name=name, payload=self._store.get_dialogue_priority(str(args.get("scene_id", "default"))))
