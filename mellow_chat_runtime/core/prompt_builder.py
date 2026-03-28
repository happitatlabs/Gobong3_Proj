from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from mellow_chat_runtime.core.rp_parser import ParsedSceneEvent
from mellow_chat_runtime.services.branch_visibility_service import BranchVisibilityService


def build_system_prompt(
    persona: Dict[str, Any],
    dialogue_priority: Dict[str, Any],
    active_character: Optional[Dict[str, Any]] = None,
    user_profile: Optional[Dict[str, Any]] = None,
    relationships: Optional[List[Dict[str, Any]]] = None,
) -> str:
    persona_desc = persona.get('description', '')
    priority_rules = dialogue_priority.get('rules', '')
    active_character = active_character or {}
    relationships = relationships or []
    character_name = active_character.get('name') or 'Unknown Character'
    speech_style = active_character.get('speech_style', {}) if isinstance(active_character.get('speech_style'), dict) else {}
    tone = speech_style.get('tone') or active_character.get('tone') or 'neutral'
    forbidden = speech_style.get('forbidden', [])
    if not isinstance(forbidden, list):
        forbidden = []
    forbidden_text = ', '.join(str(item).strip() for item in forbidden if str(item).strip()) or 'none'
    relationship_keys = active_character.get('relationship_keys', [])
    if not isinstance(relationship_keys, list):
        relationship_keys = []
    relationship_text = ', '.join(str(item).strip() for item in relationship_keys if str(item).strip()) or 'none'
    role_context = active_character.get('profile') or active_character.get('role') or active_character.get('type') or 'character'
    relationship_lines: List[str] = []
    for item in relationships[:4]:
        target_id = item.get('target_id', 'unknown')
        summary = item.get('summary', '')
        rel_tone = item.get('tone', 'neutral')
        boundaries = item.get('boundaries', [])
        if not isinstance(boundaries, list):
            boundaries = []
        boundary_text = ', '.join(str(boundary).strip() for boundary in boundaries if str(boundary).strip()) or 'none'
        relationship_lines.append(f'- {target_id}: {summary} | tone={rel_tone} | boundaries={boundary_text}')
    relationship_block = '\n'.join(relationship_lines) if relationship_lines else '- none'
    aliases = active_character.get('aliases', []) if isinstance(active_character.get('aliases'), list) else []
    alias_text = ', '.join(str(alias).strip() for alias in aliases if str(alias).strip()) or '(없음)'
    style_anchor = str(active_character.get('style_anchor') or '').strip()
    franchise_anchor = str(active_character.get('franchise_anchor') or '').strip()
    user_interpretation_block = _build_user_interpretation_block(user_profile or {})
    response_tuning_lines = _build_user_response_tuning_lines(user_profile or {})
    return (
        f'당신은 {character_name}이다.\n\n'
        '역할:\n'
        f'{role_context}\n\n'
        '말투:\n'
        f'{tone}\n\n'
        '입력 해석 규칙:\n'
        '- 사용자 입력에는 서술과 대사가 함께 들어올 수 있다\n'
        '- 서술은 장면과 행동 맥락으로 해석한다\n'
        '- 따옴표 안의 문장은 사용자의 실제 발화로 해석한다\n'
        '- 설명이 아니라 장면 안의 즉각적인 반응으로 답한다\n\n'
        '출력 형식:\n'
        '1. 짧은 서술 또는 행동 문단 하나\n'
        '2. 따옴표로 감싼 대사 한 줄\n\n'
        '핵심 규칙:\n'
        '- 항상 캐릭터를 유지한다\n'
        '- 제공된 세계관 정보와 모순되지 않게 답한다\n'
        '- 설명보다 행동과 대사를 우선한다\n'
        '- 메타 발화나 4벽 깨기를 하지 않는다\n'
        '- 응답 본문은 반드시 message.content에 들어갈 최종 RP 답변만 작성한다\n'
        '- 분석, 사고과정, 계획, 초안, 체크리스트를 출력하지 않는다\n'
        '- 빈 응답이나 생략 기호만 출력하지 않는다\n'
        '- 선택된 캐릭터를 3인칭 서술로 묘사한다\n'
        '- 사용자 입력의 주 언어와 같은 언어로 답한다\n'
        '- 사용자 입력이 한국어이면 서술과 대사를 모두 한국어로 유지하고 영어로 전환하지 않는다\n\n'
        '우선순위:\n'
        '1. 현재 장면 규칙과 장면 목표\n'
        '2. 동적 상태와 장면 연속성\n'
        '3. 세계 상태 제약과 연속성\n'
        '4. 캐릭터 기억과 관계 맥락\n'
        '5. 로어북 사실과 용어\n\n'
        '금지 요소:\n'
        f'{forbidden_text}\n\n'
        '정체성 맥락:\n'
        f'표기 앵커: 이름={character_name}, 별칭={alias_text}\n'
        f'관계 키: {relationship_text}\n'
        f'페르소나: {persona_desc}\n'
        f'스타일 앵커: {style_anchor or "(없음)"}\n'
        f'프랜차이즈 앵커: {franchise_anchor or "(없음)"}\n'
        f'대화 정책: {priority_rules}\n\n'
        '관계 맥락:\n'
        f'{relationship_block}\n\n'
        '상대 해석 프레임:\n'
        f'{user_interpretation_block}\n\n'
        '상대 해석 프레임 대응 규칙:\n'
        + '\n'.join(f'- {line}' for line in response_tuning_lines)
        + '\n\n'
        '출력 제한:\n'
        '- 사용자에게 보여줄 최종 RP 답변만 출력한다\n'
        '- 답변 설명, 지시문 언급, 분석, 계획, 체크리스트, 역할 태그를 쓰지 않는다\n'
        '- <|im_start|>, <|im_end|>, <|endoftext|>, <think> 같은 토큰을 출력하지 않는다\n'
        '- assistant 식 메타 문장을 쓰지 않는다\n'
        '- 추측으로 다른 작품이나 다른 캐릭터 정체성을 섞지 않는다\n'
        '- 끝까지 캐릭터를 유지한다\n\n'
        '아래에 대화 맥락과 기억 정보가 이어진다.\n'
        '도메인 데이터가 주어졌다면 외부 사실을 임의로 지어내지 않는다.'
    )


