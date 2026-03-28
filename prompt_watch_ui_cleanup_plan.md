# Prompt Watch UI 정리 현황

## 목적

이 문서는 현재 버전 기준으로 `Prompt Watch`가 어디까지 정리됐는지와, 남은 후속 과제가 무엇인지 정리한 문서다.

이전 문서가 `계획` 중심이었다면, 이 문서는 `완료 상태 + 남은 후속 작업` 중심으로 다시 정리한다.

## 현재 상태

Prompt Watch UI 정리 라인의 `Batch 1 ~ Batch 4`는 모두 반영된 상태다.

현재 Prompt Watch는 다음 역할을 한다.

- 현재 턴에 어떤 맥락이 모델에 들어갔는지 설명한다
- 상태, 요약, 사실, 노트, 브랜치 정보를 사람이 빠르게 읽게 한다
- retrieval/rp debug를 일반 맥락과 분리해서 보여준다
- 운영자가 바로 admin API 조회와 수정 템플릿으로 이어질 수 있게 한다

즉, 지금 Prompt Watch는 단순한 debug dump가 아니라 `운영용 설명 인터페이스 + QA 허브` 역할을 한다.

## 완료된 항목

### 1. 데이터 계약 정리

완료:

- `runtime/schemas.py`가 실제 `prompt_watch` payload와 맞춰졌다
- `dynamic_state`
- `session_summary`
- `confirmed_facts`
- `branch_context`
- `user_note`
- `session_note`
- fixture가 최신 payload 기준으로 갱신됐다

관련 파일:

- [schemas.py](/D:/Gobong3_Proj/mellow_chat_runtime/runtime/schemas.py)
- [admin_success_detail.json](/D:/Gobong3_Proj/tests/fixtures/prompt_watch/admin_success_detail.json)
- [user_success_compact.json](/D:/Gobong3_Proj/tests/fixtures/prompt_watch/user_success_compact.json)

### 2. 정보 구조 재정렬

완료:

- admin detail 섹션 순서 고정
  1. Header
  2. 상태
  3. 요약과 사실
  4. 관계와 노트
  5. 장면과 검색 보조
  6. 생성 경로
  7. Debug
- 기본 화면은 요약형 카드 중심
- raw JSON은 접힌 영역으로 이동

관련 파일:

- [prompt_watch_ui.py](/D:/Gobong3_Proj/mellow_chat_runtime/routers/prompt_watch_ui.py)
- [prompt_watch_ui_spec.md](/D:/Gobong3_Proj/prompt_watch_ui_spec.md)

### 3. 한국어 일관성 정리

완료:

- Prompt Watch 주요 UI 라벨 한국어화
- 관계/로어/월드/장면 샘플 데이터 한국어화
- 모델 라벨과 설명의 기본 샘플 한국어화

관련 파일:

- [prompt_watch_ui.py](/D:/Gobong3_Proj/mellow_chat_runtime/routers/prompt_watch_ui.py)
- [domain_lookup_store.py](/D:/Gobong3_Proj/mellow_chat_runtime/core/domain_lookup_store.py)
- [domain_data.json](/D:/Gobong3_Proj/mellow_chat_runtime_data/domain_data.json)
- [domain_data.seed.json](/D:/Gobong3_Proj/mellow_chat_runtime_data/domain_data.seed.json)

### 4. 운영 액션 연결

완료:

- Prompt Watch 안에서 아래 admin API 흐름으로 바로 이어질 수 있다
  - 캐릭터 상태 조회
  - 세션 상태 조회
  - 브랜치 상태 조회
  - 유저 노트 조회
  - 세션 노트 조회
  - 세션 요약 조회
  - 확정 사실 조회
- PUT 템플릿을 즉시 생성할 수 있다
- 새 payload가 들어오면 이전 액션 결과는 재사용하지 않는다

관련 파일:

- [prompt_watch_ui.py](/D:/Gobong3_Proj/mellow_chat_runtime/routers/prompt_watch_ui.py)
- [admin.py](/D:/Gobong3_Proj/mellow_chat_runtime/routers/admin.py)

### 5. QA와 회귀 테스트

완료:

- Prompt Watch 계약 테스트가 있다
- fixture shape 테스트가 있다
- unavailable 처리 테스트가 있다
- QA 화면에 운영 액션 패널이 포함되는지 테스트한다

관련 파일:

- [test_prompt_watch_contract.py](/D:/Gobong3_Proj/tests/test_prompt_watch_contract.py)

## 현재 Prompt Watch가 보여주는 것

admin detail 기준:

- 모델 / 캐릭터 / 화자 / 생성 상태
- 동적 상태
  - character
  - session
  - branch
- 세션 요약
- 확정 사실
- 관계
- 유저 노트
- 세션 노트
- 브랜치 컨텍스트 / 공개된 hidden facts
- 장면 / 로어 / 메모리
- 생성 경로
- retrieval debug
- rp debug
- 운영 액션

user compact 기준:

- 모델
- 활성 캐릭터
- 장면 요약
- 핵심 참고 정보 2~3개
- 생성 상태

## 남은 후속 과제

현재 남은 건 코어 정리라기보다 제품화/운영 편의 쪽이다.

### 1. 실제 프론트엔드 이관

현재 QA 화면은 `prompt_watch_ui.py`에 들어간 내장 HTML이다.

후속 후보:

- 별도 프론트 프로젝트로 컴포넌트 이관
- 디자인 시스템 적용
- 운영자용 레이아웃 정교화

### 2. inline edit 여부 결정

현재 Prompt Watch는 읽기 전용이며, admin API 조회와 PUT 템플릿까지만 제공한다.

후속 후보:

- Prompt Watch에서 직접 편집
- 혹은 지금처럼 admin API 템플릿만 제공

현재 기준에서는 후자가 더 안전하다.

### 3. action result UX 보강

현재는 조회 결과와 PUT 템플릿을 JSON으로 보여준다.

후속 후보:

- 복사 버튼
- PUT/GET 명령 예시
- 실패 응답 시 더 친절한 안내

### 4. Prompt Watch 전용 시각 회귀

현재는 계약 테스트와 QA 페이지 문자열 검증 위주다.

후속 후보:

- 스냅샷 테스트
- 섹션별 렌더 회귀 테스트
- fixture 확장

## 현재 기준 결론

Prompt Watch 정리 작업은 현재 버전 기준으로 1차 완료 상태다.

가장 중요한 변화는 이것이다.

- 예전:
  - lore/memory/relationship 중심의 초기 debug 뷰
- 현재:
  - 상태/요약/사실/노트/브랜치 중심의 운영용 설명 인터페이스

즉, 다음 단계는 `더 만들기`보다 `어디까지 제품화할지 결정하기`에 가깝다.
