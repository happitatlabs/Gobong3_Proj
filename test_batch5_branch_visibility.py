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


def _build_runtime_client(tmp_path: Path, llm: RecordingLLM) -> tuple[TestClient, object]:
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
    return TestClient(app), store


def test_batch5_branch_visibility_and_branch_aware_prompt(tmp_path: Path) -> None:
    llm = RecordingLLM([
        '그는 숨을 죽이며 낮게 말한다.\n\n"계약의 진실은 VIP booth 아래의 감사 장부와 연결돼 있어."',
        '그는 시선을 고정한 채 덧붙인다.\n\n"이제 루트가 열렸으니 더는 감출 이유가 없지."',
    ])
    client, store = _build_runtime_client(tmp_path, llm)

    first = client.post('/chat/ask', json={'question': '보안이 올라갔네. confession route로 들어간 거야?', 'stream': False, 'audience': 'admin', 'mode': 'fast', 'user_profile_id': 'user_char_01', 'character_id': 'bot_char_01', 'scene_id': 'scene_default', 'world_id': 'default'}, headers={'x-user': 'batch5_user'})
    assert first.status_code == 200
    session_id = first.json()['session_id']

    branch_put = client.put('/admin/state/branches/confession_route', json={'data': {
        'branch_id': 'confession_route',
        'route_flags': {'confession_route': True},
        'unlock_conditions': {'confession_route': True, 'high_alert': True},
        'hidden_facts_revealed': ['ipc_contract_truth'],
        'hidden_facts': [
            {
                'id': 'ipc_contract_truth',
                'fact': 'VIP booth 아래의 감사 장부가 IPC 계약의 진실과 연결된다.',
                'unlock_conditions': ['confession_route', 'high_alert'],
                'reveal_patterns': ['계약의 진실', 'contract truth'],
                'related_routes': ['confession_route'],
            },
            {
                'id': 'side_route_secret',
                'fact': '사이드 루트에서만 열리는 별도 비밀이다.',
                'unlock_conditions': ['side_route'],
                'reveal_patterns': ['side secret'],
                'related_routes': ['side_route'],
            },
        ],
        'active_objectives': ['루트 충돌 없이 정보를 공개한다.'],
    }})
    assert branch_put.status_code == 200

    session_put = client.put(f'/admin/state/sessions/{session_id}', json={'data': {
        'session_id': str(session_id),
        'branch_id': 'confession_route',
        'active_location': 'VIP booth',
        'active_phase': 'high_alert',
        'scene_flags': {'high_alert': True},
        'status_notes': ['route active'],
    }})
    assert session_put.status_code == 200

    second = client.post('/chat/ask', json={'question': '이제 공개 가능한 정보만 정리해봐.', 'session_id': session_id, 'stream': False, 'audience': 'admin', 'mode': 'fast', 'user_profile_id': 'user_char_01', 'character_id': 'bot_char_01', 'scene_id': 'scene_default', 'world_id': 'default'}, headers={'x-user': 'batch5_user'})
    assert second.status_code == 200

    user_prompt = llm.chat_calls[-1][1]['content']
    assert '브랜치 맥락:' in user_prompt
    assert 'confession_route' in user_prompt
    assert 'VIP booth 아래의 감사 장부가 IPC 계약의 진실과 연결된다.' in user_prompt
    assert 'side_route_secret' not in user_prompt
    assert '사이드 루트에서만 열리는 별도 비밀이다.' not in user_prompt

    payload = second.json()
    branch_context = payload['prompt_watch']['applied_context']['branch_context']
    assert branch_context['branch_id'] == 'confession_route'
    assert branch_context['route_flags']['confession_route'] is True
    assert branch_context['unlock_conditions']['high_alert'] is True
    assert branch_context['visible_hidden_facts'][0]['id'] == 'ipc_contract_truth'
    assert branch_context['visible_hidden_facts'][0]['fact'] == 'VIP booth 아래의 감사 장부가 IPC 계약의 진실과 연결된다.'
    assert all(item['id'] != 'side_route_secret' for item in branch_context['visible_hidden_facts'])
