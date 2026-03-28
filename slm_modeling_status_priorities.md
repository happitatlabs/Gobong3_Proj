# SLM 모델링 현황

## 목적

이 문서는 `케이브덕 기능 구조도`를 참고해, 현재 `mellow_chat_runtime`이 SLM 기반 롤플레잉/캐릭터 챗 모델링 관점에서 어디까지 와 있는지 정리한 문서다.

평가 기준은 제품 기능 전체가 아니라 아래 축에 한정한다.

1. 캐릭터 코어 프로필
2. 세계관/로어북
3. 유저 프로필
4. 대화 상태(state) 추적
5. 메모리 계층
6. 시작 조건/시나리오
7. 문체 제어
8. 분기/비밀/루트 상태

## 한줄 평가

현재 상태는 대략 `82~88%` 수준이다.

- 강한 부분:
  - 캐릭터/유저/세계관/관계 구조화
  - 동적 상태
  - turn/session summary
  - confirmed facts
  - user/session note
  - branch context / hidden facts
- 상대적으로 약한 부분:
  - 시작 조건/시나리오 프리셋 체계
  - 번역/다국어 운영 레이어
  - 예시 대화, 템플릿 치환, 회차 carry-over 같은 제품화 레이어

즉, 지금은 `프롬프트 주입형 RP 런타임`을 넘어서 `상태 기반 SLM 롤플레잉 엔진의 1차 코어`까지는 닫힌 상태다.

## 축별 평가

| 축 | 현재 수준 | 평가 |
|---|---:|---|
| 캐릭터 코어 프로필 | 85~90% | 이름, 프로필, 말투, forbidden, alias, style/franchise anchor가 구조적으로 들어감 |
| 세계관/로어북 | 80~85% | lorebook, alias, retrieval, priority, searchable payload가 있음 |
| 유저 프로필 | 78~82% | user profile, interpretation style, response tuning, user note까지 들어감 |
| 대화 상태(state) 추적 | 75~82% | `character/session/branch state`와 턴 후 상태 갱신이 있음 |
| 메모리 계층 | 80~85% | recent history, important memories, memory promotion, turn/session summary, confirmed facts가 있음 |
| 시작 조건/시나리오 | 55~65% | scene goal/rules는 있으나 scenario preset 체계는 아직 약함 |
| 문체 제어 | 82~88% | tone, interpretation style, response tuning, language drift 방지가 있음 |
| 분기/비밀/루트 상태 | 70~78% | branch schema, unlock conditions, hidden fact visibility, branch-aware prompt가 있음 |

## 현재 들어가 있는 것

### 1. 캐릭터 코어 프로필

현재는 캐릭터에 대해 아래 정보가 system prompt에 직접 들어간다.

- `name`
- `profile`
- `speech_style.tone`
- `speech_style.forbidden`
- `aliases`
- `style_anchor`
- `franchise_anchor`
- `relationship_keys`

근거:

- [prompt_builder.py](/D:/Gobong3_Proj/mellow_chat_runtime/core/prompt_builder.py)
- [domain_lookup_store.py](/D:/Gobong3_Proj/mellow_chat_runtime/core/domain_lookup_store.py)

### 2. 세계관/로어북

현재는 lorebook entry, aliases, content, priority가 있으며 retrieval에도 연결되어 있다.

또한 searchable payload와 vector reindex 흐름도 있다.

근거:

- [schemas.py](/D:/Gobong3_Proj/mellow_chat_runtime/domain/schemas.py)
- [vector_retrieval_service.py](/D:/Gobong3_Proj/mellow_chat_runtime/services/vector_retrieval_service.py)
- [summary_formatter.py](/D:/Gobong3_Proj/mellow_chat_runtime/services/summary_formatter.py)

### 3. 유저 프로필

현재는 단순 유저 이름이 아니라, 상대 해석 프레임까지 구조화되어 있다.

- `persona`
- `role`
- `core_context`
- `interpretation_style`
- `response_style`
- `user_note`
- `session_note`

즉 SLM 입장에서 유저를 "상대역"으로 안정적으로 읽게 하는 층이 이미 있다.

근거:

- [domain_lookup_store.py](/D:/Gobong3_Proj/mellow_chat_runtime/core/domain_lookup_store.py)
- [prompt_builder.py](/D:/Gobong3_Proj/mellow_chat_runtime/core/prompt_builder.py)
- [admin.py](/D:/Gobong3_Proj/mellow_chat_runtime/routers/admin.py)

### 4. 메모리 계층

현재 메모리 관련으로 이미 있는 것:

- recent history 재주입
- `important_memories`
- long-term memory retrieval
- memory promotion
- `turn_summary`
- `session_summary`
- `confirmed_facts`
- contradiction check

