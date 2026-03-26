from __future__ import annotations

import json
import uuid
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
from mellow_chat_runtime.routers.models import router as model_router
from mellow_chat_runtime.services.vector_retrieval_service import VectorRetrievalService


class RecordingLLM:
    def __init__(
        self,
        response_text: str | None = None,
        response_texts: list[str] | None = None,
        response_payloads: list[dict[str, str]] | None = None,
    ) -> None:
        self.response_text = response_text
        self.response_texts = list(response_texts or [])
        self.response_payloads = list(response_payloads or [])
        self.chat_calls: list[list[dict[str, str]]] = []
        self.chat_call_options: list[dict[str, object]] = []

    def get_model_for_mode(self, mode: str) -> str:
        return 'qwen3.5:9b'

    def _next_response(self, default_text: str) -> tuple[str, str]:
        if self.response_payloads:
            payload = self.response_payloads.pop(0)
            return str(payload.get('text', '')), str(payload.get('thinking', ''))
        if self.response_texts:
            return self.response_texts.pop(0), ''
        if self.response_text is not None:
            return self.response_text, ''
        return default_text, ''

    async def chat(self, messages, model=None, **kwargs):
        self.chat_calls.append(messages)
        self.chat_call_options.append(dict(kwargs))
        default_text = '어벤츄린은 차분히 상황을 정리한다.\n\n"필요한 정보만 골라서 답할게."'
        text, thinking = self._next_response(default_text)
        return SimpleNamespace(text=text, thinking=thinking, model=model or 'qwen3.5:9b')


def _reset_domain_store() -> None:
    domain_lookup_store_module._global_store = None


def _build_client(tmp_path: Path, llm: RecordingLLM) -> tuple[TestClient, object, VectorRetrievalService]:
    _reset_domain_store()
    domain_file = tmp_path / 'domain_data.json'
    vector_index_file = tmp_path / 'vector_index.json'
    store = domain_lookup_store_module.get_domain_store(data_path=domain_file)
    dispatcher = DomainLookupDispatcher(store)
    orchestrator = Orchestrator(lookup_dispatcher=dispatcher)
    orchestrator.register_service('llm', llm)
    vector_service = VectorRetrievalService(domain_store=store, index_path=vector_index_file)

    app_state.settings = SimpleNamespace(
        domain_data_file=domain_file,
        vector_index_file=vector_index_file,
        memory_promotion_enabled=False,
        memory_promotion_max_items=20,
    )
    app_state.orchestrator = orchestrator
    app_state.llm_service = llm
    app_state.vector_retrieval_service = vector_service

    app = FastAPI()
    app.include_router(chat_router)
    app.include_router(admin_router)
    app.include_router(model_router)
    return TestClient(app), store, vector_service


def test_models_catalog_filters_active_and_status_modes(tmp_path: Path) -> None:
    init_db()
    client, _, _ = _build_client(tmp_path, RecordingLLM())

    active = client.get('/models/catalog')
    deprecated = client.get('/models/catalog', params={'status': 'deprecated'})
    all_items = client.get('/models/catalog', params={'status': 'all'})
    admin_filtered = client.get('/models/catalog', params={'audience': 'admin', 'role_tag': 'qa_repro', 'status': 'all'})

    assert active.status_code == 200
    assert deprecated.status_code == 200
    assert all_items.status_code == 200
    assert all(item['status'] == 'active' for item in active.json())
    assert all(item['status'] == 'deprecated' for item in deprecated.json())
    assert len(all_items.json()) >= len(active.json())
    assert any(item['id'] == 'qa_repro_admin' for item in admin_filtered.json())
    assert all('admin' in item['audiences'] for item in admin_filtered.json())


def test_admin_model_catalog_crud_persists(tmp_path: Path) -> None:
    init_db()
    client, _, _ = _build_client(tmp_path, RecordingLLM())

    create = client.put(
        '/admin/models/test_model_01',
        json={
            'data': {
                'id': 'ignored_by_server',
                'label': 'Test Model',
                'provider': 'ollama',
                'model': 'qwen3.5:9b',
                'default_mode': 'fast',
                'role_tags': ['low_cost_test'],
                'audiences': ['admin'],
                'status': 'active',
                'description': 'temporary model',
            }
        },
    )
    assert create.status_code == 200
    assert create.json()['item']['id'] == 'test_model_01'

    listed = client.get('/admin/models').json()['items']
    assert any(item['id'] == 'test_model_01' for item in listed)

    deleted = client.delete('/admin/models/test_model_01')
    assert deleted.status_code == 200
    listed_after = client.get('/admin/models').json()['items']
    assert all(item['id'] != 'test_model_01' for item in listed_after)


