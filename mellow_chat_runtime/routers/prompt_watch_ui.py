from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from mellow_chat_runtime import app_state
from mellow_chat_runtime.core.domain_lookup_store import get_domain_store

router = APIRouter(tags=["QA"])

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "prompt_watch"
_ALLOWED_FIXTURES = {
    "admin_success_detail": _FIXTURE_DIR / "admin_success_detail.json",
    "user_success_compact": _FIXTURE_DIR / "user_success_compact.json",
    "user_validation_failure_unavailable": _FIXTURE_DIR / "user_validation_failure_unavailable.json",
}


def _store():
    settings = app_state.settings
    data_path = getattr(settings, "domain_data_file", None) if settings else None
    return get_domain_store(data_path=data_path)


@router.get("/qa/prompt-watch", response_class=HTMLResponse)
async def prompt_watch_ui() -> HTMLResponse:
    return HTMLResponse(_build_prompt_watch_html())


@router.get("/qa/prompt-watch/fixtures/{fixture_name}")
async def prompt_watch_fixture(fixture_name: str) -> JSONResponse:
    fixture_path = _ALLOWED_FIXTURES.get(fixture_name)
    if fixture_path is None:
        raise HTTPException(status_code=404, detail="Fixture not found")
    return JSONResponse(_read_fixture_json(fixture_path))


@router.get("/qa/prompt-watch/options")
async def prompt_watch_options() -> JSONResponse:
    store = _store()
    user_characters = list(store.list_section("user_characters").values())
    bot_characters = list(store.list_section("bot_characters").values())
    models = list(store.list_model_catalog(audience="admin", status="active").values())
    scenes = list(store.list_section("scene_state").values())
    worlds = list(store.list_section("world_state").values())
    lore_items = list(store.list_section("lorebook").values())
    return JSONResponse(
        {
            "user_characters": user_characters,
            "bot_characters": bot_characters,
            "models": models,
            "scenes": scenes,
            "worlds": worlds,
            "lore_items": lore_items,
        }
    )


