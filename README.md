# mellow_chat_runtime

텍스트 기반 캐릭터 챗봇 런타임 백엔드입니다.

현재 버전은 단순 프롬프트 주입형 RP 런타임을 넘어, `동적 상태 + 요약 + 사실 누적 + 노트 + 브랜치 맥락`을 포함하는 상태 기반 RP 런타임까지 확장된 상태입니다.

## 현재 범위

- 채팅 세션 기반 `/chat/ask` 런타임
- canonical domain store + vector index 보조 검색층
- multi-character speaker selection
- lore / memory / relationship retrieval
- 장기 기억 승격(memory promotion)
- 동적 상태 주입
  - `character_state`
  - `session_state`
  - `branch_state`
- 턴/세션 요약
  - `turn_summary`
  - `session_summary`
- 확정 사실 누적
  - `confirmed_facts`
- 유저/세션 노트
  - `user_notes`
  - `session_notes`
- branch-aware prompt / hidden fact visibility
- Prompt Watch payload + QA 화면
- 상태/노트/요약/사실 조회용 admin API
- runtime integration tests

## 현재 상태

현재 구현은 아래 3층으로 보는 것이 가장 정확합니다.

1. 기본 런타임 골격
- FastAPI 라우터
- SQLite 세션/메시지 저장
- JSON canonical domain store
- vector retrieval 보조 검색

2. RP 생성 계층
- active speaker 선택
- character / user / world / scene / lore / memory / relationship prompt injection
- validator / repair / fallback 정책

3. 상태 기반 SLM 계층
- 동적 상태 추적
- 턴 종료 후 상태 업데이트
- turn/session summary
- confirmed facts
- branch context / hidden facts
- user/session note
- Prompt Watch 운영 가시화

즉, 구조 골격은 `mellow_chat_runtime`이지만, SLM/RP 품질 계층은 케이브덕식 상태 기반 모델링 방향으로 상당 부분 이동한 상태입니다.

## 프로젝트 구조

- `mellow_chat_runtime/`
  - FastAPI 앱, 라우터, 오케스트레이터, 프롬프트/도메인 로직
- `mellow_chat_runtime_data/`
  - SQLite DB, canonical 도메인 데이터 파일, vector index 파일
- `tests/`
  - 통합 테스트 및 Prompt Watch fixture
- `service_backend_design_for_codex.md`
  - 초기 설계 참고 문서
- `admin_to_user_nn_transition_design.md`
  - `admin -> user_NN` 전환 설계안
- `slm_modeling_status_priorities.md`
  - 현재 SLM 모델링 수준과 남은 갭
- `prompt_watch_ui_spec.md`
  - Prompt Watch 최신 UI/입력 계약 스펙
- `prompt_watch_ui_cleanup_plan.md`
  - Prompt Watch 정리 결과와 남은 후속 과제

## 문서 가이드

- 전체 런타임 구조, 주요 API, 현재 범위를 빠르게 파악하고 싶을 때
  - `README.md`
- 현재 SLM 모델링 수준과 남은 갭을 보고 싶을 때
  - `slm_modeling_status_priorities.md`
- Prompt Watch 입력 계약과 표시 규칙을 보고 싶을 때
  - `prompt_watch_ui_spec.md`
- Prompt Watch 정리 결과와 후속 작업 범위를 보고 싶을 때
  - `prompt_watch_ui_cleanup_plan.md`
- Prompt Watch fixture를 바로 렌더 테스트하고 싶을 때
  - `tests/fixtures/prompt_watch/admin_success_detail.json`
  - `tests/fixtures/prompt_watch/user_success_compact.json`
  - `tests/fixtures/prompt_watch/user_validation_failure_unavailable.json`
- QA 화면에서 질문과 Prompt Watch를 같이 확인하고 싶을 때
  - `GET /qa/prompt-watch`

## 빠른 실행

1. Python 3.10+ 준비
2. 의존성 설치

```bash
pip install fastapi uvicorn sqlalchemy aiohttp pydantic pydantic-settings pytest
```

