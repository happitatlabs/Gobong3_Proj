# Prompt Watch UI 스펙

## 목적

- 본 문서는 `Prompt Watch` UI의 최신 입력 계약과 표시 규칙을 정의한다.
- 기준 데이터는 `/chat/ask` 응답의 `prompt_watch`이며, admin 상세 뷰에서는 `retrieval_debug`, `rp_debug`를 보조 진단 데이터로 함께 사용한다.
- Prompt Watch는 로그 덤프가 아니라, 현재 턴에 모델이 어떤 맥락을 읽고 답했는지 설명하는 운영 인터페이스다.

## Source Of Truth

- 기본 source of truth:
  - `/chat/ask` 응답의 `prompt_watch`
- admin 보조 source:
  - `retrieval_debug`
  - `rp_debug`

규칙:

- 프론트는 별도 재계산 없이 backend payload를 읽는다
- 새 assistant 응답이 들어올 때만 갱신한다
- 이전 turn의 `prompt_watch`를 재사용하지 않는다

## 입력 계약

`PromptWatchPanel` 입력은 아래 shape를 따른다.

- `audience: "user" | "admin"`
- `isSuccessResponse: boolean`
- `session_id`
- `prompt_watch`
- `retrieval_debug`
- `rp_debug`
- `error_code`
- `failure_reason`

## Unavailable 규칙

아래 중 하나라도 만족하면 Prompt Watch는 unavailable 처리한다.

- `isSuccessResponse === false`
- `prompt_watch` 없음
- `prompt_watch`가 객체가 아님
- compact 필수 필드 누락

user 표시:

- `Prompt Watch 사용 불가`

admin 표시:

- `Prompt Watch 사용 불가`
- 필요 시 짧은 상태 badge 허용
  - 예: `validation failure`
  - 예: `missing narration`

금지:

- 전체 error payload dump
- 내부 debug raw dump 기본 노출
- 이전 성공 응답 fallback 사용

## View 구조

### User View

항상 compact만 렌더한다.

표시 항목:

- 모델
- 활성 캐릭터
- 장면 요약 1줄
- 핵심 참고 정보 2~3개
- 생성 상태 1줄

### Admin View

- 기본은 compact
- `상세 보기`에서 detail 확장

detail 섹션 순서:

1. Header
2. 상태
3. 요약과 사실
4. 관계와 노트
5. 장면과 검색 보조
6. 생성 경로
7. 운영 액션
8. Debug

## 데이터 구조

### Compact 공통 필드

- `active_character_id`
- `active_character_name`
- `selected_speaker_id`
- `selected_speaker_type`
- `scene_id`
- `world_id`
- `input_mode`
- `target_character_hint`
- `lore_hit_ids`
- `memory_hit_ids`
- `relationship_hit_ids`
- `model`
- `repair_used`
- `fallback_used`

### Admin Detail 추가 필드

- `session_id`
- `applied_persona_id`
- `applied_user_profile_id`
- `generation_path`
- `applied_context`

### applied_context 구성

`applied_context`는 아래 필드를 가진다.

- `scene`
- `dynamic_state`
- `session_summary`
- `confirmed_facts`
- `branch_context`
- `user_note`
- `session_note`
- `relationships`
- `lore`
- `memories`

## 섹션별 표시 규칙

### 1. Header

표시:

- 활성 캐릭터 이름
- 선택 화자 id/type
- 모델 라벨
- 생성 상태

모델명 규칙:

- `prompt_watch.model.label` 우선
- 없으면 `${provider}/${model}`

생성 상태 문구:

- `fallback_used === true` -> `대체 응답`
- `repair_used === true` -> `수정된 응답`
- 그 외 -> `정상 생성`

source badge:

- `session` -> `세션 선택`
- `catalog` -> `카탈로그`
- `explicit_request` -> `직접 선택`
- `system_default` -> `기본값`

### 2. 상태

표시 대상:

- `dynamic_state.character`
- `dynamic_state.session`
- `dynamic_state.branch`
- `branch_context`

표시 규칙:

- `character`, `session`, `branch` 3카드로 분리
- `emotion`, `location`, `outfit`, `active_phase`는 라벨형 텍스트로 표시
- `scene_flags`, `route_flags`, `relationship_delta`는 key-value chip 또는 목록으로 표시
- 빈 값, 빈 dict, 빈 list는 숨긴다
- `visible_hidden_facts`만 표시한다
- `hidden_fact_ids`는 admin raw view에서만 보조 노출 가능

### 3. 요약과 사실