즉 긴 대화 품질을 위한 압축 계층이 1차 수준으로 들어와 있다.

근거:

- [memory_promotion_service.py](/D:/Gobong3_Proj/mellow_chat_runtime/services/memory_promotion_service.py)
- [turn_summary_service.py](/D:/Gobong3_Proj/mellow_chat_runtime/services/turn_summary_service.py)
- [session_summary_service.py](/D:/Gobong3_Proj/mellow_chat_runtime/services/session_summary_service.py)
- [confirmed_facts_service.py](/D:/Gobong3_Proj/mellow_chat_runtime/services/confirmed_facts_service.py)
- [contradiction_check_service.py](/D:/Gobong3_Proj/mellow_chat_runtime/services/contradiction_check_service.py)

### 5. 동적 상태

현재는 scene/world 외에 아래 상태 계층이 있다.

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

또한 턴 종료 후 `state_update_service`가 최소 규칙 기반으로 상태를 갱신한다.

근거:

- [schemas.py](/D:/Gobong3_Proj/mellow_chat_runtime/domain/schemas.py)
- [state_update_service.py](/D:/Gobong3_Proj/mellow_chat_runtime/services/state_update_service.py)
- [chat.py](/D:/Gobong3_Proj/mellow_chat_runtime/routers/chat.py)

### 6. 분기/비밀/루트 상태

현재는 branch schema와 hidden fact visibility가 있다.

- `branch_id`
- `route_flags`
- `unlock_conditions`
- `hidden_facts`
- `hidden_facts_revealed`
- branch-aware prompt

즉 단순 scene rule 수준은 이미 넘었고, route-specific context를 제한적으로 운영할 수 있다.

근거:

- [schemas.py](/D:/Gobong3_Proj/mellow_chat_runtime/domain/schemas.py)
- [branch_visibility_service.py](/D:/Gobong3_Proj/mellow_chat_runtime/services/branch_visibility_service.py)
- [prompt_builder.py](/D:/Gobong3_Proj/mellow_chat_runtime/core/prompt_builder.py)

## 아직 약한 부분

### 1. 시작 조건 / 시나리오 프리셋

scene goal, participants, rules는 있지만, 케이브덕식 방 생성 프리셋이나 진입 시나리오 UX는 아직 약하다.

부족한 항목 예시:

- 상황별 시작 프리셋
- 관계 초기값 preset
- branch별 시작점 preset
- replay carry-over preset

### 2. 번역 / 다국어 레이어

현재는 언어 감지와 한국어 유지 규칙은 있으나, 운영용 번역 파이프라인은 없다.

부족한 항목 예시:

- source/target language 정책
- 입력/출력 번역 파이프라인
- lore/localization 계층

### 3. 예시 대화 / 템플릿 치환

현재는 structured profile 중심이라, 예시 대화 few-shot과 `{{user}}`, `{{char}}` 치환 계층은 약하다.

### 4. 고급 상태 추론

현재 상태 갱신은 규칙 기반 중심이다.

추후 보강 가능 항목:

- affection / trust / tension 수치화
- contradiction repair 연동
- 회차 carry-over
- scene object / outfit inventory 상태

## 우선순위

지금 시점의 우선순위는 아래처럼 보는 게 맞다.

### P0. 시작 조건 / 시나리오 프리셋 강화

이유:

- 코어 상태 시스템은 이미 들어갔다
- 다음 품질 병목은 "어떻게 시작하느냐" 쪽이다

### P1. 번역 / 다국어 레이어

이유:

- 현재 코어는 한국어 기준으로는 많이 닫혔지만, 다국어 운영 구조는 아직 비어 있다

### P2. 고급 상태 변수 / 회차 carry-over

이유:

- 현재도 충분히 동작하지만, 장기 RP/회차형 운영으로 가려면 세밀한 상태 추론이 추가로 필요하다

### P3. 예시 대화 / 템플릿 치환

이유:

- few-shot과 템플릿은 품질 보강에는 좋지만, 지금 병목은 코어 일관성보다 낮다

## 결론

현재 `mellow_chat_runtime`은 이미 다음 단계를 넘어섰다.

- 캐릭터와 맥락을 프롬프트에 넣는 구조
- 상태를 세션 단위로 유지하는 구조
- 요약과 사실을 누적하는 구조
- 브랜치와 비밀 정보를 제한적으로 관리하는 구조

즉, 지금 문맥에서 가장 정확한 표현은 이것이다.

`기본 프로젝트 골격 위에, 케이브덕식 SLM 모델링 코어는 1차 구현이 완료된 상태`