def build_user_prompt(
    user_text: str,
    user_profile: Dict[str, Any],
    lore: Dict[str, Any],
    memories: Dict[str, Any],
    world_state: Dict[str, Any],
    scene_state: Dict[str, Any],
    character_state: Dict[str, Any],
    session_state: Dict[str, Any],
    branch_state: Dict[str, Any],
    session_summary: Dict[str, Any],
    confirmed_facts: List[Dict[str, Any]],
    user_note: Dict[str, Any],
    session_note: Dict[str, Any],
    relationships: Optional[List[Dict[str, Any]]] = None,
    history: Optional[List[Dict[str, str]]] = None,
    scene_event: Optional[ParsedSceneEvent] = None,
    target_character_hint: Optional[str] = None,
    retrieval_context: Optional[Dict[str, Any]] = None,
) -> str:
    parts: List[str] = []
    primary_language = _detect_primary_language(scene_event.raw_text if scene_event is not None else user_text)
    language_label = '한국어' if primary_language == 'ko' else '영어' if primary_language == 'en' else '입력과 동일한 언어'
    relationships = relationships or []
    retrieval_context = retrieval_context or {}
    user_name = str(user_profile.get('name') or '').strip()
    user_display_name = str(user_profile.get('display_name') or user_name or '').strip()
    user_aliases = user_profile.get('aliases', []) if isinstance(user_profile.get('aliases'), list) else []
    cleaned_user_aliases = [str(item).strip() for item in user_aliases if str(item).strip()]
    user_anchor_text = ', '.join([item for item in [user_name, *cleaned_user_aliases] if item]) or '(없음)'
    user_interpretation_block = _build_user_interpretation_block(user_profile)
    response_tuning_lines = _build_user_response_tuning_lines(user_profile)
    dynamic_state = _build_dynamic_state_block(
        character_state=character_state if isinstance(character_state, dict) else {},
        session_state=session_state if isinstance(session_state, dict) else {},
        branch_state=branch_state if isinstance(branch_state, dict) else {},
    )
    branch_context = _build_branch_context_block(
        branch_state=branch_state if isinstance(branch_state, dict) else {},
        session_state=session_state if isinstance(session_state, dict) else {},
    )
    prioritized_memories = memories.get('important_memories', []) if isinstance(memories, dict) else []
    if not isinstance(prioritized_memories, list):
        prioritized_memories = []
    prioritized_memories = [str(item).strip() for item in prioritized_memories if str(item).strip()][:5]
    world_facts = world_state.get('facts', []) if isinstance(world_state, dict) else []
    if not isinstance(world_facts, list):
        world_facts = []
    world_facts = [str(item).strip() for item in world_facts if str(item).strip()][:5]
    session_summary = session_summary if isinstance(session_summary, dict) else {}
    confirmed_facts = confirmed_facts if isinstance(confirmed_facts, list) else []
    user_note_block = _build_note_block(user_note if isinstance(user_note, dict) else {}, id_key='profile_id')
    session_note_block = _build_note_block(session_note if isinstance(session_note, dict) else {}, id_key='session_id')
    confirmed_fact_lines = [str(item.get('fact') or item.get('summary_text') or '').strip() for item in confirmed_facts if isinstance(item, dict) and str(item.get('fact') or item.get('summary_text') or '').strip()][:5]
    session_summary_text = str(session_summary.get('summary_text') or session_summary.get('summary') or '').strip()
    relationship_summary = []
    for item in relationships[:2]:
        summary = str(item.get('summary', '')).strip()
        tone = str(item.get('tone', 'neutral')).strip() or 'neutral'
        boundaries = item.get('boundaries', [])
        if not isinstance(boundaries, list):
            boundaries = []
        boundary = ', '.join(str(boundary).strip() for boundary in boundaries[:1] if str(boundary).strip()) or 'none'
        relationship_summary.append(f'tone={tone}; boundary={boundary}; summary={summary}')

    if history:
        recent = history[-6:]
        parts.append('최근 대화:\n' + '\n'.join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in recent))

    if scene_event is not None:
        parts.append(
            '파싱된 사용자 장면 이벤트:\n'
            f'원문 입력: {scene_event.raw_text or user_text}\n'
            f'사용자 서술: {scene_event.user_narration or "(없음)"}\n'
            f'사용자 대사: {scene_event.user_dialogue or "(없음)"}\n'
            f'입력 모드: {scene_event.input_mode}\n'
            f'대상 힌트: {target_character_hint or scene_event.target_character_hint or "(없음)"}'
        )

    retrieved_relationships = retrieval_context.get('relationships', []) if isinstance(retrieval_context.get('relationships'), list) else []
    retrieved_memories = retrieval_context.get('memories', []) if isinstance(retrieval_context.get('memories'), list) else []
    retrieved_lore = retrieval_context.get('lore', []) if isinstance(retrieval_context.get('lore'), list) else []
    retrieval_lines: List[str] = []
    if retrieved_relationships:
        retrieval_lines.append(
            '5. relationship summaries:\n' +
            '\n'.join(
                f'- {item.get("target_id", "unknown")}: {item.get("summary_text") or item.get("summary", "")}'
                for item in retrieved_relationships[:2]
                if str(item.get("summary_text") or item.get("summary", "")).strip()
            )
        )
    if retrieved_memories:
        retrieval_lines.append(
            '6. important memories:\n' +
            '\n'.join(
                f'- {item.get("character_id", "unknown")}: {item.get("summary_text", "")}'
                for item in retrieved_memories[:4]
                if str(item.get("summary_text", "")).strip()
            )
        )
    if retrieved_lore:
        retrieval_lines.append(
            '7. lore support:\n' +
            '\n'.join(
                f'- {item.get("topic", item.get("id", "unknown"))}: {item.get("summary_text", item.get("content", ""))}'
                for item in retrieved_lore[:3]
                if str(item.get("summary_text", item.get("content", ""))).strip()
            )
        )

    parts.append(
        '출력 제약:\n'
        f'- 응답 주 언어: {language_label}\n'
        '- 사용자 입력의 주 언어와 같은 언어를 유지한다\n'
        '- 한국어 입력이면 서술과 대사를 모두 한국어로 유지하고 영어로 전환하지 않는다\n'
        f'- 사용자 표기 앵커는 {user_anchor_text}만 사용하고, 이름을 임의로 다른 표기로 바꾸지 않는다\n'
        f'- 현재 상대는 {user_display_name or user_name or "개척자"} 해석 프레임을 가진다\n'
        '- message.content에는 최종 RP 답변만 넣고 분석/계획/생각을 쓰지 않는다\n'
        '- 빈 응답을 반환하지 않는다\n'
        f'- 서술은 선택된 캐릭터를 3인칭으로 묘사한다\n\n'
        '우선 맥락:\n'
        f'동적 상태: {json.dumps(dynamic_state, ensure_ascii=False)}\n'
        f'장면 우선: {json.dumps(scene_state, ensure_ascii=False)}\n'
        f'확정 사실: {json.dumps(confirmed_fact_lines, ensure_ascii=False)}\n'
        f'세션 요약: {json.dumps({"summary": session_summary_text, "turn_count": session_summary.get("turn_count", 0)}, ensure_ascii=False)}\n'
        f'브랜치 맥락: {json.dumps(branch_context, ensure_ascii=False)}\n'
        f'유저 노트: {json.dumps(user_note_block, ensure_ascii=False)}\n'
        f'세션 노트: {json.dumps(session_note_block, ensure_ascii=False)}\n'
        f'세계 제약: {json.dumps({"facts": world_facts, "location": world_state.get("location"), "time": world_state.get("time"), "state": world_state.get("state")}, ensure_ascii=False)}\n'
        f'캐릭터 기억: {json.dumps({"important_memories": prioritized_memories, "possessions": memories.get("possessions", [])}, ensure_ascii=False)}\n'
        f'관계 맥락: {json.dumps(relationship_summary, ensure_ascii=False)}\n'
        f'로어 참고: {json.dumps(lore, ensure_ascii=False)}'
    )
    if retrieval_lines:
        parts.append(
            '검색 보조 맥락 우선순위:\n'
            '1. scene rules / goal\n'
            '2. dynamic state\n'
            '3. world continuity\n'
            '4. active speaker constraints\n'
            '5. structured relationship constraints\n'
            + '\n'.join(retrieval_lines)
            + '\n8. recent history'
        )
    parts.append('사용자 해석 프레임:\n' + user_interpretation_block)
    parts.append('응답 조율 규칙:\n' + '\n'.join(f'- {line}' for line in response_tuning_lines))
    parts.append('사용자 프로필:\n' + json.dumps(user_profile, ensure_ascii=False))
    parts.append('현재 사용자 메시지:\n' + user_text)
    return '\n\n'.join(parts)


