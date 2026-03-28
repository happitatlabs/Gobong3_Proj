from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class SpeechStyle(BaseModel):
    tone: str = "neutral"
    forbidden: List[str] = Field(default_factory=list)


class UserCharacter(BaseModel):
    id: str
    type: str = "user"
    name: str
    profile: str = ""
    traits: List[str] = Field(default_factory=list)
    relationship_keys: List[str] = Field(default_factory=list)
    is_major: bool = True


class BotCharacter(BaseModel):
    id: str
    type: str = "bot"
    name: str
    persona_id: str = "default"
    speech_style: SpeechStyle = Field(default_factory=SpeechStyle)
    relationship_keys: List[str] = Field(default_factory=list)
    is_major: bool = True


class LorebookEntry(BaseModel):
    id: str
    topic: str
    aliases: List[str] = Field(default_factory=list)
    content: str
    priority: int = 0
    summary_text: Optional[str] = None
    embedding_status: Optional[Literal["pending", "dirty", "ready", "failed"]] = None


class SceneRule(BaseModel):
    key: str
    value: Any


class SceneState(BaseModel):
    id: str
    location: str
    time: str
    participants: List[str] = Field(default_factory=list)
    goal: str = ""
    mood: str = "neutral"
    rules: List[SceneRule] = Field(default_factory=list)


class WorldState(BaseModel):
    id: str
    location: str = ""
    time: str = ""
    state: str = "stable"
    facts: List[str] = Field(default_factory=list)


class CharacterState(BaseModel):
    character_id: str
    emotion: str = "neutral"
    location: str = ""
    outfit: str = ""
    scene_flags: Dict[str, bool] = Field(default_factory=dict)
    relationship_delta: Dict[str, float] = Field(default_factory=dict)
    status_notes: List[str] = Field(default_factory=list)


class SessionState(BaseModel):
    session_id: str
    branch_id: str = "default"
    active_location: str = ""
    active_phase: str = ""
    scene_flags: Dict[str, bool] = Field(default_factory=dict)
    status_notes: List[str] = Field(default_factory=list)


class HiddenFactEntry(BaseModel):
    id: str
    fact: str
    unlock_conditions: List[str] = Field(default_factory=list)
    reveal_patterns: List[str] = Field(default_factory=list)
    related_routes: List[str] = Field(default_factory=list)


class BranchState(BaseModel):
    branch_id: str = "default"
    route_flags: Dict[str, bool] = Field(default_factory=dict)
    unlock_conditions: Dict[str, bool] = Field(default_factory=dict)
    hidden_facts_revealed: List[str] = Field(default_factory=list)
    hidden_facts: List[HiddenFactEntry] = Field(default_factory=list)
    active_objectives: List[str] = Field(default_factory=list)


class TurnSummary(BaseModel):
    id: str
    session_id: str
    turn_index: int
    speaker_id: str = ""
    summary: str = ""
    facts: List[str] = Field(default_factory=list)
    state_changes: Dict[str, Any] = Field(default_factory=dict)


class SessionSummary(BaseModel):
    session_id: str
    turn_count: int = 0
    summary: str = ""
    recent_turn_ids: List[str] = Field(default_factory=list)
    summary_text: Optional[str] = None


class ConfirmedFact(BaseModel):
    id: str
    session_id: str
    fact: str
    source_turn_id: str = ""
    confidence: float = 0.0
    related_characters: List[str] = Field(default_factory=list)
    summary_text: Optional[str] = None


class UserNote(BaseModel):
    profile_id: str
    note: str = ""
    hard_constraints: List[str] = Field(default_factory=list)
    preferred_dynamic: List[str] = Field(default_factory=list)
    relationship_expectation: str = ""


class SessionNote(BaseModel):
    session_id: str
    note: str = ""
    hard_constraints: List[str] = Field(default_factory=list)
    preferred_dynamic: List[str] = Field(default_factory=list)
    relationship_expectation: str = ""


class MemoryPossession(BaseModel):
    character_id: str
    important_memories: List[str] = Field(default_factory=list)
    possessions: List[str] = Field(default_factory=list)
    summary_text: Optional[str] = None
    embedding_status: Optional[Literal["pending", "dirty", "ready", "failed"]] = None


class RelationshipContext(BaseModel):
    target_id: str
    summary: str = ""
    tone: str = "neutral"
    boundaries: List[str] = Field(default_factory=list)
    shared_memories: List[str] = Field(default_factory=list)
    summary_text: Optional[str] = None
    embedding_status: Optional[Literal["pending", "dirty", "ready", "failed"]] = None


class DialoguePriority(BaseModel):
    scene_id: str
    major_weight: float = 1.0
    minor_weight: float = 0.5
    recency_penalty: float = 0.25
    max_consecutive_turns: int = 1
    rules: str = ""


class ModelCatalogEntry(BaseModel):
    id: str
    label: str
    provider: str
    model: str
    default_mode: str
    role_tags: List[str] = Field(default_factory=list)
    audiences: List[Literal["user", "admin"]] = Field(default_factory=list)
    status: Literal["active", "deprecated"] = "active"
    description: str = ""

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not re.fullmatch(r"[a-z0-9_-]+", cleaned):
            raise ValueError("id must contain only lowercase letters, digits, '_' or '-'")
        return cleaned

    @field_validator("audiences")
    @classmethod
    def validate_audiences(cls, value: List[Literal["user", "admin"]]) -> List[Literal["user", "admin"]]:
        if not value:
            raise ValueError("audiences must not be empty")
        return value


class DomainDataBundle(BaseModel):
    personas: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    user_characters: Dict[str, UserCharacter] = Field(default_factory=dict)
    bot_characters: Dict[str, BotCharacter] = Field(default_factory=dict)
    lorebook: Dict[str, LorebookEntry] = Field(default_factory=dict)
    scene_state: Dict[str, SceneState] = Field(default_factory=dict)
    world_state: Dict[str, WorldState] = Field(default_factory=dict)
    character_state: Dict[str, CharacterState] = Field(default_factory=dict)
    session_state: Dict[str, SessionState] = Field(default_factory=dict)
    branch_state: Dict[str, BranchState] = Field(default_factory=dict)
    turn_summary: Dict[str, TurnSummary] = Field(default_factory=dict)
    session_summary: Dict[str, SessionSummary] = Field(default_factory=dict)
    confirmed_facts: Dict[str, ConfirmedFact] = Field(default_factory=dict)
    user_notes: Dict[str, UserNote] = Field(default_factory=dict)
    session_notes: Dict[str, SessionNote] = Field(default_factory=dict)
    memories: Dict[str, MemoryPossession] = Field(default_factory=dict)
    relationships: Dict[str, Dict[str, RelationshipContext]] = Field(default_factory=dict)
    dialogue_priority: Dict[str, DialoguePriority] = Field(default_factory=dict)
    user_profiles: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    model_catalog: Dict[str, ModelCatalogEntry] = Field(default_factory=dict)
