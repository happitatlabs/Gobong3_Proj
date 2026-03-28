from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import mellow_chat_runtime.app_state as app_state
import mellow_chat_runtime.core.domain_lookup_store as domain_lookup_store_module
from mellow_chat_runtime.core.agent_brain import AgentResult
from mellow_chat_runtime.core.domain_lookup_dispatcher import DomainLookupDispatcher
from mellow_chat_runtime.core.orchestrator import Orchestrator
from mellow_chat_runtime.core.states import TransitionResult
from mellow_chat_runtime.infra.database import init_db
from mellow_chat_runtime.routers.admin import router as admin_router
from mellow_chat_runtime.routers.chat import router as chat_router


class RecordingLLM:
    def __init__(self) -> None:
        self.chat_calls: list[list[dict[str, str]]] = []

    def get_model_for_mode(self, mode: str) -> str:
        return 'qwen3.5:9b'

    async def chat(self, messages, model=None, **kwargs):
        self.chat_calls.append(messages)
        return SimpleNamespace(text='그는 숨을 고르고 시선을 고정한다.\n\n"reply"', thinking='', model=model or 'qwen3.5:9b')

    async def generate(self, prompt, system_prompt='', mode='fast', **kwargs):
        self.chat_calls.append([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': prompt},
        ])
        return SimpleNamespace(content='그는 짧게 숨을 고른다.\n\n"fallback"')


class FakeOrchestrator:
    async def request_state_change(self, target_state, reason: str = ''):
        return TransitionResult.SUCCESS

    async def run_agent(self, **kwargs):
        return AgentResult(answer='그는 짧게 눈을 좁힌다.\n\n"reply"')


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

    app_state.settings = SimpleNamespace(
        domain_data_file=domain_file,
        memory_promotion_enabled=False,
        memory_promotion_max_items=20,
    )
    app_state.llm_service = llm
    app_state.orchestrator = orchestrator

    app = FastAPI()
    app.include_router(chat_router)
    app.include_router(admin_router)
    return TestClient(app), store


def test_domain_store_state_defaults_and_upserts(tmp_path: Path) -> None:
    client, store = _build_runtime_client(tmp_path, RecordingLLM())
    assert client is not None

    assert store.get_character_state('fresh_char') == {
        'character_id': 'fresh_char',
        'emotion': 'neutral',
        'location': '',
        'outfit': '',
        'scene_flags': {},
        'relationship_delta': {},
        'status_notes': [],
    }

    store.upsert_character_state(
        'fresh_char',
        {
            'emotion': 'guarded',
            'location': 'VIP booth',
            'scene_flags': {'guarded': True},
            'relationship_delta': {'user_char_01': 1.5},
            'status_notes': ['긴장을 숨기고 있다.'],
        },
    )
    store.upsert_session_state(
        'session-42',
        {
            'branch_id': 'confession_route',
            'active_location': 'VIP booth',
            'active_phase': 'high_alert',
            'scene_flags': {'high_alert': True},
            'status_notes': ['보안 시선이 집중된다.'],
        },
    )
    store.upsert_branch_state(
        'confession_route',
        {
            'route_flags': {'confession_route': True},
            'hidden_facts_revealed': ['ipc_contract_truth'],
            'active_objectives': ['대화를 정면 충돌 없이 유지한다.'],
        },
    )

    assert store.get_character_state('fresh_char')['emotion'] == 'guarded'
    assert store.get_session_state('session-42')['active_phase'] == 'high_alert'
    assert store.get_branch_state('confession_route')['hidden_facts_revealed'] == ['ipc_contract_truth']


def test_chat_prompt_includes_dynamic_state_block_and_prompt_watch(tmp_path: Path) -> None:
    llm = RecordingLLM()
    client, store = _build_runtime_client(tmp_path, llm)

    first = client.post(
        '/chat/ask',
        json={
            'question': '처음 장면을 연다.',
            'stream': False,
            'audience': 'admin',
            'mode': 'fast',
            'user_profile_id': 'user_char_01',
            'character_id': 'bot_char_01',
            'scene_id': 'scene_default',
            'world_id': 'default',
        },
        headers={'x-user': 'batch1_user'},
    )
    assert first.status_code == 200
    session_id = first.json()['session_id']

    store.upsert_character_state(
        'bot_char_01',
        {
            'character_id': 'bot_char_01',
            'emotion': 'guarded',
            'location': 'VIP booth',
            'outfit': 'black suit',
            'scene_flags': {'guarded': True},
            'relationship_delta': {'user_char_01': 1.5},
            'status_notes': ['속내를 감추고 있다.'],
        },
    )
    store.upsert_session_state(
        str(session_id),
        {
            'session_id': str(session_id),
            'branch_id': 'confession_route',
            'active_location': 'VIP booth',
            'active_phase': 'high_alert',
            'scene_flags': {'high_alert': True},
            'status_notes': ['테이블 아래에서 거래가 진행 중이다.'],
        },
    )
    store.upsert_branch_state(
        'confession_route',
        {
            'branch_id': 'confession_route',
            'route_flags': {'confession_route': True},
            'hidden_facts_revealed': ['ipc_contract_truth'],
            'active_objectives': ['비밀을 드러내지 않고 협상을 지속한다.'],
        },
    )

    response = client.post(
        '/chat/ask',
        json={
            'question': '지금 표정이 굳었네.',
            'session_id': session_id,
            'stream': False,
            'audience': 'admin',
            'mode': 'fast',
            'user_profile_id': 'user_char_01',
            'character_id': 'bot_char_01',
            'scene_id': 'scene_default',
            'world_id': 'default',
        },
        headers={'x-user': 'batch1_user'},
    )

    assert response.status_code == 200
    user_prompt = llm.chat_calls[-1][1]['content']
    assert '동적 상태:' in user_prompt
    assert 'guarded' in user_prompt
    assert 'VIP booth' in user_prompt
    assert 'confession_route' in user_prompt
    assert 'high_alert' in user_prompt
    assert 'ipc_contract_truth' in user_prompt

    payload = response.json()
    dynamic_state = payload['prompt_watch']['applied_context']['dynamic_state']
    assert dynamic_state['character']['emotion'] == 'guarded'
    assert dynamic_state['session']['active_phase'] == 'high_alert'
    assert dynamic_state['branch']['hidden_facts_revealed'] == ['ipc_contract_truth']