def _build_user_interpretation_block(user_profile: Dict[str, Any]) -> str:
    display_name = str(user_profile.get('display_name') or user_profile.get('name') or '개척자').strip()
    role = str(user_profile.get('role') or 'trailblazer').strip() or 'trailblazer'
    persona = str(user_profile.get('persona') or user_profile.get('profile') or '').strip()
    core_context = user_profile.get('core_context', []) if isinstance(user_profile.get('core_context'), list) else []
    cleaned_core_context = [str(item).strip() for item in core_context if str(item).strip()]
    interpretation_style = user_profile.get('interpretation_style', {}) if isinstance(user_profile.get('interpretation_style'), dict) else {}
    risk_view = str(interpretation_style.get('risk_view') or 'balanced').strip()
    emotion_weight = str(interpretation_style.get('emotion_weight') or 'medium').strip()
    decision_speed = str(interpretation_style.get('decision_speed') or 'steady').strip()
    response_style = str(interpretation_style.get('response_style') or 'balanced').strip()
    style_guidance = _interpretation_style_guidance(
        risk_view=risk_view,
        emotion_weight=emotion_weight,
        decision_speed=decision_speed,
        response_style=response_style,
    )
    core_text = '; '.join(cleaned_core_context) if cleaned_core_context else '낯선 상황에 들어온 외부자, 관찰자적 위치'
    return (
        f'- archetype: {display_name} ({role})\n'
        f'- core: {core_text}\n'
        f'- persona: {persona or "상황을 이해하고 대응해야 하는 개척자"}\n'
        f'- interpretation_style: risk_view={risk_view}, emotion_weight={emotion_weight}, decision_speed={decision_speed}, response_style={response_style}\n'
        f'- response_tuning: {style_guidance}'
    )


