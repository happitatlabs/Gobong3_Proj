from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TurnRequestUser(BaseModel):
    id: str


class TurnRequestInput(BaseModel):
    text: str
    locale: Optional[str] = None


class TurnRequestContext(BaseModel):
    character_id: Optional[str] = "default"
    model_tier_requested: Optional[str] = "free"
    metadata: Optional[Dict[str, Any]] = None


class TurnRequest(BaseModel):
    session_id: str
    user: TurnRequestUser
    input: TurnRequestInput
    context: Optional[TurnRequestContext] = None


class TurnPayload(BaseModel):
    id: str
    speech: str = ""
    passage: Optional[str] = None


class TurnState(BaseModel):
    session_id: str
    state_version: int = 1
    system_state: str = "IDLE"
    model_tier_effective: str = "free"


class TurnMeta(BaseModel):
    trace_id: str
    runtime_impl: str
    latency_ms: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TurnResponse(BaseModel):
    turn: TurnPayload
    state: TurnState
    meta: TurnMeta


class StatusRuntime(BaseModel):
    impl: str
    version: str
    uptime_sec: float


class StatusHealth(BaseModel):
    system_state: str
    last_error: Optional[str] = None


class StatusResponse(BaseModel):
    runtime: StatusRuntime
    health: StatusHealth
    time: datetime = Field(default_factory=datetime.utcnow)


class ErrorDetail(BaseModel):
    code: str
    message: str
    trace_id: Optional[str] = None


class ErrorBody(BaseModel):
    error: ErrorDetail


class RetrievalDebug(BaseModel):
    query: Optional[str] = None
    lore_source: Optional[Literal["vector", "fallback", "none", "canonical"]] = None
    memory_source: Optional[Literal["vector", "fallback", "none", "canonical"]] = None
    relationship_source: Optional[Literal["vector", "fallback", "none", "canonical"]] = None
    lore_hit_ids: List[str] = Field(default_factory=list)
    memory_hit_ids: List[str] = Field(default_factory=list)
    relationship_hit_ids: List[str] = Field(default_factory=list)
    lore_scores: Dict[str, float] = Field(default_factory=dict)
    memory_scores: Dict[str, float] = Field(default_factory=dict)
    relationship_scores: Dict[str, float] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    fallback_used: Optional[bool] = None


class RPDebug(BaseModel):
    validator_passed: Optional[bool] = None
    fallback_used: Optional[bool] = None
    retry_count: Optional[int] = None
    final_verdict: Optional[str] = None
    failure_reason: Optional[str] = None
    failure_reasons: List[str] = Field(default_factory=list)


class PromptWatchContextItem(BaseModel):
    id: Optional[str] = None
    source: Optional[str] = None
    topic: Optional[str] = None
    character_id: Optional[str] = None
    target_id: Optional[str] = None
    summary_text: str = ""


class PromptWatchModelInfo(BaseModel):
    provider: str
    model: str
    mode: str
    source: Literal["explicit_request", "catalog", "session", "system_default"]
    catalog_id: Optional[str] = None
    label: Optional[str] = None
    role_tags: List[str] = Field(default_factory=list)


class PromptWatchGenerationPath(BaseModel):
    validator_passed: Optional[bool] = None
    repair_used: bool = False
    fallback_used: bool = False
    retry_count: int = 0
    final_verdict: Literal["pass", "repaired", "fallback", "failed"] = "failed"
    failure_reason: Optional[str] = None


class PromptWatchCompact(BaseModel):
    active_character_id: Optional[str] = None
    active_character_name: Optional[str] = None
    selected_speaker_id: Optional[str] = None
    selected_speaker_type: Optional[str] = None
    scene_id: str
    world_id: str
    input_mode: Optional[str] = None
    target_character_hint: Optional[str] = None
    lore_hit_ids: List[str] = Field(default_factory=list)
    memory_hit_ids: List[str] = Field(default_factory=list)
    relationship_hit_ids: List[str] = Field(default_factory=list)
    model: PromptWatchModelInfo
    repair_used: bool = False
    fallback_used: bool = False


class PromptWatchSceneContext(BaseModel):
    goal: str = ""
    mood: str = ""


class PromptWatchAppliedContext(BaseModel):
    lore: List[PromptWatchContextItem] = Field(default_factory=list)
    memories: List[PromptWatchContextItem] = Field(default_factory=list)
    relationships: List[PromptWatchContextItem] = Field(default_factory=list)
    scene: PromptWatchSceneContext = Field(default_factory=PromptWatchSceneContext)


class PromptWatchDetail(PromptWatchCompact):
    applied_persona_id: Optional[str] = None
    applied_user_profile_id: Optional[str] = None
    generation_path: PromptWatchGenerationPath = Field(default_factory=PromptWatchGenerationPath)
    applied_context: PromptWatchAppliedContext = Field(default_factory=PromptWatchAppliedContext)


class ChatAskResponseModel(BaseModel):
    response: str
    session_id: int
    message_id: int
    speaker_id: Optional[str] = None
    speaker_type: Optional[str] = None
    model_provider: str
    model_name: str
    selected_mode: str
    processing_time_ms: int
    used_context: Dict[str, Any] = Field(default_factory=dict)
    model: Dict[str, Any] = Field(default_factory=dict)
    prompt_watch: Optional[PromptWatchCompact] = None
    request_id: str


class ChatAskAdminResponseModel(ChatAskResponseModel):
    prompt_watch: Optional[PromptWatchDetail] = None
    retrieval_debug: Optional[RetrievalDebug] = None
    rp_debug: Optional[RPDebug] = None


class VectorReindexResponse(BaseModel):
    entity_type: Literal["lore", "memory", "relationship"]
    entity_id: str
    status: Literal["queued", "reindexed"]
