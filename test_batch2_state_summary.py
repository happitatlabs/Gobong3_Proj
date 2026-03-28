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
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.chat_calls: list[list[dict[str, str]]] = []

    def get_model_for_mode(self, mode: str) -> str:
        return 'qwen3.5:9b'

    async def chat(self, messages, model=None, **kwargs):
        self.chat_calls.append(messages)
        return SimpleNamespace(text=self.response_text, thinking='', model=model or 'qwen3.5:9b')

    async def generate(self, prompt, system_prompt='', mode='fast', **kwargs):
        self.chat_calls.append([{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': prompt}])
        return SimpleNamespace(content=self.response_text)


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


def test_batch2_state_update_and_turn_summary_via_admin_api(tmp_path: Path) -> None:
    llm = RecordingLLM('그는 경계 어린 눈으로 VIP booth 안쪽을 훑는다.\n\n"계약의 진실은 아직 여기서 말할 수 없어."')
    client = _build_runtime_client(tmp_path, llm)
    response = client.post('/chat/ask', json={'question': '보안이 예민해졌네. confession route로 들어간 거야?', 'stream': False, 'audience': 'admin', 'mode': 'fast', 'user_profile_id': 'user_char_01', 'character_id': 'bot_char_01', 'scene_id': 'scene_default', 'world_id': 'default'}, headers={'x-user': 'batch2_user'})
    assert response.status_code == 200
    payload = response.json()
    session_id = payload['session_id']

    dynamic_state = payload['prompt_watch']['applied_context']['dynamic_state']
    assert dynamic_state['character']['emotion'] == 'guarded'
    assert dynamic_state['character']['location'] == 'VIP booth'
    assert dynamic_state['session']['branch_id'] == 'confession_route'
    assert dynamic_state['session']['active_phase'] == 'high_alert'
    assert dynamic_state['branch']['hidden_facts_revealed'] == ['ipc_contract_truth']

    state_debug = payload['state_debug']
    assert state_debug['state_changes']['character']['emotion'] == 'guarded'
    assert state_debug['turn_summary']['turn_index'] == 1
    assert state_debug['turn_summary']['speaker_id'] == 'bot_char_01'

    char_state = client.get('/admin/state/characters/bot_char_01')
    assert char_state.status_code == 200
    assert char_state.json()['emotion'] == 'guarded'
    assert char_state.json()['location'] == 'VIP booth'

    session_state = client.get(f'/admin/state/sessions/{session_id}')
    assert session_state.status_code == 200
    assert session_state.json()['branch_id'] == 'confession_route'
    assert session_state.json()['active_phase'] == 'high_alert'

    branch_state = client.get('/admin/state/branches/confession_route')
    assert branch_state.status_code == 200
    assert branch_state.json()['hidden_facts_revealed'] == ['ipc_contract_truth']

    summaries = client.get(f'/admin/turn-summaries/{session_id}')
    assert summaries.status_code == 200
    items = summaries.json()['items']
    assert len(items) == 1
    assert items[0]['speaker_id'] == 'bot_char_01'
    assert items[0]['turn_index'] == 1
    assert items[0]['summary'].startswith('그는 경계 어린 눈으로 VIP booth')

    override = client.put(f'/admin/state/sessions/{session_id}', json={'data': {'branch_id': 'confession_route', 'active_location': 'VIP booth', 'active_phase': 'cooldown', 'scene_flags': {'high_alert': False}, 'status_notes': ['manual override']}})
    assert override.status_code == 200
    assert override.json()['item']['active_phase'] == 'cooldown'