def _interpretation_style_guidance(
    *,
    risk_view: str,
    emotion_weight: str,
    decision_speed: str,
    response_style: str,
) -> str:
    if response_style == 'conclusive':
        return (
            '상황을 구조와 판단의 문제로 다뤄라. 감정보다 해결과 결론을 먼저 제시하고, '
            '리스크는 계산 가능한 요소처럼 설명하라. 답변은 단정적이고 빠른 결정이 느껴지게 정리하라.'
        )
    if response_style == 'descriptive':
        return (
            '상황을 체감과 맥락의 문제로 다뤄라. 감정과 분위기, 체감되는 불안을 충분히 짚은 뒤 '
            '판단을 제시하라. 답변은 설명형으로 풀고, 신중하게 결론에 도달하는 흐름을 유지하라.'
        )
    return (
        '관찰과 적응의 균형을 유지하라. 구조와 감정 모두를 과장 없이 반영하고, '
        '성급하지도 지나치게 늘어지지도 않게 대응하라.'
    )


def _build_note_block(note_payload: Dict[str, Any], *, id_key: str) -> Dict[str, Any]:
    note_text = str(note_payload.get('note') or '').strip()
    hard_constraints = [str(item).strip() for item in note_payload.get('hard_constraints', []) if str(item).strip()] if isinstance(note_payload.get('hard_constraints'), list) else []
    preferred_dynamic = [str(item).strip() for item in note_payload.get('preferred_dynamic', []) if str(item).strip()] if isinstance(note_payload.get('preferred_dynamic'), list) else []
    relationship_expectation = str(note_payload.get('relationship_expectation') or '').strip()
    return {
        id_key: str(note_payload.get(id_key) or '').strip() or None,
        'note': note_text or None,
        'hard_constraints': hard_constraints[:5],
        'preferred_dynamic': preferred_dynamic[:5],
        'relationship_expectation': relationship_expectation or None,
    }