def _read_fixture_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_prompt_watch_html() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Prompt Watch QA</title>
    <style>
      :root {
        --bg: #f4efe6;
        --panel: #fffaf2;
        --ink: #1e1c19;
        --muted: #6a6258;
        --line: #d6c9b8;
        --accent: #0f766e;
        --accent-soft: #dff4f1;
        --warn: #b45309;
        --warn-soft: #fff2db;
        --danger: #991b1b;
        --danger-soft: #fde7e7;
        --mono: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
        --sans: "Segoe UI", system-ui, sans-serif;
      }

      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: var(--sans);
        color: var(--ink);
        background:
          radial-gradient(circle at top left, #fff9ef 0, #fff9ef 18%, transparent 18%) 0 0 / 120px 120px,
          linear-gradient(180deg, #f8f2e8 0%, #f2eadf 100%);
      }

      .page {
        max-width: 1200px;
        margin: 0 auto;
        padding: 32px 20px 56px;
      }

      .hero {
        display: grid;
        gap: 12px;
        margin-bottom: 24px;
      }

      .eyebrow {
        font-size: 12px;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: var(--accent);
        font-weight: 700;
      }

      h1 {
        margin: 0;
        font-size: clamp(28px, 4vw, 44px);
        line-height: 1;
      }

      .sub {
        margin: 0;
        color: var(--muted);
        max-width: 780px;
        line-height: 1.5;
      }

      .layout {
        display: grid;
        gap: 20px;
      }

      @media (min-width: 980px) {
        .layout {
          grid-template-columns: minmax(320px, 420px) minmax(0, 1fr);
          align-items: start;
        }
      }

      .panel {
        background: color-mix(in srgb, var(--panel) 90%, white 10%);
        border: 1px solid var(--line);
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(61, 47, 29, 0.08);
      }

      .panel-body {
        padding: 18px;
      }

      .controls {
        display: grid;
        gap: 14px;
      }

      .button-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }

      button {
        border: 1px solid var(--line);
        background: #fffdf8;
        color: var(--ink);
        border-radius: 999px;
        padding: 10px 14px;
        font: inherit;
        cursor: pointer;
      }

      button.primary {
        background: var(--accent);
        color: white;
        border-color: var(--accent);
      }

      textarea {
        width: 100%;
        min-height: 360px;
        resize: vertical;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 14px;
        font-family: var(--mono);
        font-size: 13px;
        line-height: 1.5;
        background: #fffefb;
        color: var(--ink);
      }

      .hint {
        margin: 0;
        font-size: 13px;
        color: var(--muted);
        line-height: 1.5;
      }

      .status-box {
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 12px 14px;
        background: #fffefb;
        color: var(--ink);
        font-size: 14px;
        line-height: 1.5;
      }

      .status-box strong {
        display: inline-block;
        margin-right: 8px;
      }

      input[type="text"],
      select {
        width: 100%;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 11px 12px;
        font: inherit;
        background: #fffefb;
        color: var(--ink);
      }

      .composer {
        display: grid;
        gap: 14px;
      }

      .field-grid {
        display: grid;
        gap: 12px;
      }

      @media (min-width: 720px) {
        .field-grid.two {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }

      .field label {
        display: block;
        margin-bottom: 8px;
        color: var(--muted);
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 700;
      }

      .target-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }

      .target-btn {
        border: 1px solid var(--line);
        background: #fffdf8;
        color: var(--ink);
        border-radius: 16px;
        padding: 12px 14px;
        min-width: 120px;
        text-align: left;
      }

      .target-btn.active {
        background: var(--accent-soft);
        border-color: #9fd7cf;
        color: var(--accent);
      }

      .target-btn strong {
        display: block;
        font-size: 14px;
        margin-bottom: 4px;
      }

      .target-btn span {
        display: block;
        font-size: 12px;
        line-height: 1.4;
        color: inherit;
        opacity: 0.9;
      }

      .target-status {
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 12px 14px;
        background: rgba(255, 255, 255, 0.72);
      }

      .persona-note {
        margin-top: 10px;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 12px 14px;
        background: rgba(255, 255, 255, 0.72);
      }

      .persona-note strong {
        display: block;
        margin-bottom: 6px;
        font-size: 13px;
      }

      .target-status strong {
        display: block;
        margin-bottom: 6px;
        font-size: 13px;
      }

      .check-grid {
        display: grid;
        gap: 10px;
      }

      .check-item {
        display: flex;
        gap: 10px;
        align-items: flex-start;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 10px 12px;
        background: rgba(255, 255, 255, 0.7);
      }

      .check-item input {
        margin-top: 2px;
      }

      .check-copy {
        display: grid;
        gap: 4px;
      }

      .check-copy strong {
        font-size: 14px;
      }

      .check-copy span {
        color: var(--muted);
        font-size: 13px;
        line-height: 1.4;
      }

      .response-box {
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 16px;
        background: rgba(255, 255, 255, 0.76);
        white-space: pre-wrap;
        line-height: 1.6;
      }

      .mini-note {
        margin: 0;
        color: var(--muted);
        font-size: 13px;
        line-height: 1.5;
      }

      .render-root {
        display: grid;
        gap: 16px;
      }

      .watch-card {
        display: grid;
        gap: 14px;
      }

      .card-header {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
        justify-content: space-between;
      }

      .title-wrap {
        display: grid;
        gap: 4px;
      }

      .card-title {
        margin: 0;
        font-size: 24px;
      }

      .card-subtitle {
        margin: 0;
        color: var(--muted);
      }

      .badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border-radius: 999px;
        padding: 6px 10px;
        font-size: 12px;
        font-weight: 700;
        border: 1px solid transparent;
      }

      .badge.ok { background: var(--accent-soft); color: var(--accent); border-color: #b8e6df; }
      .badge.warn { background: var(--warn-soft); color: var(--warn); border-color: #f4d5a9; }
      .badge.danger { background: var(--danger-soft); color: var(--danger); border-color: #efb7b7; }
      .badge.neutral { background: #f7f1e8; color: #64594b; border-color: var(--line); }

      .grid {
        display: grid;
        gap: 12px;
      }

      @media (min-width: 720px) {
        .grid.two {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }

      .metric {
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 14px;
        background: rgba(255, 255, 255, 0.65);
      }

      .metric label {
        display: block;
        margin-bottom: 8px;
        color: var(--muted);
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 700;
      }

      .metric .value {
        font-size: 16px;
        line-height: 1.4;
        word-break: break-word;
      }

      .section-title {
        margin: 6px 0 0;
        font-size: 15px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
      }

      .summary-list {
        display: grid;
        gap: 10px;
      }

      .summary-item {
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 12px;
        background: #fffefb;
      }

      .summary-item strong {
        display: block;
        margin-bottom: 6px;
      }

      .section-block {
        display: grid;
        gap: 12px;
        padding-top: 4px;
      }

      .section-copy {
        margin: 0;
        color: var(--muted);
        font-size: 14px;
        line-height: 1.5;
      }

      .split-grid {
        display: grid;
        gap: 12px;
      }

      @media (min-width: 980px) {
        .split-grid {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }
      }

      .subcard {
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 14px;
        background: rgba(255, 255, 255, 0.74);
        display: grid;
        gap: 10px;
      }

      .subcard h3 {
        margin: 0;
        font-size: 15px;
      }

      .subcard-copy {
        margin: 0;
        color: var(--muted);
        font-size: 13px;
        line-height: 1.5;
      }

      .chip-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        max-width: 100%;
        padding: 7px 10px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: #fffdf8;
        font-size: 12px;
        line-height: 1.4;
      }

      .chip strong {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--muted);
      }

      .stack-list {
        display: grid;
        gap: 8px;
      }

      .stack-item {
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 10px 12px;
        background: #fffefb;
      }

      .stack-item strong {
        display: block;
        margin-bottom: 4px;
        font-size: 12px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }

      .action-grid {
        display: grid;
        gap: 12px;
      }

      @media (min-width: 980px) {
        .action-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }

      .action-card {
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 14px;
        background: rgba(255, 255, 255, 0.74);
        display: grid;
        gap: 10px;
      }

      .action-card h3 {
        margin: 0;
        font-size: 15px;
      }

      .action-meta {
        font-size: 13px;
        color: var(--muted);
        line-height: 1.5;
        word-break: break-word;
      }

      .action-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .action-btn {
        border-radius: 999px;
        padding: 8px 12px;
        font-size: 13px;
      }

      .action-btn.secondary {
        background: #fff7ed;
        border-color: #f2cfaa;
      }

      .action-btn:disabled {
        cursor: not-allowed;
        opacity: 0.55;
      }

      details {
        border: 1px solid var(--line);
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.72);
      }

      summary {
        cursor: pointer;
        padding: 14px 16px;
        font-weight: 700;
      }

      .details-body {
        padding: 0 16px 16px;
      }

      pre {
        margin: 0;
        padding: 14px;
        border-radius: 14px;
        background: #1d1f21;
        color: #eef2f3;
        overflow: auto;
        font-family: var(--mono);
        font-size: 12px;
        line-height: 1.5;
      }

      .empty {
        border: 1px dashed var(--line);
        border-radius: 20px;
        padding: 28px 18px;
        background: rgba(255, 255, 255, 0.48);
      }

      .empty h2 {
        margin: 0 0 8px;
      }

      .empty p {
        margin: 0;
        color: var(--muted);
      }
    </style>
  </head>
  <body>
    <div class="page">
      <header class="hero">
        <div class="eyebrow">QA 화면</div>
        <h1>프롬프트 워치</h1>
        <p class="sub">
          이 화면은 백엔드 응답 JSON을 사람이 읽기 쉬운 형태로 보여주는 QA 전용 디버그 뷰입니다.
          채팅 기능이 아니라 응답 확인용 화면이며, 나중에 별도로 쉽게 제거할 수 있게 분리되어 있습니다.
        </p>
      </header>

      <div class="layout">
        <section class="panel">
          <div class="panel-body controls">
            <div class="composer">
              <div class="section-title">간단 대화 테스트</div>
              <p class="hint">Swagger 대신 여기서 바로 질문을 보내고, 응답 텍스트와 Prompt Watch를 함께 확인할 수 있습니다.</p>

              <div class="field-grid two">
                <div class="field">
                  <label for="x-user-input">x-user</label>
                  <input id="x-user-input" type="text" value="qa_user" />
                </div>
                <div class="field">
                  <label for="audience-select">응답 타입</label>
                  <select id="audience-select">
                    <option value="admin" selected>admin 상세</option>
                    <option value="user">user 간단</option>
                  </select>
                </div>
              </div>

              <div class="field-grid two">
                <div class="field">
                  <label for="user-character-select">내 캐릭터</label>
                  <select id="user-character-select"></select>
                  <div class="persona-note" id="user-character-note">
                    <strong>현재 해석 프레임</strong>
                    <span>기본형 개척자 설명을 불러오는 중입니다.</span>
                  </div>
                </div>
                <div class="field">
                  <label for="model-mode-select">모드</label>
                  <select id="model-mode-select">
                    <option value="fast" selected>fast</option>
                    <option value="thinking">thinking</option>
                    <option value="research">research</option>
                  </select>
                </div>
              </div>

              <div class="field-grid two">
                <div class="field">
                <label for="scene-select">장면 ID</label>
                  <select id="scene-select"></select>
                </div>
                <div class="field">
                  <label for="world-select">월드 ID</label>
                  <select id="world-select"></select>
                </div>
              </div>

              <div class="field">
                <label>대상 전환</label>
                <div class="target-row" id="target-button-row"></div>
                <div class="target-status" id="target-status">
                  <strong>현재 대상</strong>
                  <span>자동 선택</span>
                </div>
              </div>

              <div class="field">
                <label>AI 캐릭터 후보</label>
                <div class="check-grid" id="bot-character-list"></div>
              </div>

              <div class="field">
                <label for="lore-topic-input">로어 토픽</label>
                <input id="lore-topic-input" type="text" value="IPC" />
              </div>

              <div class="field">
                <label for="question-input">질문</label>
                <textarea id="question-input" spellcheck="false">"어벤츄린, 먼저 네 생각부터 말해줘."</textarea>
              </div>

              <div class="button-row">
                <button class="primary" id="send-chat-btn">질문 보내기</button>
                <button id="reset-session-btn">세션 초기화</button>
              </div>

              <div class="mini-note" id="session-note">현재 세션 ID: 새 세션</div>

              <div>
                <div class="section-title">응답 텍스트</div>
                <div class="response-box" id="response-box">아직 응답이 없습니다.</div>
              </div>
            </div>

            <div>
              <div class="section-title">샘플 불러오기</div>
              <div class="button-row">
                <button data-fixture="admin_success_detail">관리자 상세 샘플</button>
                <button data-fixture="user_success_compact">유저 간단 샘플</button>
                <button data-fixture="user_validation_failure_unavailable">실패 샘플</button>
              </div>
            </div>

            <div>
              <div class="section-title">사용 방법</div>
              <p class="hint">먼저 위 샘플 버튼을 누르세요. 실제 테스트를 하고 싶으면 `/chat/ask`의 응답 JSON 전체를 아래 칸에 붙여넣고 `렌더링`을 누르면 됩니다.</p>
            </div>

            <div class="status-box" id="status-box">
              <strong>상태</strong>
              <span>샘플을 불러오는 중입니다.</span>
            </div>

            <textarea id="payload-input" spellcheck="false"></textarea>

            <div class="button-row">
              <button class="primary" id="render-btn">렌더링</button>
              <button id="format-btn">JSON 정리</button>
              <button id="clear-btn">초기화</button>
            </div>
          </div>
        </section>

        <section class="render-root" id="render-root"></section>
      </div>
    </div>

    <script>
      const input = document.getElementById("payload-input");
      const renderRoot = document.getElementById("render-root");
      const statusBox = document.getElementById("status-box");
      const responseBox = document.getElementById("response-box");
      const sessionNote = document.getElementById("session-note");
      const xUserInput = document.getElementById("x-user-input");
      const audienceSelect = document.getElementById("audience-select");
      const userCharacterSelect = document.getElementById("user-character-select");
      const modeSelect = document.getElementById("model-mode-select");
      const sceneSelect = document.getElementById("scene-select");
      const worldSelect = document.getElementById("world-select");
      const userCharacterNote = document.getElementById("user-character-note");
      const targetButtonRow = document.getElementById("target-button-row");
      const targetStatus = document.getElementById("target-status");
      const botCharacterList = document.getElementById("bot-character-list");
      const loreTopicInput = document.getElementById("lore-topic-input");
      const questionInput = document.getElementById("question-input");
      const sendChatBtn = document.getElementById("send-chat-btn");
      const resetSessionBtn = document.getElementById("reset-session-btn");
      const state = {
        currentSessionId: null,
        targetMode: "auto",
        targetCharacterId: null,
        botCharacters: [],
        userCharacters: [],
        lastActionResult: null,
      };
      const QUESTION_PLACEHOLDERS = {
        auto: '예: "둘 다 들어봐. 지금 누가 먼저 답해야 할지 보자."',
        bot_char_01: '예: "어벤츄린, 이번 거래에서 제일 중요한 포인트만 말해줘."',
        bot_char_02: '예: "선데이, 이 계획에서 가장 신중하게 봐야 할 부분을 말해줘."',
      };

      function setStatus(title, message) {
        statusBox.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(message)}</span>`;
      }

      function setSessionNote() {
        sessionNote.textContent = state.currentSessionId ? `현재 세션 ID: ${state.currentSessionId}` : "현재 세션 ID: 새 세션";
      }

      function setResponseText(value) {
        responseBox.textContent = value && String(value).trim() ? String(value) : "아직 응답이 없습니다.";
      }

      function setTargetStatus(title, detail) {
        targetStatus.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(detail)}</span>`;
      }

      function setUserCharacterNote(item) {
        const displayName = item && (item.display_name || item.name || item.id) ? (item.display_name || item.name || item.id) : "개척자";
        const summary = item && (item.selection_hint || item.persona || item.profile)
          ? (item.selection_hint || item.persona || item.profile)
          : "기본형 개척자";
        const style = item && item.interpretation_style && typeof item.interpretation_style === "object"
          ? [
              item.interpretation_style.risk_view,
              item.interpretation_style.decision_speed,
              item.interpretation_style.response_style,
            ].filter(Boolean).join(" / ")
          : "";
        userCharacterNote.innerHTML = `
          <strong>${escapeHtml(displayName)}</strong>
          <span>${escapeHtml(style ? `${summary} | ${style}` : summary)}</span>
        `;
      }

      function escapeHtml(value) {
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;");
      }

      function truncate(value, max = 220) {
        const text = String(value ?? "").trim();
        if (text.length <= max) return text;
        return text.slice(0, max - 3).trimEnd() + "...";
      }

      function renderJsonBlock(value) {
        return `<pre>${escapeHtml(JSON.stringify(value ?? null, null, 2))}</pre>`;
      }

      function fillSelect(element, items, formatter, fallbackLabel) {
        const safeItems = Array.isArray(items) ? items : [];
        if (!safeItems.length) {
          element.innerHTML = `<option value="">${escapeHtml(fallbackLabel)}</option>`;
          return;
        }
        element.innerHTML = safeItems.map((item, index) => {
          const shape = formatter(item, index);
          return `<option value="${escapeHtml(shape.value)}" ${shape.selected ? "selected" : ""}>${escapeHtml(shape.label)}</option>`;
        }).join("");
      }

      function syncBotCheckboxes() {
        const checkboxes = Array.from(botCharacterList.querySelectorAll('input[type="checkbox"]'));
        if (!checkboxes.length) {
          return;
        }
        if (state.targetMode === "auto") {
          checkboxes.forEach((checkbox, index) => {
            checkbox.checked = index < 2;
          });
          return;
        }
        checkboxes.forEach((checkbox) => {
          checkbox.checked = checkbox.value === state.targetCharacterId;
        });
      }

      function updateQuestionPlaceholder() {
        const placeholder = QUESTION_PLACEHOLDERS[state.targetCharacterId] || QUESTION_PLACEHOLDERS[state.targetMode] || QUESTION_PLACEHOLDERS.auto;
        questionInput.placeholder = placeholder;
      }

      function syncUserCharacterNote() {
        const selectedId = userCharacterSelect.value;
        const current = state.userCharacters.find((item) => item.id === selectedId);
        setUserCharacterNote(current || null);
      }

      function renderTargetButtons() {
        const buttons = [
          {
            key: "auto",
            title: "자동 선택",
            body: "두 캐릭터를 후보로 두고, 시스템이 이번 턴 화자를 고릅니다.",
          },
          ...state.botCharacters.map((item) => ({
            key: item.id,
            title: `${item.name || item.id}에게`,
            body: item.id === "bot_char_01"
              ? "어벤츄린에게 바로 묻습니다."
              : item.id === "bot_char_02"
                ? "선데이에게 바로 묻습니다."
                : "이 캐릭터를 현재 대상으로 고정합니다.",
          })),
        ];
        targetButtonRow.innerHTML = buttons.map((item) => `
          <button class="target-btn ${((item.key === 'auto' && state.targetMode === 'auto') || item.key === state.targetCharacterId) ? 'active' : ''}" type="button" data-target-key="${escapeHtml(item.key)}">
            <strong>${escapeHtml(item.title)}</strong>
            <span>${escapeHtml(item.body)}</span>
          </button>
        `).join("");
        targetButtonRow.querySelectorAll("[data-target-key]").forEach((button) => {
          button.addEventListener("click", () => {
            const key = button.getAttribute("data-target-key");
            if (key === "auto") {
              state.targetMode = "auto";
              state.targetCharacterId = null;
              setTargetStatus("현재 대상: 자동 선택", "두 캐릭터를 모두 후보로 두고, 이번 턴 화자를 자동으로 고릅니다.");
            } else {
              state.targetMode = "single";
              state.targetCharacterId = key;
              const target = state.botCharacters.find((item) => item.id === key);
              setTargetStatus(`현재 대상: ${target ? target.name : key}`, "이 캐릭터를 직접 호출하는 형태로 질문을 보낼 수 있습니다.");
            }
            syncBotCheckboxes();
            updateQuestionPlaceholder();
            renderTargetButtons();
          });
        });
      }

      function renderBotCharacterChoices(items) {
        const safeItems = Array.isArray(items) ? items : [];
        state.botCharacters = safeItems;
        if (!safeItems.length) {
          botCharacterList.innerHTML = `<div class="metric"><label>캐릭터</label><div class="value">선택할 AI 캐릭터가 없습니다.</div></div>`;
          return;
        }
        botCharacterList.innerHTML = safeItems.map((item, index) => `
          <label class="check-item">
            <input type="checkbox" value="${escapeHtml(item.id || "")}" ${index < 2 ? "checked" : ""} />
            <span class="check-copy">
              <strong>${escapeHtml(item.name || item.id || "bot")}</strong>
              <span>${escapeHtml(item.profile || item.type || "")}</span>
            </span>
          </label>
        `).join("");
        botCharacterList.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
          checkbox.addEventListener("change", () => {
            if (state.targetMode === "single" && checkbox.value === state.targetCharacterId && !checkbox.checked) {
              checkbox.checked = true;
            }
          });
        });
        renderTargetButtons();
        syncBotCheckboxes();
        updateQuestionPlaceholder();
      }

      function getSelectedBotCharacterIds() {
        return Array.from(botCharacterList.querySelectorAll('input[type="checkbox"]:checked'))
          .map((input) => input.value)
          .filter(Boolean);
      }

      function splitCsv(value) {
        return String(value || "")
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
      }

      function normalizeChatResponse(body, response, audience) {
        const isSuccess = response.ok && body && typeof body === "object" && "response" in body;
        return {
          audience,
          isSuccessResponse: isSuccess,
          session_id: body && typeof body === "object" ? body.session_id ?? null : null,
          prompt_watch: body && typeof body === "object" ? body.prompt_watch ?? null : null,
          retrieval_debug: body && typeof body === "object" ? body.retrieval_debug ?? null : null,
          rp_debug: body && typeof body === "object" ? body.rp_debug ?? null : null,
          error_code: body && typeof body === "object" ? body.error_code ?? body.error ?? null : null,
          failure_reason: body && typeof body === "object" ? body.failure_reason ?? body.message ?? null : null,
        };
      }

      async function loadOptions() {
        const response = await fetch("/qa/prompt-watch/options");
        if (!response.ok) {
          throw new Error(`옵션을 불러오지 못했습니다. 상태코드: ${response.status}`);
        }
        const payload = await response.json();
        state.userCharacters = Array.isArray(payload.user_characters) ? payload.user_characters : [];
        fillSelect(
          userCharacterSelect,
          payload.user_characters,
          (item, index) => ({
            value: item.id || "",
            label: item.display_name
              ? `${item.display_name} | ${item.selection_hint || item.persona || item.profile || item.id || ""}`
              : item.name
                ? `${item.name} | ${item.selection_hint || item.persona || item.profile || item.id || ""}`
                : item.id || `user_${index + 1}`,
            selected: index === 0,
          }),
          "선택할 유저 캐릭터가 없습니다."
        );
        userCharacterSelect.addEventListener("change", syncUserCharacterNote);
        syncUserCharacterNote();
        fillSelect(
          sceneSelect,
          payload.scenes,
          (item, index) => ({
            value: item.id || "",
            label: item.id ? `${item.id} / ${item.goal || "장면"}` : `scene_${index + 1}`,
            selected: index === 0,
          }),
          "scene 없음"
        );
        fillSelect(
          worldSelect,
          payload.worlds,
          (item, index) => ({
            value: item.id || "",
            label: item.id ? `${item.id} / ${item.location || "월드"}` : `world_${index + 1}`,
            selected: index === 0,
          }),
          "world 없음"
        );
        renderBotCharacterChoices(payload.bot_characters);
      }

      async function sendChatRequest() {
        const botCharacterIds = getSelectedBotCharacterIds();
        if (!botCharacterIds.length) {
          setStatus("상태", "AI 캐릭터를 하나 이상 선택해야 합니다.");
          return;
        }
        if (!String(questionInput.value || "").trim()) {
          setStatus("상태", "질문을 입력해야 합니다.");
          return;
        }

        const audience = audienceSelect.value || "admin";
        const requestBody = {
          question: String(questionInput.value || "").trim(),
          stream: false,
          audience,
          mode: modeSelect.value || "fast",
          user_profile_id: userCharacterSelect.value || "default",
          character_ids: botCharacterIds,
          character_id: botCharacterIds[0],
          scene_id: sceneSelect.value || "scene_default",
          world_id: worldSelect.value || "default",
          lore_topics: splitCsv(loreTopicInput.value),
        };
        if (state.targetMode === "single" && state.targetCharacterId) {
          requestBody.character_id = state.targetCharacterId;
          requestBody.character_ids = [state.targetCharacterId];
        }
        if (state.currentSessionId) {
          requestBody.session_id = state.currentSessionId;
        }

        setStatus("상태", "질문을 보내는 중입니다.");
        setResponseText("응답을 기다리는 중입니다...");

        const response = await fetch("/chat/ask", {
          method: "POST",
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "x-user": xUserInput.value || "qa_user",
          },
          body: JSON.stringify(requestBody),
        });

        let body = null;
        try {
          body = await response.json();
        } catch (error) {
          body = { error: "invalid_json", message: String(error) };
        }

        if (response.ok && body && typeof body === "object" && body.session_id) {
          state.currentSessionId = body.session_id;
          setSessionNote();
        }

        const normalized = normalizeChatResponse(body, response, audience);
        input.value = JSON.stringify(normalized, null, 2);
        setResponseText(body && typeof body === "object" ? body.response || body.message || "응답 본문이 없습니다." : "응답 본문이 없습니다.");
        renderPromptWatch(normalized);
      }

      function modelLabel(model) {
        if (!model || typeof model !== "object") return "알 수 없는 모델";
        return model.label || [model.provider, model.model].filter(Boolean).join("/") || "알 수 없는 모델";
      }

      function generationStatus(watch) {
        if (!watch || typeof watch !== "object") return { text: "확인 불가", cls: "danger" };
        if (watch.fallback_used) return { text: "대체 응답", cls: "warn" };
        if (watch.repair_used) return { text: "수정된 응답", cls: "warn" };
        return { text: "정상 응답", cls: "ok" };
      }

      function sourceLabel(source) {
        const map = {
          session: "세션 선택",
          catalog: "카탈로그",
          explicit_request: "직접 선택",
          system_default: "기본값",
        };
        return map[source] || source || "알 수 없음";
      }

      function requiredPromptWatchFields(watch) {
        return Boolean(
          watch &&
          typeof watch === "object" &&
          watch.model &&
          watch.active_character_id &&
          watch.scene_id &&
          watch.world_id
        );
      }

      function compactRefs(payload) {
        const watch = payload.prompt_watch || {};
        const applied = watch.applied_context || {};
        const refs = [];

        const lore = Array.isArray(applied.lore) ? applied.lore : [];
        const memories = Array.isArray(applied.memories) ? applied.memories : [];
        const relationships = Array.isArray(applied.relationships) ? applied.relationships : [];

        lore.forEach((item) => refs.push({ title: item.topic || "로어", body: item.summary_text || item.id || "" }));
        memories.forEach((item) => refs.push({ title: item.character_id || "메모리", body: item.summary_text || item.id || "" }));
        relationships.forEach((item) => refs.push({ title: item.target_id ? `관계 ${item.target_id}` : "관계", body: item.summary_text || item.id || "" }));

        if (!refs.length) {
          (Array.isArray(watch.lore_hit_ids) ? watch.lore_hit_ids : []).forEach((id) => refs.push({ title: "로어", body: id }));
          (Array.isArray(watch.memory_hit_ids) ? watch.memory_hit_ids : []).forEach((id) => refs.push({ title: "메모리", body: id }));
          (Array.isArray(watch.relationship_hit_ids) ? watch.relationship_hit_ids : []).forEach((id) => refs.push({ title: "관계", body: id }));
        }

        return refs.slice(0, 3);
      }

      function unavailableView(payload, note) {
        const audience = payload.audience || "user";
        const reason = payload.failure_reason || payload.error_code || "";
        const badge = audience === "admin" && reason
          ? `<div class="badge-row"><span class="badge danger">${escapeHtml(reason)}</span></div>`
          : "";
        return `
          <section class="panel">
            <div class="panel-body empty">
              <h2>Prompt Watch 사용 불가</h2>
              <p>${escapeHtml(note || "렌더링할 수 있는 Prompt Watch 데이터가 없습니다.")}</p>
              ${badge}
            </div>
          </section>
        `;
      }

      function metric(label, value) {
        return `
          <div class="metric">
            <label>${escapeHtml(label)}</label>
            <div class="value">${escapeHtml(value || "-")}</div>
          </div>
        `;
      }

      function optionalMetric(label, value) {
        const text = String(value ?? "").trim();
        if (!text) return "";
        return metric(label, text);
      }

      function summaryItems(items, formatter) {
        if (!Array.isArray(items) || !items.length) {
          return `<div class="metric"><label>항목</label><div class="value">-</div></div>`;
        }
        return `
          <div class="summary-list">
            ${items.map((item) => `
              <div class="summary-item">
                <strong>${escapeHtml(formatter(item).title)}</strong>
                <div>${escapeHtml(truncate(formatter(item).body))}</div>
              </div>
            `).join("")}
          </div>
        `;
      }

      function summarySection(title, items, formatter, emptyLabel = "항목", emptyText = "-") {
        return `
          <div class="section-block">
            <div class="section-title">${escapeHtml(title)}</div>
            ${Array.isArray(items) && items.length
              ? summaryItems(items, formatter)
              : `<div class="metric"><label>${escapeHtml(emptyLabel)}</label><div class="value">${escapeHtml(emptyText)}</div></div>`}
          </div>
        `;
      }

      function chipList(items, formatter, emptyText = "표시할 항목이 없습니다.") {
        const safeItems = Array.isArray(items)
          ? items.map((item, index) => formatter(item, index)).filter((item) => item && item.value)
          : [];
        if (!safeItems.length) {
          return `<div class="metric"><label>상태</label><div class="value">${escapeHtml(emptyText)}</div></div>`;
        }
        return `
          <div class="chip-list">
            ${safeItems.map((item) => `
              <span class="chip">
                ${item.label ? `<strong>${escapeHtml(item.label)}</strong>` : ""}
                <span>${escapeHtml(item.value)}</span>
              </span>
            `).join("")}
          </div>
        `;
      }

      function objectChips(value, emptyText = "표시할 상태가 없습니다.") {
        if (!value || typeof value !== "object" || Array.isArray(value)) {
          return `<div class="metric"><label>상태</label><div class="value">${escapeHtml(emptyText)}</div></div>`;
        }
        const entries = Object.entries(value)
          .filter(([_, item]) => item !== null && item !== undefined && String(item).trim() !== "");
        return chipList(entries, ([key, item]) => ({ label: key, value: String(item) }), emptyText);
      }

      function textStack(title, items, emptyText = "표시할 메모가 없습니다.") {
        const safeItems = Array.isArray(items)
          ? items.map((item) => String(item ?? "").trim()).filter(Boolean)
          : [];
        return `
          <div class="section-block">
            <div class="section-title">${escapeHtml(title)}</div>
            ${safeItems.length ? `
              <div class="stack-list">
                ${safeItems.map((item, index) => `
                  <div class="stack-item">
                    <strong>항목 ${index + 1}</strong>
                    <div>${escapeHtml(item)}</div>
                  </div>
                `).join("")}
              </div>
            ` : `<div class="metric"><label>${escapeHtml(title)}</label><div class="value">${escapeHtml(emptyText)}</div></div>`}
          </div>
        `;
      }

      function noteCard(title, note, emptyText) {
        const payload = note && typeof note === "object" ? note : {};
        const noteText = String(payload.note || "").trim();
        const hardConstraints = Array.isArray(payload.hard_constraints) ? payload.hard_constraints.filter(Boolean) : [];
        const preferredDynamic = Array.isArray(payload.preferred_dynamic) ? payload.preferred_dynamic.filter(Boolean) : [];
        const relationshipExpectation = String(payload.relationship_expectation || "").trim();
        if (!noteText && !hardConstraints.length && !preferredDynamic.length && !relationshipExpectation) {
          return `
            <div class="subcard">
              <h3>${escapeHtml(title)}</h3>
              <p class="subcard-copy">${escapeHtml(emptyText)}</p>
            </div>
          `;
        }
        return `
          <div class="subcard">
            <h3>${escapeHtml(title)}</h3>
            ${noteText ? `<div class="metric"><label>메모</label><div class="value">${escapeHtml(noteText)}</div></div>` : ""}
            ${hardConstraints.length ? `<div><div class="section-title">고정 제약</div>${chipList(hardConstraints, (item) => ({ value: item }), "")}</div>` : ""}
            ${preferredDynamic.length ? `<div><div class="section-title">선호 다이내믹</div>${chipList(preferredDynamic, (item) => ({ value: item }), "")}</div>` : ""}
            ${relationshipExpectation ? `<div class="metric"><label>관계 기대치</label><div class="value">${escapeHtml(relationshipExpectation)}</div></div>` : ""}
          </div>
        `;
      }

      function renderGenerationPath(path, watch) {
        const effective = path && typeof path === "object"
          ? path
          : {
              repair_used: Boolean(watch && watch.repair_used),
              fallback_used: Boolean(watch && watch.fallback_used),
              retry_count: 0,
              final_verdict: watch && watch.fallback_used ? "fallback" : watch && watch.repair_used ? "repaired" : "pass",
            };
        return `
          <div class="section-block">
            <div class="section-title">생성 경로</div>
            <div class="grid two">
              ${metric("최종 판정", effective.final_verdict === "pass" ? "정상 생성" : effective.final_verdict === "repaired" ? "수정된 응답" : effective.final_verdict === "fallback" ? "대체 응답" : effective.final_verdict === "failed" ? "실패" : effective.final_verdict || "-")}
              ${metric("검증기", effective.validator_passed === true ? "통과" : effective.validator_passed === false ? "실패" : "미상")}
              ${metric("수정 재생성 사용", effective.repair_used ? "예" : "아니오")}
              ${metric("대체 응답 사용", effective.fallback_used ? "예" : "아니오")}
              ${metric("재시도 횟수", String(effective.retry_count ?? 0))}
              ${metric("실패 사유", effective.failure_reason || "-")}
            </div>
            <details>
              <summary>생성 경로 Raw</summary>
              <div class="details-body">
                ${renderJsonBlock(effective)}
              </div>
            </details>
          </div>
        `;
      }

      function stringifyActionResult(value) {
        return JSON.stringify(value ?? null, null, 2);
      }

      function adminActionItems(payload, watch) {
        const applied = watch && watch.applied_context && typeof watch.applied_context === "object" ? watch.applied_context : {};
        const dynamicState = applied.dynamic_state && typeof applied.dynamic_state === "object" ? applied.dynamic_state : {};
        const characterState = dynamicState.character && typeof dynamicState.character === "object" ? dynamicState.character : {};
        const sessionState = dynamicState.session && typeof dynamicState.session === "object" ? dynamicState.session : {};
        const branchState = dynamicState.branch && typeof dynamicState.branch === "object" ? dynamicState.branch : {};
        const branchContext = applied.branch_context && typeof applied.branch_context === "object" ? applied.branch_context : {};
        const userNote = applied.user_note && typeof applied.user_note === "object" ? applied.user_note : {};
        const sessionNotePayload = applied.session_note && typeof applied.session_note === "object" ? applied.session_note : {};

        const sessionId = String(payload && payload.session_id ? payload.session_id : "").trim();
        const characterId = String(watch && (watch.selected_speaker_id || watch.active_character_id) || "").trim();
        const branchId = String(branchContext.branch_id || sessionState.branch_id || "").trim();
        const profileId = String(watch && watch.applied_user_profile_id || "").trim();

        return [
          {
            key: "character_state",
            title: "캐릭터 상태",
            description: "현재 선택 화자의 상태를 조회하거나 PUT 템플릿을 만든다.",
            endpoint: characterId ? `/admin/state/characters/${encodeURIComponent(characterId)}` : "",
            putTemplate: characterId ? { data: {
              emotion: characterState.emotion || "neutral",
              location: characterState.location || "",
              outfit: characterState.outfit || "",
              scene_flags: characterState.scene_flags || {},
              relationship_delta: characterState.relationship_delta || {},
              status_notes: characterState.status_notes || [],
            } } : null,
          },
          {
            key: "session_state",
            title: "세션 상태",
            description: "현재 세션의 상태를 조회하거나 PUT 템플릿을 만든다.",
            endpoint: sessionId ? `/admin/state/sessions/${encodeURIComponent(sessionId)}` : "",
            putTemplate: sessionId ? { data: {
              branch_id: sessionState.branch_id || "default",
              active_location: sessionState.active_location || "",
              active_phase: sessionState.active_phase || "",
              scene_flags: sessionState.scene_flags || {},
              status_notes: sessionState.status_notes || [],
            } } : null,
          },
          {
            key: "branch_state",
            title: "브랜치 상태",
            description: "현재 브랜치 상태를 조회하거나 PUT 템플릿을 만든다.",
            endpoint: branchId ? `/admin/state/branches/${encodeURIComponent(branchId)}` : "",
            putTemplate: branchId ? { data: {
              branch_id: branchId,
              route_flags: branchState.route_flags || branchContext.route_flags || {},
              unlock_conditions: branchContext.unlock_conditions || {},
              hidden_facts_revealed: branchState.hidden_facts_revealed || [],
              active_objectives: branchState.active_objectives || branchContext.active_objectives || [],
            } } : null,
          },
          {
            key: "user_note",
            title: "유저 노트",
            description: "현재 적용된 유저 노트를 조회하거나 PUT 템플릿을 만든다.",
            endpoint: profileId ? `/admin/user-notes/${encodeURIComponent(profileId)}` : "",
            putTemplate: profileId ? { data: {
              note: userNote.note || "",
              hard_constraints: userNote.hard_constraints || [],
              preferred_dynamic: userNote.preferred_dynamic || [],
              relationship_expectation: userNote.relationship_expectation || "",
            } } : null,
          },
          {
            key: "session_note",
            title: "세션 노트",
            description: "현재 세션 노트를 조회하거나 PUT 템플릿을 만든다.",
            endpoint: sessionId ? `/admin/session-notes/${encodeURIComponent(sessionId)}` : "",
            putTemplate: sessionId ? { data: {
              note: sessionNotePayload.note || "",
              hard_constraints: sessionNotePayload.hard_constraints || [],
              preferred_dynamic: sessionNotePayload.preferred_dynamic || [],
              relationship_expectation: sessionNotePayload.relationship_expectation || "",
            } } : null,
          },
          {
            key: "session_summary",
            title: "세션 요약",
            description: "현재 세션 요약 레코드를 조회한다. 이 항목은 읽기 전용이다.",
            endpoint: sessionId ? `/admin/session-summaries/${encodeURIComponent(sessionId)}` : "",
            putTemplate: null,
          },
          {
            key: "confirmed_facts",
            title: "확정 사실",
            description: "현재 세션의 확정 사실 목록을 조회한다. 이 항목은 읽기 전용이다.",
            endpoint: sessionId ? `/admin/confirmed-facts/${encodeURIComponent(sessionId)}` : "",
            putTemplate: null,
          },
        ];
      }

      function renderAdminActions(payload, watch) {
        const items = adminActionItems(payload, watch);
        const result = state.lastActionResult;
        return `
          <div class="section-block">
            <div class="section-title">운영 액션</div>
            <p class="section-copy">Prompt Watch는 읽기 전용입니다. 실제 수정은 아래 admin API 경로로 이어서 처리합니다.</p>
            <div class="action-grid">
              ${items.map((item) => `
                <div class="action-card">
                  <h3>${escapeHtml(item.title)}</h3>
                  <div class="action-meta">${escapeHtml(item.description)}</div>
                  <div class="action-meta">${escapeHtml(item.endpoint || "현재 payload만으로 endpoint를 결정할 수 없습니다.")}</div>
                  <div class="action-row">
                    <button
                      class="action-btn"
                      type="button"
                      data-action-kind="fetch"
                      data-action-key="${escapeHtml(item.key)}"
                      data-action-title="${escapeHtml(item.title)}"
                      data-action-endpoint="${escapeHtml(item.endpoint || "")}"
                      ${item.endpoint ? "" : "disabled"}
                    >조회</button>
                    <button
                      class="action-btn secondary"
                      type="button"
                      data-action-kind="template"
                      data-action-key="${escapeHtml(item.key)}"
                      ${item.putTemplate ? `data-action-template="${escapeHtml(stringifyActionResult(item.putTemplate))}"` : ""}
                      ${item.putTemplate ? "" : "disabled"}
                    >PUT 템플릿</button>
                  </div>
                </div>
              `).join("")}
            </div>
            <div id="admin-action-result">
              ${result ? `
                <details open>
                  <summary>${escapeHtml(result.title || "운영 액션 결과")}</summary>
                  <div class="details-body">
                    ${result.endpoint ? `<div class="action-meta">${escapeHtml(result.endpoint)}</div>` : ""}
                    ${renderJsonBlock(result.payload)}
                  </div>
                </details>
              ` : `
                <div class="metric">
                  <label>운영 액션 결과</label>
                  <div class="value">조회 결과나 PUT 템플릿이 여기에 표시됩니다.</div>
                </div>
              `}
            </div>
          </div>
        `;
      }

      function bindAdminActionButtons() {
        renderRoot.querySelectorAll("[data-action-kind]").forEach((button) => {
          button.addEventListener("click", async () => {
            const kind = button.getAttribute("data-action-kind");
            const title = button.getAttribute("data-action-title") || button.textContent || "운영 액션";
            const endpoint = button.getAttribute("data-action-endpoint") || "";
            if (kind === "template") {
              const raw = button.getAttribute("data-action-template") || "null";
              let payload = null;
              try {
                payload = JSON.parse(raw);
              } catch (error) {
                payload = { error: String(error && error.message || error) };
              }
              state.lastActionResult = {
                title: `${button.closest(".action-card")?.querySelector("h3")?.textContent || title} PUT 템플릿`,
                endpoint: endpoint ? `PUT ${endpoint}` : "",
                payload,
              };
              const panel = renderRoot.querySelector("#admin-action-result");
              if (panel) {
                panel.innerHTML = `
                  <details open>
                    <summary>${escapeHtml(state.lastActionResult.title)}</summary>
                    <div class="details-body">
                      ${state.lastActionResult.endpoint ? `<div class="action-meta">${escapeHtml(state.lastActionResult.endpoint)}</div>` : ""}
                      ${renderJsonBlock(state.lastActionResult.payload)}
                    </div>
                  </details>
                `;
              }
              setStatus("상태", "PUT 템플릿을 생성했습니다.");
              return;
            }

            if (!endpoint) {
              setStatus("상태", "이 액션은 현재 payload만으로 endpoint를 결정할 수 없습니다.");
              return;
            }

            setStatus("상태", `${title} 조회 중입니다.`);
            try {
              const response = await fetch(endpoint);
              let payload = null;
              try {
                payload = await response.json();
              } catch (error) {
                payload = { error: "invalid_json", message: String(error && error.message || error) };
              }
              state.lastActionResult = {
                title: `${button.closest(".action-card")?.querySelector("h3")?.textContent || title} 조회 결과`,
                endpoint: `GET ${endpoint}`,
                payload,
              };
              const panel = renderRoot.querySelector("#admin-action-result");
              if (panel) {
                panel.innerHTML = `
                  <details open>
                    <summary>${escapeHtml(state.lastActionResult.title)}</summary>
                    <div class="details-body">
                      <div class="action-meta">${escapeHtml(state.lastActionResult.endpoint)}</div>
                      ${renderJsonBlock(state.lastActionResult.payload)}
                    </div>
                  </details>
                `;
              }
              setStatus("상태", response.ok ? "운영 액션 조회를 완료했습니다." : "운영 액션 조회는 완료했지만 오류 응답이 돌아왔습니다.");
            } catch (error) {
              state.lastActionResult = {
                title: `${button.closest(".action-card")?.querySelector("h3")?.textContent || title} 조회 실패`,
                endpoint: `GET ${endpoint}`,
                payload: { error: String(error && error.message || error) },
              };
              const panel = renderRoot.querySelector("#admin-action-result");
              if (panel) {
                panel.innerHTML = `
                  <details open>
                    <summary>${escapeHtml(state.lastActionResult.title)}</summary>
                    <div class="details-body">
                      <div class="action-meta">${escapeHtml(state.lastActionResult.endpoint)}</div>
                      ${renderJsonBlock(state.lastActionResult.payload)}
                    </div>
                  </details>
                `;
              }
              setStatus("상태", "운영 액션 조회에 실패했습니다.");
            }
          });
        });
      }

      function renderPromptWatch(payload) {
        const watch = payload.prompt_watch;
        if (!payload.isSuccessResponse || !requiredPromptWatchFields(watch)) {
          setStatus("상태", "렌더링할 수 없는 응답입니다.");
          renderRoot.innerHTML = unavailableView(payload, "응답이 실패했거나 Prompt Watch 필수 필드가 빠져 있습니다.");
          return;
        }

        state.lastActionResult = null;
        const status = generationStatus(watch);
        const refs = compactRefs(payload);
        const audience = payload.audience || "user";
        const scene = watch.applied_context && watch.applied_context.scene ? watch.applied_context.scene : {};

        const compactHtml = `
          <section class="panel">
            <div class="panel-body watch-card">
              <div class="card-header">
                <div class="title-wrap">
                  <h2 class="card-title">${escapeHtml(modelLabel(watch.model))}</h2>
                  <p class="card-subtitle">${escapeHtml(watch.active_character_name || watch.active_character_id || "알 수 없는 캐릭터")}</p>
                </div>
                <div class="badge-row">
                  <span class="badge ${status.cls}">${escapeHtml(status.text)}</span>
                  ${audience === "admin" ? `<span class="badge neutral">${escapeHtml(sourceLabel(watch.model && watch.model.source))}</span>` : ""}
                </div>
              </div>

              <div class="grid two">
                ${metric("화자", watch.selected_speaker_id || "-")}
                ${metric("장면", [watch.scene_id, scene.goal || "", scene.mood || ""].filter(Boolean).join(" / "))}
                ${metric("월드", watch.world_id || "-")}
                ${metric("입력 모드", watch.input_mode || "-")}
              </div>

              <div>
                <div class="section-title">참고된 정보</div>
                ${refs.length ? `
                  <div class="summary-list">
                    ${refs.map((item) => `
                      <div class="summary-item">
                        <strong>${escapeHtml(item.title)}</strong>
                        <div>${escapeHtml(truncate(item.body))}</div>
                      </div>
                    `).join("")}
                  </div>
                ` : `<div class="metric"><label>참고 정보</label><div class="value">표시할 참고 항목이 없습니다.</div></div>`}
              </div>
            </div>
          </section>
        `;

        if (audience !== "admin") {
          setStatus("상태", "유저용 간단 화면으로 렌더링했습니다.");
          renderRoot.innerHTML = compactHtml;
          return;
        }

        const applied = watch.applied_context || {};
        const dynamicState = applied.dynamic_state || {};
        const characterState = dynamicState.character || {};
        const sessionState = dynamicState.session || {};
        const branchState = dynamicState.branch || {};
        const sessionSummary = applied.session_summary || {};
        const branchContext = applied.branch_context || {};
        const confirmedFacts = Array.isArray(applied.confirmed_facts) ? applied.confirmed_facts : [];
        const visibleHiddenFacts = Array.isArray(branchContext.visible_hidden_facts) ? branchContext.visible_hidden_facts : [];
        const activeObjectives = Array.isArray(branchContext.active_objectives) ? branchContext.active_objectives : [];
        const userNote = applied.user_note || {};
        const sessionNotePayload = applied.session_note || {};
        const detailHtml = `
          <section class="panel">
            <div class="panel-body watch-card">
              <div class="card-header">
                <div class="title-wrap">
                  <h2 class="card-title">관리자 상세 보기</h2>
                  <p class="card-subtitle">QA 전용 상세 컨텍스트와 진단 정보입니다.</p>
                </div>
                <div class="badge-row">
                  <span class="badge ${status.cls}">${escapeHtml(status.text)}</span>
                  <span class="badge neutral">${escapeHtml(sourceLabel(watch.model && watch.model.source))}</span>
                </div>
              </div>

              <div class="grid two">
                ${metric("활성 캐릭터", watch.active_character_id || "-")}
                ${metric("선택 화자", [watch.selected_speaker_id || "-", watch.selected_speaker_type || ""].filter(Boolean).join(" / "))}
                ${metric("페르소나", watch.applied_persona_id || "-")}
                ${metric("유저 프로필", watch.applied_user_profile_id || "-")}
                ${metric("타깃 힌트", watch.target_character_hint || "-")}
                ${metric("모델 모드", watch.model && watch.model.mode ? watch.model.mode : "-")}
              </div>

              <div class="section-block">
                <div class="section-title">상태</div>
                <p class="section-copy">현재 턴에서 모델이 읽은 캐릭터, 세션, 브랜치 상태를 요약해서 보여줍니다.</p>
                <div class="split-grid">
                  <div class="subcard">
                    <h3>캐릭터 상태</h3>
                    <div class="grid two">
                      ${optionalMetric("감정", characterState.emotion)}
                      ${optionalMetric("위치", characterState.location)}
                      ${optionalMetric("의상", characterState.outfit)}
                    </div>
                    <div>
                      <div class="section-title">장면 플래그</div>
                      ${objectChips(characterState.scene_flags, "캐릭터 플래그가 없습니다.")}
                    </div>
                    <div>
                      <div class="section-title">관계 변화량</div>
                      ${objectChips(characterState.relationship_delta, "변화량이 없습니다.")}
                    </div>
                    ${textStack("상태 메모", characterState.status_notes, "캐릭터 상태 메모가 없습니다.")}
                  </div>
                  <div class="subcard">
                    <h3>세션 상태</h3>
                    <div class="grid two">
                      ${optionalMetric("브랜치", sessionState.branch_id)}
                      ${optionalMetric("활성 위치", sessionState.active_location)}
                      ${optionalMetric("진행 단계", sessionState.active_phase)}
                    </div>
                    <div>
                      <div class="section-title">세션 플래그</div>
                      ${objectChips(sessionState.scene_flags, "세션 플래그가 없습니다.")}
                    </div>
                    ${textStack("세션 메모", sessionState.status_notes, "세션 메모가 없습니다.")}
                  </div>
                  <div class="subcard">
                    <h3>브랜치 상태</h3>
                    <div>
                      <div class="section-title">Route Flags</div>
                      ${objectChips(branchState.route_flags, "브랜치 플래그가 없습니다.")}
                    </div>
                    ${textStack("활성 목표", branchState.active_objectives, "현재 목표가 없습니다.")}
                    ${textStack("공개된 숨김 사실 ID", branchState.hidden_facts_revealed, "공개된 숨김 사실이 없습니다.")}
                  </div>
                </div>
              </div>

              <div class="section-block">
                <div class="section-title">요약과 사실</div>
                <p class="section-copy">긴 history 대신 현재 세션의 요약과 확정된 사실을 먼저 읽을 수 있게 정리합니다.</p>
                <div class="grid two">
                  ${metric("세션 요약", sessionSummary.summary_text || sessionSummary.summary || "-")}
                  ${metric("요약 턴 수", String(sessionSummary.turn_count ?? 0))}
                </div>
                ${Array.isArray(sessionSummary.recent_turn_ids) && sessionSummary.recent_turn_ids.length
                  ? `<div><div class="section-title">최근 요약 턴</div>${chipList(sessionSummary.recent_turn_ids, (item) => ({ value: item }), "")}</div>`
                  : ""}
                ${summarySection("확정 사실", confirmedFacts, (item) => ({ title: item.id || "사실", body: item.summary_text || item.id || "" }), "확정 사실", "확정 사실이 없습니다.")}
              </div>

              <div class="section-block">
                <div class="section-title">관계와 노트</div>
                <p class="section-copy">관계 컨텍스트와 사용자가 고정해둔 세션 전제를 함께 보여줍니다.</p>
                ${summarySection("관계", applied.relationships, (item) => ({ title: item.target_id || item.id || "관계", body: item.summary_text || item.id || "" }), "관계", "적용된 관계 정보가 없습니다.")}
                <div class="grid two">
                  ${noteCard("유저 노트", userNote, "유저 노트가 없습니다.")}
                  ${noteCard("세션 노트", sessionNotePayload, "세션 노트가 없습니다.")}
                </div>
              </div>

              <div class="section-block">
                <div class="section-title">장면과 검색 보조</div>
                <p class="section-copy">장면 정보와 검색으로 들어온 로어, 메모리 보조 정보를 분리해서 보여줍니다.</p>
                <div class="grid two">
                  ${metric("장면 목표", scene.goal || "-")}
                  ${metric("장면 분위기", scene.mood || "-")}
                  ${metric("브랜치 컨텍스트", branchContext.branch_id || "-")}
                  ${metric("해금 조건", Object.keys(branchContext.unlock_conditions || {}).length ? Object.entries(branchContext.unlock_conditions).map(([key, value]) => `${key}:${value ? "on" : "off"}`).join(", ") : "-")}
                </div>
                ${activeObjectives.length ? `<div><div class="section-title">브랜치 목표</div>${chipList(activeObjectives, (item) => ({ value: item }), "")}</div>` : ""}
                ${summarySection("공개된 숨김 사실", visibleHiddenFacts, (item) => ({ title: item.id || "숨김 사실", body: item.fact || "" }), "숨김 사실", "공개된 숨김 사실이 없습니다.")}
                ${summarySection("로어", applied.lore, (item) => ({ title: item.topic || item.id || "로어", body: item.summary_text || item.id || "" }), "로어", "적용된 로어가 없습니다.")}
                ${summarySection("메모리", applied.memories, (item) => ({ title: item.character_id || item.id || "메모리", body: item.summary_text || item.id || "" }), "메모리", "적용된 메모리가 없습니다.")}
              </div>

              ${renderGenerationPath(watch.generation_path, watch)}

              ${renderAdminActions(payload, watch)}

              <div class="section-block">
                <div class="section-title">Debug</div>
                <p class="section-copy">기본 화면에는 숨기고, 진단이 필요할 때만 펼쳐서 보는 영역입니다.</p>
                <details>
                  <summary>검색 디버그</summary>
                  <div class="details-body">
                    ${renderJsonBlock(payload.retrieval_debug || null)}
                  </div>
                </details>
                <details>
                  <summary>RP 디버그</summary>
                  <div class="details-body">
                    ${renderJsonBlock(payload.rp_debug || null)}
                  </div>
                </details>
                <details>
                  <summary>적용 컨텍스트 Raw</summary>
                  <div class="details-body">
                    ${renderJsonBlock(applied)}
                  </div>
                </details>
              </div>
            </div>
          </section>
        `;

        setStatus("상태", "관리자 상세 화면으로 렌더링했습니다.");
        renderRoot.innerHTML = compactHtml + detailHtml;
        bindAdminActionButtons();
      }

      async function loadFixture(name) {
        setStatus("상태", "샘플 데이터를 불러오는 중입니다.");
        const response = await fetch(`/qa/prompt-watch/fixtures/${name}`);
        if (!response.ok) {
          throw new Error(`샘플 데이터를 불러오지 못했습니다. 상태코드: ${response.status}`);
        }
        const payload = await response.json();
        input.value = JSON.stringify(payload, null, 2);
        renderPromptWatch(payload);
      }

      function parsePayload() {
        const raw = input.value.trim();
        if (!raw) {
          setStatus("상태", "입력창이 비어 있습니다.");
          renderRoot.innerHTML = unavailableView({}, "먼저 샘플 버튼을 누르거나 응답 JSON을 붙여넣어 주세요.");
          return null;
        }
        try {
          return JSON.parse(raw);
        } catch (error) {
          setStatus("상태", "JSON 형식이 잘못되었습니다.");
          renderRoot.innerHTML = unavailableView({}, `JSON 형식 오류: ${error.message}`);
          return null;
        }
      }

      document.getElementById("render-btn").addEventListener("click", () => {
        const payload = parsePayload();
        if (payload) renderPromptWatch(payload);
      });

      document.getElementById("format-btn").addEventListener("click", () => {
        const payload = parsePayload();
        if (payload) {
          input.value = JSON.stringify(payload, null, 2);
          renderPromptWatch(payload);
        }
      });

      document.getElementById("clear-btn").addEventListener("click", () => {
        input.value = "";
        setStatus("상태", "초기화했습니다.");
        renderRoot.innerHTML = unavailableView({}, "먼저 샘플 버튼을 누르거나 응답 JSON을 붙여넣어 주세요.");
      });

      sendChatBtn.addEventListener("click", async () => {
        try {
          await sendChatRequest();
        } catch (error) {
          setStatus("상태", "질문 전송에 실패했습니다.");
          setResponseText(String(error.message || error));
          renderRoot.innerHTML = unavailableView({}, String(error.message || error));
        }
      });

      resetSessionBtn.addEventListener("click", () => {
        state.currentSessionId = null;
        setSessionNote();
        setStatus("상태", "세션을 초기화했습니다.");
      });

      document.querySelectorAll("[data-fixture]").forEach((button) => {
        button.addEventListener("click", async () => {
          try {
            await loadFixture(button.dataset.fixture);
          } catch (error) {
            setStatus("상태", "샘플 로드에 실패했습니다.");
            renderRoot.innerHTML = unavailableView({}, error.message);
          }
        });
      });

      setSessionNote();
      loadOptions()
        .then(() => loadFixture("admin_success_detail"))
        .catch((error) => {
          setStatus("상태", "초기 데이터 로드에 실패했습니다.");
          renderRoot.innerHTML = unavailableView({}, error.message);
        });
    </script>
  </body>
</html>
"""