3. 서버 실행

```bash
python -m mellow_chat_runtime.main
```

기본 주소:

- `http://127.0.0.1:8010`

## 환경 변수

예시:

```env
API_HOST=127.0.0.1
API_PORT=8010
API_DEBUG=false

OLLAMA_HOST=localhost
OLLAMA_PORT=11434
OLLAMA_TIMEOUT=60

FAST_MODEL=qwen3.5:9b
THINKING_MODEL=qwen3.5:9b
RESEARCH_MODEL=qwen3.5:9b

DOMAIN_LOOKUP_BACKEND=json
# VECTORDB_LORE_SEARCH_URL=http://localhost:9000/lore/search
# VECTORDB_TIMEOUT_SEC=2.0
VECTOR_INDEX_FILE=./mellow_chat_runtime_data/vector_index.json

MEMORY_PROMOTION_ENABLED=true
MEMORY_PROMOTION_MAX_ITEMS=20
```

## 핵심 동작

### 1. Chat Runtime

`POST /chat/ask`

지원:

- non-stream JSON 응답
- stream SSE 응답
- `audience=user|admin` 실행 경로 분리
- recent history 반영
- active character 선택 및 prompt injection
- lore / memory / relationship / world / scene 주입
- dynamic state / session summary / confirmed facts / notes / branch context 주입
- request-scoped logging
- structured error response

non-stream 성공 응답 주요 필드:

- `response`
- `session_id`
- `message_id`
- `speaker_id`
- `speaker_type`
- `model_provider`
- `model_name`
- `selected_mode`
- `processing_time_ms`
- `used_context`
- `request_id`
- `prompt_watch`

`audience=admin` 추가 필드:

- `retrieval_debug`
- `rp_debug`
- `state_debug`

### 2. Prompt Priority

현재 프롬프트 우선순위는 대략 아래 구조를 따른다.

1. current scene rules and scene goal
2. dynamic state and continuity
3. confirmed facts and session summary
4. world-state constraints
5. character memories and relationship context
6. lorebook support
7. recent history

### 3. Memory / Summary / Facts

- short-term memory
  - 세션 메시지가 SQLite `chat_messages`에 저장
  - 최근 대화가 prompt에 재주입됨
- long-term memory
  - 캐릭터별 `memories`가 domain data에 저장
  - generation prompt에서 중요한 메모리 상위 항목을 사용
- memory promotion
  - 중요 문장을 감지해 `important_memories`로 승격
- turn summary
  - 각 턴의 핵심과 상태 변화를 저장
- session summary
  - 최근 turn summary를 압축해 세션 맥락으로 저장
- confirmed facts
  - session-local fact ledger로 별도 저장

### 4. Dynamic State / Branch

- `character_state`
  - emotion
  - location
  - outfit
  - scene_flags
  - relationship_delta
- `session_state`
  - branch_id
  - active_location
  - active_phase
  - scene_flags
- `branch_state`
  - route_flags
  - unlock_conditions
  - hidden_facts_revealed
  - hidden_facts
  - active_objectives

브랜치에서는 hidden fact visibility 로직이 적용되어, 공개된 사실만 prompt에 주입됩니다.

### 5. Prompt Watch

Prompt Watch는 `/chat/ask` 응답에 포함되는 설명 인터페이스입니다.

admin detail에서는 아래를 보여줍니다.

- 상태
- 세션 요약
- 확정 사실
- 관계
- 유저/세션 노트
- 로어/메모리 보조 맥락
- 생성 경로
- retrieval/rp debug
- 운영 액션
  - 상태 조회
  - 노트 조회
  - 세션 요약/사실 조회
  - PUT 템플릿 생성

QA 화면:

- `GET /qa/prompt-watch`

### 6. Canonical Store / Vector Index

- canonical store는 source of truth입니다.
  - session / message / participants / model selection / request log는 SQLite에 유지됩니다.
  - user profile / character profile / scene / world / lore / memory / relationship / state / notes canonical payload는 domain JSON에 유지됩니다.