def _build_branch_context_block(*, branch_state: Dict[str, Any], session_state: Dict[str, Any]) -> Dict[str, Any]:
    service = BranchVisibilityService()
    return service.build_branch_context(branch_state if isinstance(branch_state, dict) else {}, session_state if isinstance(session_state, dict) else {})


def _build_dynamic_state_block(
    *,
    character_state: Dict[str, Any],
    session_state: Dict[str, Any],
    branch_state: Dict[str, Any],
) -> Dict[str, Any]:
    character_flags = character_state.get('scene_flags', {}) if isinstance(character_state.get('scene_flags'), dict) else {}
    relationship_delta = character_state.get('relationship_delta', {}) if isinstance(character_state.get('relationship_delta'), dict) else {}
    session_flags = session_state.get('scene_flags', {}) if isinstance(session_state.get('scene_flags'), dict) else {}
    route_flags = branch_state.get('route_flags', {}) if isinstance(branch_state.get('route_flags'), dict) else {}
    return {
        'character': {
            'emotion': str(character_state.get('emotion') or 'neutral').strip() or 'neutral',
            'location': str(character_state.get('location') or '').strip() or None,
            'outfit': str(character_state.get('outfit') or '').strip() or None,
            'scene_flags': {str(key): bool(value) for key, value in character_flags.items()},
            'relationship_delta': {str(key): float(value) for key, value in relationship_delta.items() if _is_number(value)},
            'status_notes': [str(item).strip() for item in character_state.get('status_notes', []) if str(item).strip()][:3],
        },
        'session': {
            'branch_id': str(session_state.get('branch_id') or 'default').strip() or 'default',
            'active_location': str(session_state.get('active_location') or '').strip() or None,
            'active_phase': str(session_state.get('active_phase') or '').strip() or None,
            'scene_flags': {str(key): bool(value) for key, value in session_flags.items()},
            'status_notes': [str(item).strip() for item in session_state.get('status_notes', []) if str(item).strip()][:3],
        },
        'branch': {
            'route_flags': {str(key): bool(value) for key, value in route_flags.items()},
            'hidden_facts_revealed': [str(item).strip() for item in branch_state.get('hidden_facts_revealed', []) if str(item).strip()][:5],
            'active_objectives': [str(item).strip() for item in branch_state.get('active_objectives', []) if str(item).strip()][:5],
        },
    }