def test_models_select_catalog_resolves_and_session_lookup_keeps_metadata(tmp_path: Path) -> None:
    init_db()
    client, _, _ = _build_client(tmp_path, RecordingLLM())
    username = f'user_{uuid.uuid4().hex[:8]}'

    selected = client.post(
        '/models/select',
        json={'selection': {'catalog_id': 'qa_repro_admin'}},
        headers={'x-user': username},
    )
    assert selected.status_code == 200
    selected_body = selected.json()
    assert selected_body['selected']['catalog_id'] == 'qa_repro_admin'
    assert selected_body['selected']['mode'] == 'research'
    assert selected_body['selected']['source'] == 'catalog'

    session_lookup = client.get(f"/models/sessions/{selected_body['session_id']}", headers={'x-user': username})
    assert session_lookup.status_code == 200
    lookup_body = session_lookup.json()
    assert lookup_body['selected']['catalog_id'] == 'qa_repro_admin'
    assert lookup_body['selected']['label'] == 'QA Repro'
    assert lookup_body['selected']['status'] == 'active'
    assert lookup_body['selected']['source'] == 'session'


def test_models_select_explicit_catalog_mismatch_returns_400(tmp_path: Path) -> None:
    init_db()
    client, _, _ = _build_client(tmp_path, RecordingLLM())

    response = client.post(
        '/models/select',
        json={
            'selection': {
                'provider': 'ollama',
                'model': 'qwen3.5:9b',
                'mode': 'fast',
                'catalog_id': 'qa_repro_admin',
            }
        },
        headers={'x-user': 'mismatch_user'},
    )

    assert response.status_code == 400
    assert 'catalog' in response.json()['detail'].lower()


def test_chat_prompt_watch_user_compact_uses_catalog_request_source(tmp_path: Path) -> None:
    init_db()
    llm = RecordingLLM('어벤츄린은 짧게 고개를 끄덕인다.\n\n"관련 카드만 추려서 말할게."')
    client, _, vector_service = _build_client(tmp_path, llm)
    vector_service.reindex()

    response = client.post(
        '/chat/ask',
        json={
            'question': 'IPC 규약과 station negotiation 이야기를 기억해?',
            'stream': False,
            'audience': 'user',
            'catalog_id': 'rp_stable_main',
            'user_profile_id': 'user_char_01',
            'character_id': 'bot_char_01',
            'scene_id': 'scene_default',
            'world_id': 'default',
            'lore_topics': ['IPC'],
        },
        headers={'x-user': 'catalog_prompt_watch_user'},
    )

    assert response.status_code == 200
    body = response.json()
    prompt_watch = body['prompt_watch']
    serialized = json.dumps(prompt_watch, ensure_ascii=False)
    assert prompt_watch['model']['source'] == 'catalog'
    assert prompt_watch['model']['catalog_id'] == 'rp_stable_main'
    assert prompt_watch['lore_hit_ids']
    assert prompt_watch['memory_hit_ids']
    assert 'applied_context' not in prompt_watch
    assert 'generation_path' not in prompt_watch
    assert '최근 대화' not in serialized
    assert 'IPC 규약과 station negotiation 이야기를 기억해?' not in serialized


def test_chat_prompt_watch_admin_detail_matches_applied_context(tmp_path: Path) -> None:
    init_db()
    llm = RecordingLLM('선데이는 차분히 시선을 들었다.\n\n"그래. 실제로 쓰인 맥락만 기준으로 답할게."')
    client, _, vector_service = _build_client(tmp_path, llm)
    vector_service.reindex()

    response = client.post(
        '/chat/ask',
        json={
            'question': '나는 천천히 고개를 들고 선데이를 바라봤다.\n"선데이, 그 말 진심이야?"',
            'stream': False,
            'audience': 'admin',
            'user_profile_id': 'user_char_01',
            'character_ids': ['bot_char_01', 'bot_char_02'],
            'scene_id': 'scene_default',
            'world_id': 'default',
            'lore_topics': ['IPC'],
        },
        headers={'x-user': 'admin_prompt_watch_user'},
    )

    assert response.status_code == 200
    body = response.json()
    prompt_watch = body['prompt_watch']
    assert 'retrieval_debug' in body
    assert 'rp_debug' in body
    assert prompt_watch['applied_context']['lore']
    assert prompt_watch['applied_context']['memories']
    assert prompt_watch['selected_speaker_id'] == body['speaker_id']
    assert prompt_watch['active_character_id'] == body['speaker_id']
    assert prompt_watch['target_character_hint'] == 'bot_char_02'
    assert prompt_watch['lore_hit_ids'] == [item['id'] for item in prompt_watch['applied_context']['lore']]
    assert prompt_watch['generation_path']['final_verdict'] == 'pass'


