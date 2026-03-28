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


def test_batch3_session_summary_confirmed_facts_and_contradiction_debug(tmp_path: Path) -> None:
    llm = RecordingLLM([
        '그는 목소리를 낮춘다.\n\n"계약의 진실은 여기 있다."',
        '그는 고개를 젓는다.\n\n"계약의 진실은 없어."',
    ])
    client = _build_runtime_client(tmp_path, llm)

    first = client.post('/chat/ask', json={'question': '핵심만 말해.', 'stream': False, 'audience': 'admin', 'mode': 'fast', 'user_profile_id': 'user_char_01', 'character_id': 'bot_char_01', 'scene_id': 'scene_default', 'world_id': 'default'}, headers={'x-user': 'batch3_user'})
    assert first.status_code == 200
    session_id = first.json()['session_id']
    first_debug = first.json()['state_debug']
    assert first_debug['session_summary']['turn_count'] == 1
    assert any('계약의 진실은 여기 있다.' in item['fact'] for item in first_debug['confirmed_facts'])

    second = client.post('/chat/ask', json={'question': '아까 한 말 다시 확인해.', 'session_id': session_id, 'stream': False, 'audience': 'admin', 'mode': 'fast', 'user_profile_id': 'user_char_01', 'character_id': 'bot_char_01', 'scene_id': 'scene_default', 'world_id': 'default'}, headers={'x-user': 'batch3_user'})
    assert second.status_code == 200

    user_prompt = llm.chat_calls[-1][1]['content']
    assert '확정 사실:' in user_prompt
    assert '세션 요약:' in user_prompt
    assert '계약의 진실은 여기 있다.' in user_prompt

    payload = second.json()
    state_debug = payload['state_debug']
    assert state_debug['session_summary']['turn_count'] == 2
    assert state_debug['contradictions']
    assert '계약의 진실은 여기 있다.' in state_debug['contradictions'][0]['fact']
    assert '계약의 진실은 없어.' in state_debug['contradictions'][0]['candidate']

    session_summary = payload['prompt_watch']['applied_context']['session_summary']
    assert session_summary['turn_count'] == 2
    confirmed_facts = payload['prompt_watch']['applied_context']['confirmed_facts']
    assert any('계약의 진실은 여기 있다.' in item['summary_text'] for item in confirmed_facts)

    session_summary_api = client.get(f'/admin/session-summaries/{session_id}')
    assert session_summary_api.status_code == 200
    assert session_summary_api.json()['turn_count'] == 2

    confirmed_facts_api = client.get(f'/admin/confirmed-facts/{session_id}')
    assert confirmed_facts_api.status_code == 200
    assert any('계약의 진실은 여기 있다.' in item['fact'] for item in confirmed_facts_api.json()['items'])