def _is_number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


def _build_user_response_tuning_lines(user_profile: Dict[str, Any]) -> List[str]:
    interpretation_style = user_profile.get('interpretation_style', {}) if isinstance(user_profile.get('interpretation_style'), dict) else {}
    response_style = str(interpretation_style.get('response_style') or 'balanced').strip()
    if response_style == 'conclusive':
        return [
            '상황을 문제와 구조로 먼저 정리하고, 감정 묘사는 필요한 만큼만 짧게 다룬다.',
            '리스크를 계산 가능한 조건, 변수, 우선순위로 나눠 설명한다.',
            '결론이나 판단을 앞부분에 두고, 근거는 그 뒤에 압축해서 붙인다.',
            '망설이는 어조보다 단정적이고 빠른 결정을 선호하는 톤을 유지한다.',
        ]
    if response_style == 'descriptive':
        return [
            '상황을 체감과 맥락으로 먼저 풀고, 감정의 결을 무시하지 않는다.',
            '리스크를 단순 수치가 아니라 실제로 느껴지는 불안과 파장으로 설명한다.',
            '배경과 맥락을 먼저 짚은 뒤에 판단을 제시한다.',
            '서두르기보다 신중하게 결론에 도달하는 톤을 유지한다.',
        ]
    return [
        '상황의 구조와 감정적 맥락을 균형 있게 함께 반영한다.',
        '리스크는 계산 가능한 요소와 체감되는 부담을 함께 언급한다.',
        '결론을 서두르지 않되 지나치게 늘이지 말고, 관찰과 적응의 흐름을 유지한다.',
        '기본형 개척자를 상대한다는 전제로 차분하고 유연한 응답 흐름을 유지한다.',
    ]


def _detect_primary_language(text: str) -> str:
    hangul_count = len(re.findall(r'[\u3131-\u318E\uAC00-\uD7A3]', text or ''))
    latin_count = len(re.findall(r'[A-Za-z]', text or ''))
    if hangul_count >= max(8, latin_count * 2):
        return 'ko'
    if latin_count >= max(12, hangul_count * 2):
        return 'en'
    return 'same-as-input'
