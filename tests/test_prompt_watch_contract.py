from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mellow_chat_runtime.runtime.schemas import PromptWatchCompact, PromptWatchDetail
from mellow_chat_runtime.routers.prompt_watch_ui import router as prompt_watch_ui_router


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "prompt_watch"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_admin_prompt_watch_fixture_matches_detail_schema() -> None:
    payload = _load_fixture("admin_success_detail.json")

    watch = PromptWatchDetail.model_validate(payload["prompt_watch"])

    assert payload["session_id"] == 314
    assert watch.active_character_name == "어벤츄린"
    assert watch.applied_context.dynamic_state.character.emotion == "흥미를 보이며 침착함"
    assert watch.applied_context.dynamic_state.session.branch_id == "ipc_route"
    assert watch.applied_context.session_summary.turn_count == 4
    assert len(watch.applied_context.confirmed_facts) == 2
    assert watch.applied_context.branch_context.visible_hidden_facts[0].id == "hf_contract_leverage"
    assert watch.applied_context.user_note.profile_id == "user_char_01"
    assert watch.applied_context.session_note.session_id == "314"


def test_admin_prompt_watch_fixture_contains_latest_applied_context_sections() -> None:
    payload = _load_fixture("admin_success_detail.json")

    applied_context = payload["prompt_watch"]["applied_context"]

    assert {
        "scene",
        "dynamic_state",
        "session_summary",
        "confirmed_facts",
        "branch_context",
        "user_note",
        "session_note",
        "relationships",
        "lore",
        "memories",
    }.issubset(applied_context.keys())


def test_user_prompt_watch_fixture_matches_compact_schema() -> None:
    payload = _load_fixture("user_success_compact.json")

    watch = PromptWatchCompact.model_validate(payload["prompt_watch"])

    assert payload["session_id"] == 314
    assert watch.active_character_name == "어벤츄린"
    assert watch.model.source == "catalog"
    assert watch.fallback_used is False


def test_unavailable_fixture_keeps_prompt_watch_null() -> None:
    payload = _load_fixture("user_validation_failure_unavailable.json")

    assert payload["isSuccessResponse"] is False
    assert payload["prompt_watch"] is None
    assert payload["error_code"] == "NARRATION_RULE_FAILED"


def test_prompt_watch_qa_page_includes_admin_action_copy() -> None:
    app = FastAPI()
    app.include_router(prompt_watch_ui_router)
    client = TestClient(app)

    response = client.get("/qa/prompt-watch")

    assert response.status_code == 200
    html = response.text
    assert "운영 액션" in html
    assert "Prompt Watch는 읽기 전용입니다." in html
    assert "캐릭터 상태" in html
    assert "PUT 템플릿" in html