표시 대상:

- `session_summary`
- `confirmed_facts`

표시 규칙:

- `session_summary.summary_text` 우선
- 없으면 `summary`
- 확정 사실은 최대 5개 기본 노출
- 각 fact는 `summary_text` 우선, 없으면 `fact` 계열 텍스트 표시
- confidence, source turn 같은 메타는 기본 숨김, admin raw에서만 허용

### 4. 관계와 노트

표시 대상:

- `relationships`
- `user_note`
- `session_note`

표시 규칙:

- 관계는 `target_id + summary_text` 우선
- 노트는 `note`, `hard_constraints`, `preferred_dynamic`, `relationship_expectation`로 분리
- null, empty string, empty list는 숨김

### 5. 장면과 검색 보조

표시 대상:

- `scene`
- `lore`
- `memories`

표시 규칙:

- compact 참고 정보 우선순위:
  - `lore`
  - `memories`
  - `relationships`
- compact에서는 최대 2~3개만 노출
- detail에서는 section별 리스트로 분리

context item 표시:

- lore:
  - `topic` 우선
  - 없으면 `summary_text`
- memories:
  - `summary_text`
- relationships:
  - `target_id + summary_text`

### 6. 생성 경로

표시 대상:

- `generation_path`

표시 규칙:

- `validator_passed`
- `repair_used`
- `fallback_used`
- `retry_count`
- `final_verdict`
- `failure_reason`

이 섹션은 debug가 아니라 상단 운영 정보에 가깝다. 별도 카드로 분리한다.

### 7. Debug

표시 대상:

- `retrieval_debug`
- `rp_debug`

규칙:

- 서로 독립된 accordion
- 기본 collapsed
- 자동 expand 금지
- score map, errors는 기본 숨김 가능

### 8. 운영 액션

표시 대상:

- 상태 조회 경로
- 노트 조회 경로
- 세션 요약/확정 사실 조회 경로
- PUT 템플릿

규칙:

- Prompt Watch 자체는 읽기 전용이다
- 실제 수정은 admin API에서 수행한다
- QA 화면에서는 아래 액션을 제공할 수 있다
  - GET 조회
  - PUT 템플릿 생성
- 새 payload가 들어오면 이전 액션 결과를 재사용하지 않는다

## 요약형과 Raw View 규칙

- 기본 화면은 사람이 읽는 요약형 텍스트를 우선한다
- raw JSON은 별도 펼침 영역으로 이동한다
- 같은 정보가 요약형과 raw에 중복 노출되어도, 기본 화면에서는 raw를 직접 보여주지 않는다

## Truncate 규칙

- backend `summary_text` 기본 기준은 200자
- frontend에서 220자 초과 시 추가 truncate 가능
- truncate 시 말줄임표 처리

## 금지 항목

다음은 어떤 경우에도 기본 UI에 노출하지 않는다.

- raw system prompt
- raw user prompt
- full history
- 내부 LLM payload
- token-level dump

## 테스트 기준

### 컴포넌트/렌더

- user compact 정상 렌더
- admin detail 정상 렌더
- unavailable 처리
- compact/detail 분리
- source badge 정확성
- 운영 액션 패널 노출

### 계약/shape

- admin fixture가 최신 `applied_context` 필드를 모두 포함하는지
- runtime schema와 fixture shape가 일치하는지
- partial payload를 정상 payload로 취급하지 않는지

### 상태 검증

- `422 validation failure` -> unavailable
- 이전 turn 데이터 유지 금지
- debug accordion 기본 collapsed
- 새 payload 렌더 시 이전 액션 결과 유지 금지

## Fixture

테스트용 fixture는 아래를 사용한다.

- [admin_success_detail.json](/D:/Gobong3_Proj/tests/fixtures/prompt_watch/admin_success_detail.json)
- [user_success_compact.json](/D:/Gobong3_Proj/tests/fixtures/prompt_watch/user_success_compact.json)
- [user_validation_failure_unavailable.json](/D:/Gobong3_Proj/tests/fixtures/prompt_watch/user_validation_failure_unavailable.json)

admin fixture는 아래를 포함해야 한다.

- `session_id`
- `dynamic_state`
- `session_summary`
- `confirmed_facts`
- `branch_context`
- `user_note`
- `session_note`

## 최종 원칙

- Prompt Watch는 설명 인터페이스다
- 상태와 서사 연속성을 먼저 보여준다
- 진단 정보는 별도 계층으로 분리한다
- user view는 짧고, admin view는 운영 가능해야 한다
