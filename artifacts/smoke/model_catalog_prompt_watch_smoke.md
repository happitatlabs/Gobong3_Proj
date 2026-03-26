# Model Catalog + Prompt Watch Smoke Report

## 실행 정보

- timestamp: 2026-03-26T12:59:05
- base_url: http://127.0.0.1:8010
- primary session_id: None
- selected_catalog_id: None
- prompt: IPC 규약을 기억하고, 짧게 답하되 상황이나 행동 묘사를 한 줄 포함해줘.

## 최종 요약

- Core checks passed: 0/4
- Content-dependent checks passed: 0/2
- Core failures: 4
- Content failures: 0
- Warnings: 0
- Skipped: 2

## Core Checks

- [FAIL] catalog_list (session_id=None)
- [FAIL] catalog_select (session_id=None)
- [FAIL] explicit_select (session_id=None)
- [FAIL] prompt_watch_admin_detail (session_id=None)

## Content-Dependent Checks

- [SKIP] explicit_user_compact (session_id=None)
- [SKIP] prompt_watch_user_compact (session_id=None)

## Warnings

- 없음

## 시나리오별 결과

### catalog_list
- category: core
- severity: hard
- status: failed
- session_id: None
- note: <urlopen error [WinError 10061] 대상 컴퓨터에서 연결을 거부했으므로 연결하지 못했습니다>

- snapshot: active catalog list and selected model metadata
- active_count: None
- ids: -
- selected_catalog: {}

### catalog_select
- category: core
- severity: hard
- status: failed
- session_id: None
- note: catalog selection skipped because no active catalog item was resolved

- snapshot: session-selected metadata and admin prompt_watch model
- session_selected: {}
- admin_prompt_watch: {}
- forbidden_exposure: {}

### explicit_select
- category: core
- severity: hard
- status: failed
- session_id: None
- note: explicit selection skipped because catalog item is unavailable

- snapshot: session-selected metadata and admin prompt_watch model
- session_selected: {}
- admin_prompt_watch: {}
- forbidden_exposure: {}

### explicit_user_compact
- category: content
- severity: soft
- status: skipped
- session_id: None
- note: explicit user compact check skipped because explicit session is unavailable

- snapshot: prompt_watch and exposure result
- prompt_watch: {}
- prompt_exposure: {}

### prompt_watch_admin_detail
- category: core
- severity: hard
- status: failed
- session_id: None
- note: prompt_watch admin detail skipped because catalog session is unavailable

- snapshot: prompt_watch and exposure result
- prompt_watch: {}
- prompt_exposure: {}

### prompt_watch_user_compact
- category: content
- severity: soft
- status: skipped
- session_id: None
- note: prompt_watch user compact skipped because catalog session is unavailable

- snapshot: prompt_watch and exposure result
- prompt_watch: {}
- prompt_exposure: {}

## User/Admin 응답 비교 요약

- admin source: None
- admin retrieval_debug preserved: None
- admin rp_debug preserved: None
- user status: skipped
- user validation note: prompt_watch user compact skipped because catalog session is unavailable

## Warning 상세

- 없음

## 최종 판정

- Core functionality verification failed.
- Review failed core checks before trusting this environment.