def test_chat_prompt_watch_source_resolution_paths(tmp_path: Path) -> None:
    init_db()
    client, _, _ = _build_client(tmp_path, RecordingLLM('어벤츄린은 조용히 계산을 마친다.\n\n"출처 경로를 확인해 봐."'))
    username = f'user_{uuid.uuid4().hex[:8]}'

    system_default = client.post(
        '/chat/ask',
        json={
            'question': '기본 경로로 답해.',
            'stream': False,
            'user_profile_id': 'user_char_01',
            'character_id': 'bot_char_01',
            'scene_id': 'scene_default',
            'world_id': 'default',
        },
        headers={'x-user': username},
    )
    assert system_default.status_code == 200
    assert system_default.json()['prompt_watch']['model']['source'] == 'system_default'

    selected = client.post('/models/select', json={'selection': {'catalog_id': 'qa_repro_admin'}}, headers={'x-user': username})
    assert selected.status_code == 200
    session_id = selected.json()['session_id']

    session_based = client.post(
        '/chat/ask',
        json={
            'session_id': session_id,
            'question': '세션 저장 모델로 답해.',
            'stream': False,
            'user_profile_id': 'user_char_01',
            'character_id': 'bot_char_01',
            'scene_id': 'scene_default',
            'world_id': 'default',
        },
        headers={'x-user': username},
    )
    assert session_based.status_code == 200
    assert session_based.json()['prompt_watch']['model']['source'] == 'session'

    explicit = client.post(
        '/chat/ask',
        json={
            'session_id': session_id,
            'question': '명시적 모델로 답해.',
            'stream': False,
            'provider': 'ollama',
            'model': 'qwen3.5:9b',
            'user_profile_id': 'user_char_01',
            'character_id': 'bot_char_01',
            'scene_id': 'scene_default',
            'world_id': 'default',
        },
        headers={'x-user': username},
    )
    assert explicit.status_code == 200
    assert explicit.json()['prompt_watch']['model']['source'] == 'explicit_request'


def test_chat_prompt_watch_repaired_and_fallback_verdicts(tmp_path: Path) -> None:
    init_db()
    repair_llm = RecordingLLM(response_texts=[
        '요청하신 대로 차분하고 정중한 말투로 답변드리겠습니다.',
        '선데이는 조용히 숨을 고른다.\n\n"그래. 지금은 그렇게 말할 수 있어."',
    ])
    repair_client, _, _ = _build_client(tmp_path / 'repair_case', repair_llm)

    repaired = repair_client.post(
        '/chat/ask',
        json={
            'question': '나는 천천히 고개를 들고 선데이를 바라봤다.\n"선데이, 그 말 진심이야?"',
            'stream': False,
            'audience': 'admin',
            'user_profile_id': 'user_char_01',
            'character_ids': ['bot_char_01', 'bot_char_02'],
            'scene_id': 'scene_default',
            'world_id': 'default',
        },
        headers={'x-user': 'repair_user'},
    )
    assert repaired.status_code == 200
    repaired_watch = repaired.json()['prompt_watch']
    assert repaired_watch['repair_used'] is True
    assert repaired_watch['generation_path']['final_verdict'] == 'repaired'

    fallback_llm = RecordingLLM(response_payloads=[
        {'text': '', 'thinking': 'I should answer in character.'},
        {'text': '', 'thinking': 'Still thinking.'},
    ])
    fallback_client, _, _ = _build_client(tmp_path / 'fallback_case', fallback_llm)
    fallback = fallback_client.post(
        '/chat/ask',
        json={
            'question': '나는 잠깐 숨을 멈추고 선데이를 바라봤다.\n"정말 솔직하게 말해줘."',
            'stream': False,
            'audience': 'admin',
            'user_profile_id': 'user_char_01',
            'character_ids': ['bot_char_01', 'bot_char_02'],
            'scene_id': 'scene_default',
            'world_id': 'default',
        },
        headers={'x-user': 'fallback_user'},
    )
    assert fallback.status_code == 200
    fallback_watch = fallback.json()['prompt_watch']
    assert fallback_watch['fallback_used'] is True
    assert fallback_watch['generation_path']['final_verdict'] == 'fallback'
