# Prompt Watch UI 1차 스펙 및 전달 계획

## 요약

- 본 문서는 Prompt Watch UI의 프론트엔드 구현을 위한 전달 스펙이다.
- 실제 UI 구현은 이 저장소에서 수행하지 않으며, 별도 프론트엔드에서 본 스펙을 기준으로 개발한다.
- Prompt Watch는 `/chat/ask` 응답의 `prompt_watch`를 기반으로 구성되며, UI는 해당 데이터를 설명 가능한 형태로 렌더링하는 것을 목표로 한다.
- `prompt_watch`는 설명 계층, `retrieval_debug`/`rp_debug`는 admin 전용 진단 계층으로 분리한다.
- 실패 응답, `prompt_watch` 누락, partial payload는 모두 `Prompt Watch unavailable` 상태로 처리한다.

---

## 1. 데이터 계약 (Frontend Input Contract)

### 1.1 Source of Truth

- UI의 기본 source of truth는 `/chat/ask` 응답의 `prompt_watch`이다.
- admin 상세 뷰에서는 보조 데이터로 `retrieval_debug`, `rp_debug`를 추가 사용한다.
- 프론트는 backend 응답 shape를 그대로 읽으며, 별도 view model로 reshape하지 않는다.

### 1.2 입력 데이터 구조

`PromptWatchPanel`은 아래 데이터를 상위 메시지 렌더 계층으로부터 전달받는다.

- `audience: "user" | "admin"`
- `isSuccessResponse: boolean`
- `prompt_watch`
- `retrieval_debug`
- `rp_debug`
- `error_code`
- `failure_reason`

### 1.3 컴포넌트 성격

- `PromptWatchPanel`은 API 호출을 하지 않는 순수 렌더링 컴포넌트다.
- 네트워크 요청, refetch, 내부 캐시를 갖지 않는다.
- 새로운 assistant 응답이 들어올 때만 갱신된다.
- 이전 turn의 `prompt_watch`는 재사용하지 않는다.

---

## 2. Unavailable 상태 정의

다음 조건 중 하나라도 만족하면 Prompt Watch를 렌더링하지 않는다.

- `isSuccessResponse === false`
- `prompt_watch` 없음
- 필수 필드 누락
- partial payload

### 표시 방식

- user:
  - `"Prompt Watch unavailable"` 고정 문구만 표시
- admin:
  - `"Prompt Watch unavailable"` + 짧은 상태 badge 허용
  - 예: `validation failure`, `narration rule failed`

### 금지

- 전체 error payload 표시
- 내부 debug dump 노출
- 이전 응답 데이터 fallback 사용

---

## 3. UI View 구조

### 3.1 User View (Compact)

- 항상 compact view만 렌더
- 표시 항목:
  - 모델명
  - 캐릭터
  - 참고 정보 (2~3개)
  - 상태
  - scene 요약

---

### 3.2 Admin View (Detail)

- 기본: compact
- “상세 보기” 토글 시 detail 확장

#### Detail 구성

- Model
- Speaker
- Context
- Scene
- Generation
- Debug (accordion)

---

### 3.3 Debug 영역

- `Retrieval Debug`
- `RP Debug`

규칙:

- 서로 독립된 accordion
- 기본 collapsed
- 자동 expand 금지

---

## 4. 표시 규칙

### 4.1 모델명

- `prompt_watch.model.label` 우선
- 없으면 `${provider}/${model}`

---

### 4.2 상태 문구

- 정상 생성
- 수정된 응답
- 대체 응답

---

### 4.3 Source Badge (Admin Only)

허용값:

- `session`
- `catalog`
- `explicit_request`
- `system_default`

표시:

- `session` → 세션 선택
- `catalog` → 카탈로그
- `explicit_request` → 직접 선택
- `system_default` → 기본값

---

### 4.4 Compact 참고 정보 우선순위

1. lore
2. memories
3. relationships

규칙:

- 최대 2~3개
- scene 제외
- backend 순서 유지

---

### 4.5 Context 표시 규칙

- lore:
  - topic 우선
  - 없으면 summary_text
- memories:
  - summary_text
- relationships:
  - target_id + summary_text
- scene:
  - goal, mood

---

### 4.6 summary_text 처리

- backend 기준 200자
- frontend에서 220자 초과 시 추가 truncate

---

## 5. 금지 항목

다음은 어떤 경우에도 UI에 노출하지 않는다.

- raw system prompt
- raw user prompt
- full history
- 내부 LLM payload
- token-level data

---

## 6. 테스트/검증 기준

### 컴포넌트 테스트

- API 호출 없음
- compact/detail 분리
- source badge 정확성
- truncate 동작
- debug accordion 분리

### 상태 테스트

- 422 validation failure → unavailable 처리
- 이전 turn 데이터 유지 금지

### 통합 테스트

- admin detail 정상 렌더
- user compact 정상 렌더
- source별 badge 확인

### 테스트용 fixture JSON

이 저장소에는 프론트 전달/테스트용 fixture JSON 3개가 포함되어 있다.

- [`tests/fixtures/prompt_watch/admin_success_detail.json`](D:/Gobong3_Proj/tests/fixtures/prompt_watch/admin_success_detail.json)
  - admin 성공 응답
  - detail `prompt_watch`
  - `retrieval_debug`, `rp_debug` 포함
- [`tests/fixtures/prompt_watch/user_success_compact.json`](D:/Gobong3_Proj/tests/fixtures/prompt_watch/user_success_compact.json)
  - user 성공 응답
  - compact `prompt_watch`
- [`tests/fixtures/prompt_watch/user_validation_failure_unavailable.json`](D:/Gobong3_Proj/tests/fixtures/prompt_watch/user_validation_failure_unavailable.json)
  - user 실패 응답
  - `error_code=NARRATION_RULE_FAILED`
  - `failure_reason=missing_narration`
  - unavailable 상태 검증용

이 fixture들은 `PromptWatchPanel` 입력 계약 형태로 정리되어 있으며, 별도 프론트 프로젝트에서 그대로 import해 한 번에 렌더 테스트할 수 있다.

---

## 7. 가정 및 범위

- 본 문서는 UI 구현 스펙이며, 이 저장소에서 UI를 직접 구현하지 않는다.
- 프론트는 별도 프로젝트에서 본 스펙을 기반으로 개발한다.
- backend 스키마는 변경하지 않는다.
- partial payload는 지원하지 않는다.

---

## 최종 원칙

- Prompt Watch는 “로그 출력”이 아니라 “설명 인터페이스”다.
- 동일 payload를 기반으로 user/admin view만 다르게 렌더링한다.
- 설명 계층과 진단 계층을 분리한다.
- 데이터는 있는 그대로 읽고, 의미만 번역한다.
