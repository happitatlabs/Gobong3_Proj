from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from mellow_chat_runtime import app_state
from mellow_chat_runtime.core.domain_lookup_store import get_domain_store
from mellow_chat_runtime.core.prompt_builder import _build_branch_context_block, _build_dynamic_state_block
from mellow_chat_runtime.core.rp_parser import ParsedSceneEvent, parse_scene_event
from mellow_chat_runtime.core.speaker_relevance import build_speaker_relevance
from mellow_chat_runtime.core.speaker_selector import SpeakerParticipant, select_next_speaker
from mellow_chat_runtime.core.states import SystemState, TransitionResult
from mellow_chat_runtime.core.text_sanitizer import sanitize_assistant_text, sanitize_history_text
from mellow_chat_runtime.infra.database import (
    ChatMessage,
    ChatSession,
    MessageFeedback,
    get_db,
    get_or_create_session,
    get_or_create_user,
)
from mellow_chat_runtime.services.memory_promotion_service import MemoryPromotionService
from mellow_chat_runtime.services.state_update_service import StateUpdateService
from mellow_chat_runtime.services.session_summary_service import SessionSummaryService
from mellow_chat_runtime.services.confirmed_facts_service import ConfirmedFactsService
from mellow_chat_runtime.services.contradiction_check_service import ContradictionCheckService
from mellow_chat_runtime.services.model_routing_service import ModelRoutingService
from mellow_chat_runtime.services.summary_formatter import build_prompt_watch_summary
from mellow_chat_runtime.services.turn_summary_service import TurnSummaryService
from mellow_chat_runtime.services.vector_retrieval_service import RetrievalQueryContext, VectorRetrievalService

router = APIRouter(tags=['Chat'])
model_router = ModelRoutingService(default_provider='ollama')
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    question: str = Field(...)
    audience: str = Field('user')
    mode: str = Field('fast')
    provider: Optional[str] = None
    model: Optional[str] = None
    catalog_id: Optional[str] = None
    session_id: Optional[int] = None
    stream: bool = True
    persona_id: str = 'default'
    user_profile_id: str = 'default'
    lore_topic: str = 'default'
    lore_topics: Optional[List[str]] = None
    character_id: str = 'default'
    character_ids: Optional[List[str]] = None
    world_id: str = 'default'
    scene_id: str = 'default'


class SessionParticipantsRequest(BaseModel):
    user_character_ids: List[str] = Field(default_factory=list)
    bot_character_ids: List[str] = Field(default_factory=list)


class SessionParticipantsResponse(BaseModel):
    session_id: int
    user_character_ids: List[str] = Field(default_factory=list)
    bot_character_ids: List[str] = Field(default_factory=list)


class ChatErrorResponse(BaseModel):
    error: str
    message: str
    request_id: str


class ChatValidationFailureResponse(BaseModel):
    success: bool
    error_code: str
    message: str
    request_id: str
    failure_reason: str


def _user_from_header(x_user: Optional[str]) -> str:
    return (x_user or 'default_user').strip() or 'default_user'