- vector index는 보조 검색층입니다.
  - 검색 가속과 관련 context 후보 추출만 담당합니다.
  - canonical structured field를 덮어쓰지 않습니다.

## 주요 API

### Health / Runtime

- `GET /health`
- `GET /runtime/status`

### Model Selection

- `POST /models/select`
- `GET /models/sessions/{session_id}`

### Session Participants

- `GET /sessions/{session_id}/participants`
- `POST /sessions/{session_id}/participants`

### Chat

- `POST /chat/ask`
- `GET /chat/sessions`
- `GET /chat/sessions/{session_id}/messages`
- `DELETE /chat/sessions/{session_id}`
- `POST /chat/messages/{message_id}/feedback`

### Admin

- Characters
  - `GET /admin/characters`
  - `GET /admin/characters/{user|bot}/{character_id}`
  - `PUT /admin/characters/{user|bot}/{character_id}`
  - `DELETE /admin/characters/{user|bot}/{character_id}`
- Memories / Relationships / Lore
  - `GET /admin/memories/{character_id}`
  - `PUT /admin/memories/{character_id}`
  - `GET /admin/relationships/{source_id}`
  - `PUT /admin/relationships`
  - `GET /admin/lore/{lore_id}`
  - `PUT /admin/lore/{lore_id}`
- Dynamic State
  - `GET /admin/state/characters/{character_id}`
  - `PUT /admin/state/characters/{character_id}`
  - `GET /admin/state/sessions/{session_id}`
  - `PUT /admin/state/sessions/{session_id}`
  - `GET /admin/state/branches/{branch_id}`
  - `PUT /admin/state/branches/{branch_id}`
- Summary / Facts / Notes
  - `GET /admin/turn-summaries/{session_id}`
  - `GET /admin/session-summaries/{session_id}`
  - `GET /admin/confirmed-facts/{session_id}`
  - `GET /admin/user-notes/{profile_id}`
  - `PUT /admin/user-notes/{profile_id}`
  - `DELETE /admin/user-notes/{profile_id}`
  - `GET /admin/session-notes/{session_id}`
  - `PUT /admin/session-notes/{session_id}`
  - `DELETE /admin/session-notes/{session_id}`
- Vector
  - `POST /admin/vector/reindex`

## 데이터 파일

- SQLite DB
  - `mellow_chat_runtime_data/chatbot.db`
- 런타임 도메인 데이터
  - `mellow_chat_runtime_data/domain_data.json`
- vector index
  - `mellow_chat_runtime_data/vector_index.json`
- 시드 예시
  - `mellow_chat_runtime_data/domain_data.seed.json`

## 테스트

실행:

```bash
pytest -q
```

주요 테스트 범위:

- memory promotion
- vector retrieval / reindex smoke
- retrieval scoring QA scenarios
- `/chat/ask` non-stream / stream / failure path
- character prompt enforcement
- multi-character speaker selection
- relationship context prompt injection
- long-term memory prompt usage
- admin API flow
- Prompt Watch contract / fixture

Prompt Watch 관련 테스트:

```bash
pytest -q tests/test_prompt_watch_contract.py
```

retrieval scoring QA 테스트:

```bash
pytest -q test_retrieval_reranker.py
```

QA 스모크:

```bash
python scripts/rp_qa_smoke.py --max-scenarios 1 --audience admin
```

## admin -> user_NN 확장

현재 `admin` API는 운영자 수정용입니다.

이후 일반 사용자용 `user_NN` 구조로 확장하려면:

- `user_NN`은 account id
- `user_char_*`는 character id
- ownership은 DB에서 관리
- 일반 사용자용 `/me/*` 계층 추가

상세 설계:

- `admin_to_user_nn_transition_design.md`

## 현재 범위에서 의도적으로 제외

- auth / permission framework 전면 도입
- media / VTuber pipeline
- scheduler / evolution / guardian
- 대규모 아키텍처 재설계
- 다국어 번역 파이프라인
