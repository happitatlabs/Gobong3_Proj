from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import mellow_chat_runtime.app_state as app_state
import mellow_chat_runtime.core.domain_lookup_store as domain_lookup_store_module
from mellow_chat_runtime.core.domain_lookup_dispatcher import DomainLookupDispatcher
from mellow_chat_runtime.core.orchestrator import Orchestrator
from mellow_chat_runtime.infra.database import init_db
from mellow_chat_runtime.routers.admin import router as admin_router
from mellow_chat_runtime.routers.chat import router as chat_router


class RecordingLLM:
    def __init__(self, response_texts: list[str]) -> None:
        self.response_texts = list(response_texts)
        self.chat_calls: list[list[dict[str, str]]] = []

    def get_model_for_mode(self, mode: str) -> str:
        return 'qwen3.5:9b'

    async def chat(self, messages, model=None, **kwargs):
        self.chat_calls.append(messages)
        text = self.response_texts.pop(0)
        return SimpleNamespace(text=text, thinking='', model=model or 'qwen3.5:9b')

    async def generate(self, prompt, system_prompt='', mode='fast', **kwargs):
        self.chat_calls.append([{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': prompt}])
        text = self.response_texts.pop(0)
        return SimpleNamespace(content=text)


def _reset_domain_store() -> None:
    domain_lookup_store_module._global_store = None


def _build_runtime_client(tmp_path: Path, llm: RecordingLLM) -> TestClient:
    _reset_domain_store()
    domain_file = tmp_path / 'domain_data.json'
    store = domain_lookup_store_module.get_domain_store(data_path=domain_file)
    dispatcher = DomainLookupDispatcher(store)
    init_db()
    orchestrator = Orchestrator(lookup_dispatcher=dispatcher)
    orchestrator.register_service('llm', llm)
    app_state.settings = SimpleNamespace(domain_data_file=domain_file, memory_promotion_enabled=False, memory_promotion_max_items=20)
    app_state.llm_service = llm
    app_state.orchestrator = orchestrator
    app = FastAPI()
    app.include_router(chat_router)
    app.include_router(admin_router)
    return TestClient(app)


def test_batch4_user_and_session_notes_are_stored_and_injected(tmp_path: Path) -> None:
    llm = RecordingLLM([
        '그는 짧게 시선을 들었다.\n\n"좋아, 전제를 맞춰보자."',
        '그는 고개를 조금 기울인다.\n\n"이번엔 네 기준에 맞춰서 간다."',
    ])
    client = _build_runtime_client(tmp_path, llm)

    user_note_put = client.put('/admin/user-notes/user_char_01', json={'data': {
        'note': '유저는 감정 과잉보다 명확한 구조를 선호한다.',
        'hard_constraints': ['반말 금지', '메타 발화 금지'],
        'preferred_dynamic': ['긴장 완화', '명시적 합의'],
        'relationship_expectation': '신뢰 가능한 협상 상대처럼 대우한다.',
    }})
    assert user_note_put.status_code == 200
    assert user_note_put.json()['item']['hard_constraints'] == ['반말 금지', '메타 발화 금지']

    first = client.post('/chat/ask', json={'question': '기준부터 맞추자.', 'stream': False, 'audience': 'admin', 'mode': 'fast', 'user_profile_id': 'user_char_01', 'character_id': 'bot_char_01', 'scene_id': 'scene_default', 'world_id': 'default'}, headers={'x-user': 'batch4_user'})
    assert first.status_code == 200
    session_id = first.json()['session_id']

    session_note_put = client.put(f'/admin/session-notes/{session_id}', json={'data': {
        'note': '이번 세션에서는 합의 문구를 명시적으로 확인해야 한다.',
        'hard_constraints': ['서두르지 말 것'],
        'preferred_dynamic': ['합의 확인', '긴장 완화'],
        'relationship_expectation': '압박 대신 조율을 우선한다.',
    }})
    assert session_note_put.status_code == 200
    assert session_note_put.json()['item']['relationship_expectation'] == '압박 대신 조율을 우선한다.'

    second = client.post('/chat/ask', json={'question': '이번 판은 압박 없이 가자.', 'session_id': session_id, 'stream': False, 'audience': 'admin', 'mode': 'fast', 'user_profile_id': 'user_char_01', 'character_id': 'bot_char_01', 'scene_id': 'scene_default', 'world_id': 'default'}, headers={'x-user': 'batch4_user'})
    assert second.status_code == 200

    user_prompt = llm.chat_calls[-1][1]['content']
    assert '유저 노트:' in user_prompt
    assert '세션 노트:' in user_prompt
    assert '반말 금지' in user_prompt
    assert '합의 확인' in user_prompt
    assert '신뢰 가능한 협상 상대처럼 대우한다.' in user_prompt
    assert '압박 대신 조율을 우선한다.' in user_prompt

    payload = second.json()
    applied = payload['prompt_watch']['applied_context']
    assert applied['user_note']['note'] == '유저는 감정 과잉보다 명확한 구조를 선호한다.'
    assert applied['session_note']['note'] == '이번 세션에서는 합의 문구를 명시적으로 확인해야 한다.'
    assert applied['user_note']['hard_constraints'] == ['반말 금지', '메타 발화 금지']
    assert applied['session_note']['preferred_dynamic'] == ['합의 확인', '긴장 완화']

    user_note_get = client.get('/admin/user-notes/user_char_01')
    assert user_note_get.status_code == 200
    assert user_note_get.json()['relationship_expectation'] == '신뢰 가능한 협상 상대처럼 대우한다.'

    session_note_get = client.get(f'/admin/session-notes/{session_id}')
    assert session_note_get.status_code == 200
    assert session_note_get.json()['hard_constraints'] == ['서두르지 말 것']

    user_note_delete = client.delete('/admin/user-notes/user_char_01')
    assert user_note_delete.status_code == 200
    session_note_delete = client.delete(f'/admin/session-notes/{session_id}')
    assert session_note_delete.status_code == 200