def _parse_json_list(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: List[str] = []
    for item in data:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                out.append(cleaned)
    return out


def _compact_unique(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _resolve_lore_keys(request: ChatRequest) -> List[str]:
    keys: List[str] = []
    if request.lore_topics:
        keys.extend(request.lore_topics)
    if request.lore_topic and request.lore_topic != 'default':
        keys.append(request.lore_topic)
    return _compact_unique(keys)


def _get_participants_from_session(session: ChatSession) -> Dict[str, List[str]]:
    return {
        'user_character_ids': _parse_json_list(session.user_character_ids_json),
        'bot_character_ids': _parse_json_list(session.bot_character_ids_json),
    }


def _new_request_id() -> str:
    return f'chat_{uuid.uuid4().hex[:10]}'


def _vector_service() -> Optional[VectorRetrievalService]:
    service = getattr(app_state, 'vector_retrieval_service', None)
    if service is not None:
        return service
    settings = app_state.settings
    if settings is None:
        return None
    domain_store = get_domain_store(data_path=getattr(settings, 'domain_data_file', None))
    service = VectorRetrievalService(
        domain_store=domain_store,
        index_path=getattr(settings, 'vector_index_file', Path('./mellow_chat_runtime_data/vector_index.json')),
    )
    app_state.vector_retrieval_service = service
    return service


def _classify_chat_error(exc: Exception) -> tuple[int, str, str]:
    if isinstance(exc, HTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else 'request_failed'
        return exc.status_code, 'request_failed', detail
    message = str(exc).strip() or 'Chat request failed'
    lowered = message.lower()
    if 'llm service unavailable' in lowered or 'orchestrator not initialized' in lowered:
        return 503, 'model_unavailable', message
    return 500, 'generation_failed', message


def _non_stream_error_response(exc: Exception, request_id: str) -> JSONResponse:
    status_code, error_code, message = _classify_chat_error(exc)
    return JSONResponse(
        status_code=status_code,
        content=ChatErrorResponse(error=error_code, message=message, request_id=request_id).model_dump(),
    )


def _stream_error_event(exc: Exception, request_id: str) -> str:
    _, error_code, message = _classify_chat_error(exc)
    payload = ChatErrorResponse(error=error_code, message=message, request_id=request_id).model_dump()
    return f'event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'


def _validation_failure_response(result: Any, request_id: str, status_code: int = 422) -> JSONResponse:
    payload = ChatValidationFailureResponse(
        success=False,
        error_code=str(getattr(result, 'error_code', '') or 'RP_VALIDATION_FAILED'),
        message=str(getattr(result, 'message', '') or 'RP 응답 품질 검증에 실패했습니다. 잠시 후 다시 시도해 주세요.'),
        request_id=request_id,
        failure_reason=str(getattr(result, 'failure_reason', '') or 'RP_VALIDATION_FAILED'),
    ).model_dump()
    return JSONResponse(status_code=status_code, content=payload)


def _validation_failure_payload(result: Any, request_id: str) -> Dict[str, Any]:
    return ChatValidationFailureResponse(
        success=False,
        error_code=str(getattr(result, 'error_code', '') or 'RP_VALIDATION_FAILED'),
        message=str(getattr(result, 'message', '') or 'RP 응답 품질 검증에 실패했습니다. 잠시 후 다시 시도해 주세요.'),
        request_id=request_id,
        failure_reason=str(getattr(result, 'failure_reason', '') or 'RP_VALIDATION_FAILED'),
    ).model_dump()


def _build_sanitized_history(rows: List[ChatMessage], max_items: int = 8) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for row in rows[-max_items:]:
        content = sanitize_history_text(row.role, row.content)
        if not content:
            continue
        out.append({'role': row.role, 'content': content})
    return out


def _build_retrieval_query(
    question: str,
    active_speaker_id: str,
    participant_ids: List[str],
    history: List[Dict[str, str]],
    scene_state: Dict[str, Any],
    lore_keys: List[str],
) -> str:
    history_lines = [
        f"{item.get('role', 'user')}: {item.get('content', '')}"
        for item in history[-4:]
        if str(item.get('content', '')).strip()
    ]
    parts = [
        question.strip(),
        f"active_speaker={active_speaker_id}",
        f"participants={','.join(participant_ids)}",
        f"scene_goal={scene_state.get('goal', '')}",
        f"scene_mood={scene_state.get('mood', '')}",
    ]
    if lore_keys:
        parts.append(f"lore_topics={','.join(lore_keys)}")
    if history_lines:
        parts.append("recent_turns=" + " | ".join(history_lines))
    return "\n".join(part for part in parts if part)


def _extract_hit_ids(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    hit_ids: List[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_id = item.get('id') or item.get('source_id')
        if not raw_id and item.get('character_id') and item.get('target_id'):
            raw_id = f"{item.get('character_id')}:{item.get('target_id')}"
        if not raw_id and item.get('character_id'):
            raw_id = item.get('character_id')
        cleaned = str(raw_id or '').strip()
        if cleaned:
            hit_ids.append(cleaned)
    return hit_ids


def _normalize_retrieval_source(source: Any, hit_ids: List[str]) -> str:
    cleaned = str(source or '').strip().lower()
    if cleaned == 'vector':
        return 'vector'
    if cleaned in {'canonical', 'fallback'}:
        return cleaned
    if hit_ids:
        return 'canonical'
    return 'none'


def _extract_score_map(items: Any) -> Dict[str, float]:
    if not isinstance(items, list):
        return {}
    out: Dict[str, float] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_id = item.get('id') or item.get('source_id')
        if not raw_id and item.get('character_id') and item.get('target_id'):
            raw_id = f"{item.get('character_id')}:{item.get('target_id')}"
        if not raw_id and item.get('character_id'):
            raw_id = item.get('character_id')
        cleaned = str(raw_id or '').strip()
        if not cleaned:
            continue
        raw_score = item.get('score')
        if raw_score is None:
            continue
        try:
            out[cleaned] = float(raw_score)
        except (TypeError, ValueError):
            continue
    return out


def _build_retrieval_debug_payload(query: str, retrieval_context: Dict[str, Any]) -> Dict[str, Any]:
    debug = retrieval_context.get('debug', {}) if isinstance(retrieval_context.get('debug'), dict) else {}
    lore_hit_ids = _extract_hit_ids(retrieval_context.get('lore', []))
    memory_hit_ids = _extract_hit_ids(retrieval_context.get('memories', []))
    relationship_hit_ids = _extract_hit_ids(retrieval_context.get('relationships', []))
    errors = [str(item).strip() for item in debug.get('errors', []) if str(item).strip()]
    return {
        'query': query,
        'lore_source': _normalize_retrieval_source(debug.get('lore_source'), lore_hit_ids),
        'memory_source': _normalize_retrieval_source(debug.get('memory_source'), memory_hit_ids),
        'relationship_source': _normalize_retrieval_source(debug.get('relationship_source'), relationship_hit_ids),
        'lore_hit_ids': lore_hit_ids,
        'memory_hit_ids': memory_hit_ids,
        'relationship_hit_ids': relationship_hit_ids,
        'lore_scores': _extract_score_map(retrieval_context.get('lore', [])),
        'memory_scores': _extract_score_map(retrieval_context.get('memories', [])),
        'relationship_scores': _extract_score_map(retrieval_context.get('relationships', [])),
        'errors': errors,
        'fallback_used': bool(debug.get('fallback_used', False)),
    }


def _build_prompt_watch_generation_path(result: Any) -> Dict[str, Any]:
    retry_count = int(getattr(result, 'retry_count', 0) or 0)
    fallback_used = bool(getattr(result, 'fallback_used', False))
    validator_passed = bool(getattr(result, 'validator_passed', False))
    if fallback_used:
        final_verdict = 'fallback'
    elif validator_passed and retry_count > 0:
        final_verdict = 'repaired'
    elif validator_passed:
        final_verdict = 'pass'
    else:
        final_verdict = 'failed'
    return {
        'validator_passed': getattr(result, 'validator_passed', None),
        'repair_used': retry_count > 0,
        'fallback_used': fallback_used,
        'retry_count': retry_count,
        'final_verdict': final_verdict,
        'failure_reason': str(getattr(result, 'failure_reason', '') or '') or None,
    }


def _resolve_prompt_watch_character(domain_store: Any, character_id: Optional[str], fallback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cleaned = str(character_id or '').strip()
    if cleaned:
        user_character = domain_store.get_user_character(cleaned)
        if user_character:
            return user_character
        bot_character = domain_store.get_bot_character(cleaned)
        if bot_character:
            return bot_character
        return {'id': cleaned, 'name': cleaned}
    return dict(fallback or {})


def _build_prompt_watch_context_items(items: Any, section: str, source: Optional[str]) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_id = item.get('id') or item.get('source_id')
        if not raw_id and item.get('character_id') and item.get('target_id'):
            raw_id = f"{item.get('character_id')}:{item.get('target_id')}"
        summary_text = build_prompt_watch_summary(section, item)
        out.append({
            'id': str(raw_id or '').strip() or None,
            'source': source,
            'topic': str(item.get('topic') or '').strip() or None,
            'character_id': str(item.get('character_id') or '').strip() or None,
            'target_id': str(item.get('target_id') or '').strip() or None,
            'summary_text': summary_text,
        })
    return out


def _build_prompt_watch_dynamic_state(
    domain_store: Any,
    *,
    character_id: Optional[str],
    session_id: Optional[int],
) -> Dict[str, Any]:
    cleaned_character_id = str(character_id or '').strip()
    cleaned_session_id = str(session_id or 'default').strip() or 'default'
    character_state = domain_store.get_character_state(cleaned_character_id) if cleaned_character_id else {}
    session_state = domain_store.get_session_state(cleaned_session_id)
    branch_id = str(session_state.get('branch_id') or 'default').strip() or 'default'
    branch_state = domain_store.get_branch_state(branch_id)
    return _build_dynamic_state_block(
        character_state=character_state if isinstance(character_state, dict) else {},
        session_state=session_state if isinstance(session_state, dict) else {},
        branch_state=branch_state if isinstance(branch_state, dict) else {},
    )


def _build_prompt_watch_session_summary(domain_store: Any, session_id: Optional[int]) -> Dict[str, Any]:
    cleaned_session_id = str(session_id or 'default').strip() or 'default'
    return domain_store.get_session_summary(cleaned_session_id)


def _build_prompt_watch_confirmed_facts(domain_store: Any, session_id: Optional[int], limit: int = 5) -> List[Dict[str, Any]]:
    cleaned_session_id = str(session_id or 'default').strip() or 'default'
    return domain_store.list_confirmed_facts(cleaned_session_id, limit=limit)


def _build_prompt_watch_user_note(domain_store: Any, profile_id: Optional[str]) -> Dict[str, Any]:
    cleaned_profile_id = str(profile_id or 'default').strip() or 'default'
    return domain_store.get_user_note(cleaned_profile_id)


def _build_prompt_watch_session_note(domain_store: Any, session_id: Optional[int]) -> Dict[str, Any]:
    cleaned_session_id = str(session_id or 'default').strip() or 'default'
    return domain_store.get_session_note(cleaned_session_id)


def _build_prompt_watch_branch_context(domain_store: Any, session_id: Optional[int]) -> Dict[str, Any]:
    cleaned_session_id = str(session_id or 'default').strip() or 'default'
    session_state = domain_store.get_session_state(cleaned_session_id)
    branch_id = str(session_state.get('branch_id') or 'default').strip() or 'default'
    branch_state = domain_store.get_branch_state(branch_id)
    return _build_branch_context_block(branch_state=branch_state if isinstance(branch_state, dict) else {}, session_state=session_state if isinstance(session_state, dict) else {})



def _persist_turn_runtime_state(
    domain_store: Any,
    *,
    session_id: int,
    character_id: Optional[str],
    user_text: str,
    assistant_text: str,
    scene_state: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        cleaned_session_id = str(session_id or 'default').strip() or 'default'
        fact_service = ConfirmedFactsService(domain_store)
        existing_confirmed_facts = fact_service.list_for_session(cleaned_session_id, limit=12)
        contradiction_service = ContradictionCheckService()
        contradictions = contradiction_service.detect(assistant_text, existing_confirmed_facts)
        update_service = StateUpdateService(domain_store)
        state_changes = update_service.apply_turn(
            session_id=cleaned_session_id,
            character_id=str(character_id or '').strip(),
            user_text=user_text,
            assistant_text=assistant_text,
            scene_state=scene_state if isinstance(scene_state, dict) else {},
        )
        turn_summary_service = TurnSummaryService(domain_store)
        turn_summary = turn_summary_service.record_turn(
            session_id=cleaned_session_id,
            speaker_id=str(character_id or '').strip(),
            user_text=user_text,
            assistant_text=assistant_text,
            state_changes=state_changes,
        )
        session_summary_service = SessionSummaryService(domain_store)
        session_summary = session_summary_service.rebuild_for_session(cleaned_session_id)
        confirmed_facts = fact_service.update_from_turn(turn_summary)
        return {
            'state_changes': state_changes,
            'turn_summary': turn_summary,
            'session_summary': session_summary,
            'confirmed_facts': confirmed_facts,
            'contradictions': contradictions,
        }
    except Exception as exc:
        logger.warning('chat.ask.state_update_error session_id=%s character_id=%s error=%s', session_id, character_id, exc)
        return {
            'state_changes': {},
            'turn_summary': None,
            'session_summary': None,
            'confirmed_facts': [],
            'contradictions': [],
            'error': str(exc),
        }


def _build_prompt_watch_payload(
    request: ChatRequest,
    effective_user_profile_id: str,
    selection: Any,
    selected_speaker_id: Optional[str],
    selected_speaker_type: Optional[str],
    parsed_scene_event: ParsedSceneEvent,
    retrieval_context: Dict[str, Any],
    retrieval_debug: Dict[str, Any],
    result: Any,
    active_character: Dict[str, Any],
    scene_state: Dict[str, Any],
    domain_store: Any,
    session_id: Optional[int],
) -> Dict[str, Any]:
    applied_lore = retrieval_context.get('lore', [])[:3] if isinstance(retrieval_context.get('lore'), list) else []
    applied_memories = retrieval_context.get('memories', [])[:4] if isinstance(retrieval_context.get('memories'), list) else []
    applied_relationships = retrieval_context.get('relationships', [])[:2] if isinstance(retrieval_context.get('relationships'), list) else []
    generation_path = _build_prompt_watch_generation_path(result)
    compact = {
        'active_character_id': str(active_character.get('id') or selected_speaker_id or '').strip() or None,
        'active_character_name': str(active_character.get('name') or '').strip() or None,
        'selected_speaker_id': selected_speaker_id,
        'selected_speaker_type': selected_speaker_type,
        'scene_id': request.scene_id,
        'world_id': request.world_id,
        'input_mode': getattr(parsed_scene_event, 'input_mode', None),
        'target_character_hint': getattr(parsed_scene_event, 'target_character_hint', None),
        'lore_hit_ids': _extract_hit_ids(applied_lore),
        'memory_hit_ids': _extract_hit_ids(applied_memories),
        'relationship_hit_ids': _extract_hit_ids(applied_relationships),
        'model': {
            'provider': selection.provider,
            'model': selection.model,
            'mode': selection.mode,
            'source': selection.source,
            'catalog_id': selection.catalog_id,
            'label': selection.label,
            'role_tags': list(selection.role_tags or []),
        },
        'repair_used': bool(generation_path['repair_used']),
        'fallback_used': bool(generation_path['fallback_used']),
    }
    if request.audience != 'admin':
        return compact
    return {
        **compact,
        'applied_persona_id': request.persona_id,
        'applied_user_profile_id': effective_user_profile_id,
        'generation_path': generation_path,
        'applied_context': {
            'lore': _build_prompt_watch_context_items(applied_lore, 'lorebook', retrieval_debug.get('lore_source')),
            'memories': _build_prompt_watch_context_items(applied_memories, 'memories', retrieval_debug.get('memory_source')),
            'relationships': _build_prompt_watch_context_items(applied_relationships, 'relationships', retrieval_debug.get('relationship_source')),
            'scene': {
                'goal': str(scene_state.get('goal') or '').strip(),
                'mood': str(scene_state.get('mood') or '').strip(),
            },
            'dynamic_state': _build_prompt_watch_dynamic_state(
                domain_store,
                character_id=selected_speaker_id or request.character_id,
                session_id=session_id,
            ),
            'session_summary': _build_prompt_watch_session_summary(domain_store, session_id),
            'confirmed_facts': _build_prompt_watch_context_items(
                _build_prompt_watch_confirmed_facts(domain_store, session_id, limit=5),
                'confirmed_facts',
                'session_store',
            ),
            'branch_context': _build_prompt_watch_branch_context(domain_store, session_id),
            'user_note': _build_prompt_watch_user_note(domain_store, effective_user_profile_id),
            'session_note': _build_prompt_watch_session_note(domain_store, session_id),
        },
    }


def _list_known_characters(domain_store: Any) -> List[Dict[str, Any]]:
    user_characters = list(domain_store.list_section('user_characters').values())
    bot_characters = list(domain_store.list_section('bot_characters').values())
    return [item for item in user_characters + bot_characters if isinstance(item, dict)]

@router.get('/chat/sessions')
async def get_chat_sessions(x_user: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    username = _user_from_header(x_user)
    user = get_or_create_user(db, username)
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id, ChatSession.is_active == True)
        .order_by(ChatSession.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            'id': s.id,
            'title': s.title,
            'created_at': s.created_at.isoformat(),
            'selected_model': {
                'provider': s.selected_model_provider,
                'model': s.selected_model_name,
                'mode': s.selected_model_mode,
            },
            'participants': _get_participants_from_session(s),
        }
        for s in sessions
    ]


@router.get('/chat/sessions/{session_id}/messages')
async def get_session_messages(session_id: int, x_user: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    username = _user_from_header(x_user)
    user = get_or_create_user(db, username)
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')

    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp.asc()).all()
    feedbacks = db.query(MessageFeedback).all()
    feedback_map = {f.message_id: f.is_positive for f in feedbacks}

    return [
        {
            'id': m.id,
            'role': m.role,
            'speaker_id': m.speaker_id,
            'speaker_type': m.speaker_type,
            'content': m.content,
            'selected_mode': m.selected_mode,
            'processing_time': m.processing_time,
            'feedback_positive': feedback_map.get(m.id),
            'created_at': m.timestamp.isoformat(),
        }
        for m in messages
    ]


@router.delete('/chat/sessions/{session_id}')
async def delete_chat_session(session_id: int, x_user: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    username = _user_from_header(x_user)
    user = get_or_create_user(db, username)
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')
    session.is_active = False
    db.commit()
    return {'success': True, 'deleted_id': session_id}


@router.post('/chat/messages/{message_id}/feedback')
async def submit_message_feedback(message_id: int, request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    is_positive = body.get('is_positive')
    if is_positive is None:
        raise HTTPException(status_code=400, detail='is_positive is required')

    existing = db.query(MessageFeedback).filter(MessageFeedback.message_id == message_id).first()
    if existing:
        existing.is_positive = bool(is_positive)
    else:
        db.add(MessageFeedback(message_id=message_id, is_positive=bool(is_positive)))
    db.commit()
    return {'success': True, 'message_id': message_id, 'positive': bool(is_positive)}


@router.get('/sessions/{session_id}/participants', response_model=SessionParticipantsResponse)
async def get_session_participants(session_id: int, x_user: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    username = _user_from_header(x_user)
    user = get_or_create_user(db, username)
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user.id, ChatSession.is_active == True).first()
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')
    participants = _get_participants_from_session(session)
    return SessionParticipantsResponse(
        session_id=session.id,
        user_character_ids=participants['user_character_ids'],
        bot_character_ids=participants['bot_character_ids'],
    )


@router.post('/sessions/{session_id}/participants', response_model=SessionParticipantsResponse)
async def upsert_session_participants(
    session_id: int,
    request: SessionParticipantsRequest,
    x_user: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    username = _user_from_header(x_user)
    user = get_or_create_user(db, username)
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user.id, ChatSession.is_active == True).first()
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')

    user_character_ids = _compact_unique(request.user_character_ids)
    bot_character_ids = _compact_unique(request.bot_character_ids)
    session.user_character_ids_json = json.dumps(user_character_ids, ensure_ascii=False)
    session.bot_character_ids_json = json.dumps(bot_character_ids, ensure_ascii=False)
    db.commit()
    db.refresh(session)

    return SessionParticipantsResponse(
        session_id=session.id,
        user_character_ids=user_character_ids,
        bot_character_ids=bot_character_ids,
    )


@router.post('/chat/ask')
async def chat_ask(request: ChatRequest, http_request: Request, x_user: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    request_id = _new_request_id()
    if not request.question.strip():
        raise HTTPException(status_code=400, detail='Question is required')

    if app_state.orchestrator is None:
        raise HTTPException(status_code=503, detail='Orchestrator not initialized')
    if app_state.llm_service is None:
        raise HTTPException(status_code=503, detail='LLM service not initialized')

    username = _user_from_header(x_user)
    user = get_or_create_user(db, username)
    session = get_or_create_session(db=db, user_id=user.id, session_id=request.session_id)
    session_participants = _get_participants_from_session(session)
    lore_keys = _resolve_lore_keys(request)
    requested_character_ids = _compact_unique(request.character_ids or [])
    if not requested_character_ids and request.character_id and request.character_id != 'default':
        requested_character_ids = [request.character_id]

    domain_store = get_domain_store(data_path=app_state.settings.domain_data_file if app_state.settings else None)
    effective_user_profile_id = request.user_profile_id
    if not effective_user_profile_id or effective_user_profile_id == 'default':
        if session_participants['user_character_ids']:
            effective_user_profile_id = session_participants['user_character_ids'][0]
    if effective_user_profile_id and not domain_store.get_user_profile(effective_user_profile_id):
        effective_user_profile_id = 'user_char_01'
    known_characters = _list_known_characters(domain_store)
    parsed_scene_event = parse_scene_event(request.question, known_characters)
    speaker_relevance = build_speaker_relevance(
        parsed_scene_event=parsed_scene_event,
        characters=known_characters,
        scene_state=domain_store.get_scene_state(request.scene_id),
    )

    active_character_ids = _compact_unique(
        requested_character_ids
        + ([effective_user_profile_id] if effective_user_profile_id and effective_user_profile_id != 'default' else [])
        + session_participants['bot_character_ids']
    )
    effective_lore_topic = lore_keys[0] if lore_keys else request.lore_topic

    user_speaker_id = effective_user_profile_id or request.user_profile_id
    user_msg = ChatMessage(
        session_id=session.id,
        role='user',
        speaker_id=user_speaker_id,
        speaker_type='user',
        content=request.question,
    )
    db.add(user_msg)
    db.commit()

    state_result = await app_state.orchestrator.request_state_change(SystemState.TEXT, reason='chat ask')
    if state_result == TransitionResult.INVALID_TRANSITION:
        raise HTTPException(status_code=409, detail='Invalid state transition')

    history_rows = db.query(ChatMessage).filter(ChatMessage.session_id == session.id).order_by(ChatMessage.timestamp.asc()).all()
    history = _build_sanitized_history(history_rows, max_items=8)
    recent_speaker_history = [str(row.speaker_id) for row in history_rows if row.speaker_id]
    request_catalog_entry = domain_store.get_model_catalog_item(request.catalog_id or '') if request.catalog_id else {}
    session_catalog_entry = domain_store.get_model_catalog_item(session.selected_model_catalog_id or '') if session.selected_model_catalog_id else {}
    try:
        selection = model_router.resolve(
            session=session,
            llm_service=app_state.llm_service,
            mode=request.mode,
            request_provider=request.provider,
            request_model=request.model,
            request_catalog_id=request.catalog_id,
            request_mode=request.mode if request.provider and request.model else None,
            request_catalog_entry=request_catalog_entry,
            session_catalog_entry=session_catalog_entry,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    memory_promotion_enabled = bool(getattr(app_state.settings, 'memory_promotion_enabled', True))
    memory_promotion_service = MemoryPromotionService(
        domain_store=domain_store,
        max_items=int(getattr(app_state.settings, 'memory_promotion_max_items', 20)),
    )
    scene_state = domain_store.get_scene_state(request.scene_id)
    scene_rules: Dict[str, Any] = {}
    if isinstance(scene_state.get('rules'), dict):
        scene_rules = dict(scene_state.get('rules', {}))
    if isinstance(scene_state.get('rules'), list):
        for item in scene_state.get('rules', []):
            if isinstance(item, dict):
                key = item.get('key')
                value = item.get('value')
                if isinstance(key, str):
                    scene_rules[key] = value
    bot_participants: List[SpeakerParticipant] = []
    bot_ids = _compact_unique(requested_character_ids + session_participants['bot_character_ids'])
    for character_id in bot_ids:
        bot_data = domain_store.get_bot_character(character_id)
        if not bot_data:
            continue
        bot_participants.append(
            SpeakerParticipant(
                character_id=character_id,
                is_major=bool(bot_data.get('is_major', True)),
            )
        )
    if not bot_participants and request.character_id and request.character_id != 'default':
        bot_participants.append(SpeakerParticipant(character_id=request.character_id, is_major=True))
    selected_speaker_id = select_next_speaker(
        participants=bot_participants,
        recent_speaker_history=recent_speaker_history,
        dialogue_priority=domain_store.get_dialogue_priority(request.scene_id),
        scene_rules=scene_rules,
        target_character_hint=parsed_scene_event.target_character_hint,
        speaker_relevance=speaker_relevance,
    )
    if selected_speaker_id is None and bot_ids:
        selected_speaker_id = bot_ids[0]
    speaker_type = 'bot'
    if selected_speaker_id and domain_store.get_user_character(selected_speaker_id):
        speaker_type = 'user'
    active_character = _resolve_prompt_watch_character(domain_store, selected_speaker_id or request.character_id)
    used_context = {
        'persona_id': request.persona_id,
        'user_profile_id': effective_user_profile_id,
        'character_ids': active_character_ids,
        'scene_id': request.scene_id,
        'world_id': request.world_id,
        'lore_keys': lore_keys,
    }
    logger.info(
        'chat.ask.start request_id=%s session_id=%s user=%s selected_model=%s selected_speaker=%s stream=%s audience=%s input_mode=%s target_hint=%s',
        request_id,
        session.id,
        username,
        selection.model,
        selected_speaker_id or request.character_id,
        request.stream,
        request.audience,
        parsed_scene_event.input_mode,
        parsed_scene_event.target_character_hint,
    )

    async def stream_generator():
        started = time.time()
        assistant_id: Optional[int] = None
        try:
            retrieval_context: Dict[str, Any] = {}
            retrieval_service = _vector_service()
            retrieval_query = _build_retrieval_query(
                question=request.question,
                active_speaker_id=selected_speaker_id or request.character_id,
                participant_ids=active_character_ids,
                history=history,
                scene_state=scene_state if isinstance(scene_state, dict) else {},
                lore_keys=lore_keys,
            )
            if retrieval_service is not None:
                try:
                    retrieval_context = retrieval_service.build_context(
                        RetrievalQueryContext(
                            query=retrieval_query,
                            active_speaker_id=selected_speaker_id or request.character_id,
                            participant_ids=active_character_ids,
                            lore_topics=lore_keys,
                        )
                    )
                except Exception as exc:
                    retrieval_context = {
                        'lore': [],
                        'memories': [],
                        'relationships': [],
                        'debug': {
                            'fallback_used': True,
                            'errors': [str(exc)],
                        },
                    }
                    logger.warning('chat.ask.retrieval_error request_id=%s session_id=%s error=%s', request_id, session.id, exc)
                if retrieval_context.get('debug', {}).get('fallback_used'):
                    logger.info(
                        'chat.ask.retrieval_fallback request_id=%s session_id=%s debug=%s',
                        request_id,
                        session.id,
                        json.dumps(retrieval_context.get('debug', {}), ensure_ascii=False),
                    )
            retrieval_debug = _build_retrieval_debug_payload(retrieval_query, retrieval_context)
            result = await app_state.orchestrator.run_agent(
                user_input=request.question,
                history=history,
                retrieval_context=retrieval_context,
                mode=selection.mode,
                persona_id=request.persona_id,
                user_profile_id=effective_user_profile_id,
                lore_topic=effective_lore_topic,
                character_id=selected_speaker_id or request.character_id,
                world_id=request.world_id,
                scene_id=request.scene_id,
                session_id=str(session.id),
                selected_model=selection.model,
                scene_event=parsed_scene_event,
                target_character_hint=parsed_scene_event.target_character_hint,
                request_id=request_id,
                audience=request.audience,
            )
            if request.audience == 'user' and not result.success:
                yield f'event: error\ndata: {json.dumps(_validation_failure_payload(result, request_id), ensure_ascii=False)}\n\n'
                return

            full = sanitize_assistant_text(result.answer or '')
            for i in range(0, len(full), 200):
                yield f'event: chunk\ndata: {json.dumps({"chunk": full[i:i+200], "request_id": request_id}, ensure_ascii=False)}\n\n'

            elapsed_ms = int((time.time() - started) * 1000)
            assistant = ChatMessage(
                session_id=session.id,
                role='assistant',
                speaker_id=selected_speaker_id,
                speaker_type=speaker_type,
                content=full,
                selected_mode=selection.mode,
                processing_time=elapsed_ms,
            )
            db.add(assistant)
            db.commit()
            db.refresh(assistant)
            assistant_id = assistant.id
            if memory_promotion_enabled:
                memory_promotion_service.promote_from_text(user_speaker_id, request.question)
                if selected_speaker_id:
                    memory_promotion_service.promote_from_text(selected_speaker_id, full)
            state_debug = _persist_turn_runtime_state(
                domain_store,
                session_id=session.id,
                character_id=selected_speaker_id or request.character_id,
                user_text=request.question,
                assistant_text=full,
                scene_state=scene_state if isinstance(scene_state, dict) else {},
            )

            done_payload = {
                'done': True,
                'session_id': session.id,
                'message_id': assistant.id,
                'speaker_id': selected_speaker_id,
                'speaker_type': speaker_type,
                'model_provider': selection.provider,
                'model_name': selection.model,
                'selected_mode': selection.mode,
                'processing_time_ms': elapsed_ms,
                'used_context': used_context,
                'model': {
                    'provider': selection.provider,
                    'model': selection.model,
                    'mode': selection.mode,
                    'source': selection.source,
                    'catalog_id': selection.catalog_id,
                    'label': selection.label,
                    'role_tags': list(selection.role_tags or []),
                    'status': selection.status,
                },
                'request_id': request_id,
            }
            done_payload['prompt_watch'] = _build_prompt_watch_payload(
                request=request,
                effective_user_profile_id=effective_user_profile_id,
                selection=selection,
                selected_speaker_id=selected_speaker_id,
                selected_speaker_type=speaker_type,
                parsed_scene_event=parsed_scene_event,
                retrieval_context=retrieval_context,
                retrieval_debug=retrieval_debug,
                result=result,
                active_character=active_character,
                scene_state=scene_state if isinstance(scene_state, dict) else {},
                domain_store=domain_store,
                session_id=session.id,
            )
            if request.audience == 'admin':
                done_payload['retrieval_debug'] = retrieval_debug
                done_payload['state_debug'] = state_debug
            if request.audience == 'admin':
                done_payload['rp_debug'] = {
                    'validator_passed': result.validator_passed,
                    'fallback_used': result.fallback_used,
                    'retry_count': result.retry_count,
                    'final_verdict': result.final_verdict,
                    'failure_reason': result.failure_reason,
                    'failure_reasons': result.failure_reasons,
                }
            logger.info(
                'chat.ask.end request_id=%s session_id=%s message_id=%s success=true latency_ms=%s',
                request_id,
                session.id,
                assistant_id,
                elapsed_ms,
            )
            yield f'event: done\ndata: {json.dumps(done_payload, ensure_ascii=False)}\n\n'
        except Exception as e:
            elapsed_ms = int((time.time() - started) * 1000)
            logger.exception(
                'chat.ask.error request_id=%s session_id=%s latency_ms=%s error=%s',
                request_id,
                session.id,
                elapsed_ms,
                str(e),
            )
            yield _stream_error_event(e, request_id)
        finally:
            await app_state.orchestrator.request_state_change(SystemState.IDLE, reason='chat ask done')

    if request.stream:
        return StreamingResponse(stream_generator(), media_type='text/event-stream')

    started = time.time()
    try:
        retrieval_context: Dict[str, Any] = {}
        retrieval_service = _vector_service()
        retrieval_query = _build_retrieval_query(
            question=request.question,
            active_speaker_id=selected_speaker_id or request.character_id,
            participant_ids=active_character_ids,
            history=history,
            scene_state=scene_state if isinstance(scene_state, dict) else {},
            lore_keys=lore_keys,
        )
        if retrieval_service is not None:
            try:
                retrieval_context = retrieval_service.build_context(
                    RetrievalQueryContext(
                        query=retrieval_query,
                        active_speaker_id=selected_speaker_id or request.character_id,
                        participant_ids=active_character_ids,
                        lore_topics=lore_keys,
                    )
                )
            except Exception as exc:
                retrieval_context = {
                    'lore': [],
                    'memories': [],
                    'relationships': [],
                    'debug': {
                        'fallback_used': True,
                        'errors': [str(exc)],
                    },
                }
                logger.warning('chat.ask.retrieval_error request_id=%s session_id=%s error=%s', request_id, session.id, exc)
            if retrieval_context.get('debug', {}).get('fallback_used'):
                logger.info(
                    'chat.ask.retrieval_fallback request_id=%s session_id=%s debug=%s',
                    request_id,
                    session.id,
                    json.dumps(retrieval_context.get('debug', {}), ensure_ascii=False),
                )
        retrieval_debug = _build_retrieval_debug_payload(retrieval_query, retrieval_context)
        result = await app_state.orchestrator.run_agent(
            user_input=request.question,
            history=history,
            retrieval_context=retrieval_context,
            mode=request.mode,
            persona_id=request.persona_id,
            user_profile_id=effective_user_profile_id,
            lore_topic=effective_lore_topic,
            character_id=selected_speaker_id or request.character_id,
            world_id=request.world_id,
            scene_id=request.scene_id,
            session_id=str(session.id),
            selected_model=selection.model,
            scene_event=parsed_scene_event,
            target_character_hint=parsed_scene_event.target_character_hint,
            request_id=request_id,
            audience=request.audience,
        )
        elapsed_ms = int((time.time() - started) * 1000)
        if request.audience == 'user' and not result.success:
            logger.warning(
                'chat.ask.validation_failed request_id=%s session_id=%s latency_ms=%s error_code=%s failure_reason=%s',
                request_id,
                session.id,
                elapsed_ms,
                result.error_code,
                result.failure_reason,
            )
            return _validation_failure_response(result, request_id)
        cleaned_response = sanitize_assistant_text(result.answer or '')
        assistant = ChatMessage(
            session_id=session.id,
            role='assistant',
            speaker_id=selected_speaker_id,
            speaker_type=speaker_type,
            content=cleaned_response,
            selected_mode=selection.mode,
            processing_time=elapsed_ms,
        )
        db.add(assistant)
        db.commit()
        db.refresh(assistant)
        if memory_promotion_enabled:
            memory_promotion_service.promote_from_text(user_speaker_id, request.question)
            if selected_speaker_id:
                memory_promotion_service.promote_from_text(selected_speaker_id, cleaned_response)
        state_debug = _persist_turn_runtime_state(
            domain_store,
            session_id=session.id,
            character_id=selected_speaker_id or request.character_id,
            user_text=request.question,
            assistant_text=cleaned_response,
            scene_state=scene_state if isinstance(scene_state, dict) else {},
        )
        logger.info(
            'chat.ask.end request_id=%s session_id=%s message_id=%s success=true latency_ms=%s',
            request_id,
            session.id,
            assistant.id,
            elapsed_ms,
        )
        response_payload = {
            'response': cleaned_response,
            'session_id': session.id,
            'message_id': assistant.id,
            'speaker_id': selected_speaker_id,
            'speaker_type': speaker_type,
            'model_provider': selection.provider,
            'model_name': selection.model,
            'selected_mode': selection.mode,
            'processing_time_ms': elapsed_ms,
            'used_context': used_context,
            'model': {
                'provider': selection.provider,
                'model': selection.model,
                'mode': selection.mode,
                'source': selection.source,
                'catalog_id': selection.catalog_id,
                'label': selection.label,
                'role_tags': list(selection.role_tags or []),
                'status': selection.status,
            },
            'prompt_watch': _build_prompt_watch_payload(
                request=request,
                effective_user_profile_id=effective_user_profile_id,
                selection=selection,
                selected_speaker_id=selected_speaker_id,
                selected_speaker_type=speaker_type,
                parsed_scene_event=parsed_scene_event,
                retrieval_context=retrieval_context,
                retrieval_debug=retrieval_debug,
                result=result,
                active_character=active_character,
                scene_state=scene_state if isinstance(scene_state, dict) else {},
                domain_store=domain_store,
                session_id=session.id,
            ),
            'request_id': request_id,
        }
        if request.audience == 'admin':
            response_payload['retrieval_debug'] = retrieval_debug
            response_payload['state_debug'] = state_debug
        if request.audience == 'admin':
            response_payload['rp_debug'] = {
                'validator_passed': result.validator_passed,
                'fallback_used': result.fallback_used,
                'retry_count': result.retry_count,
                'final_verdict': result.final_verdict,
                'failure_reason': result.failure_reason,
                'failure_reasons': result.failure_reasons,
            }
        return response_payload
    except Exception as e:
        elapsed_ms = int((time.time() - started) * 1000)
        logger.exception(
            'chat.ask.error request_id=%s session_id=%s latency_ms=%s error=%s',
            request_id,
            session.id,
            elapsed_ms,
            str(e),
        )
        return _non_stream_error_response(e, request_id)
    finally:
        await app_state.orchestrator.request_state_change(SystemState.IDLE, reason='chat ask done')
