from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_QUESTION = 'IPC 규약을 기억하고, 짧게 답하되 상황이나 행동 묘사를 한 줄 포함해줘.'
FORBIDDEN_PROMPT_KEYS = {'system_prompt', 'user_prompt', 'history', 'full_history', 'raw_prompt'}
SUMMARY_TEXT_LIMIT = 220
NARRATION_ERROR_CODES = {'NARRATION_RULE_FAILED'}
NARRATION_FAILURE_REASONS = {'missing_narration'}


@dataclass
class CheckResult:
    name: str
    category: str
    severity: str
    status: str
    details: Dict[str, Any]


class SmokeClient:
    def __init__(self, base_url: str, timeout: float, x_user: str) -> None:
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.x_user = x_user

    def request_json(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[int], Any, Optional[str]]:
        url = self.base_url + path
        if query:
            cleaned_query = {key: value for key, value in query.items() if value is not None and value != ''}
            if cleaned_query:
                url += '?' + urllib.parse.urlencode(cleaned_query)
        headers = {
            'Accept': 'application/json',
            'x-user': self.x_user,
        }
        data = None
        if payload is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        request = urllib.request.Request(url=url, data=data, method=method.upper(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode('utf-8')
                body = json.loads(raw) if raw else None
                return response.status, body, None
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode('utf-8', errors='replace')
            try:
                body = json.loads(raw) if raw else None
            except Exception:
                body = raw
            return exc.code, body, None
        except Exception as exc:
            return None, None, str(exc)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='model_catalog + prompt_watch 공유용 스모크 리포트 생성')
    parser.add_argument('--base-url', required=True, help='실행 중인 고봉밥 API base URL')
    parser.add_argument('--output-dir', required=True, type=Path, help='JSON/Markdown 리포트 저장 디렉터리')
    parser.add_argument('--timeout', type=float, default=10.0, help='HTTP timeout seconds')
    parser.add_argument('--session-id', type=int, help='catalog/session 시나리오에 사용할 세션 ID')
    parser.add_argument('--catalog-id', help='우선 사용할 catalog_id. 없으면 active catalog 첫 항목 사용')
    return parser.parse_args()


def _make_check(name: str, category: str, severity: str, status: str, details: Dict[str, Any]) -> CheckResult:
    return CheckResult(name=name, category=category, severity=severity, status=status, details=details)


def _gather_keys(value: Any) -> List[str]:
    keys: List[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.append(str(key))
            keys.extend(_gather_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.extend(_gather_keys(item))
    return keys


def _find_long_summary_paths(value: Any, path: str = 'prompt_watch') -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            child_path = f'{path}.{key}'
            if key == 'summary_text' and isinstance(nested, str) and len(nested) > SUMMARY_TEXT_LIMIT:
                violations.append({'path': child_path, 'length': len(nested)})
            violations.extend(_find_long_summary_paths(nested, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(_find_long_summary_paths(item, f'{path}[{index}]'))
    return violations


def _forbidden_prompt_exposure(prompt_watch: Any) -> Dict[str, Any]:
    keys = set(_gather_keys(prompt_watch))
    present = sorted(key for key in FORBIDDEN_PROMPT_KEYS if key in keys)
    long_summary_paths = _find_long_summary_paths(prompt_watch)
    return {
        'forbidden_keys_present': present,
        'summary_text_violations': long_summary_paths,
        'ok': not present and not long_summary_paths,
    }


def _pick_model_fields(model_payload: Any) -> Dict[str, Any]:
    if not isinstance(model_payload, dict):
        return {}
    return {
        'provider': model_payload.get('provider'),
        'model': model_payload.get('model'),
        'mode': model_payload.get('mode'),
        'source': model_payload.get('source'),
        'catalog_id': model_payload.get('catalog_id'),
        'label': model_payload.get('label'),
        'role_tags': model_payload.get('role_tags'),
    }


def _snapshot_prompt_watch(prompt_watch: Any) -> Dict[str, Any]:
    if not isinstance(prompt_watch, dict):
        return {}
    snapshot = {
        'active_character_id': prompt_watch.get('active_character_id'),
        'active_character_name': prompt_watch.get('active_character_name'),
        'selected_speaker_id': prompt_watch.get('selected_speaker_id'),
        'selected_speaker_type': prompt_watch.get('selected_speaker_type'),
        'scene_id': prompt_watch.get('scene_id'),
        'world_id': prompt_watch.get('world_id'),
        'input_mode': prompt_watch.get('input_mode'),
        'target_character_hint': prompt_watch.get('target_character_hint'),
        'lore_hit_ids': prompt_watch.get('lore_hit_ids'),
        'memory_hit_ids': prompt_watch.get('memory_hit_ids'),
        'relationship_hit_ids': prompt_watch.get('relationship_hit_ids'),
        'repair_used': prompt_watch.get('repair_used'),
        'fallback_used': prompt_watch.get('fallback_used'),
        'model': _pick_model_fields(prompt_watch.get('model')),
    }
    if 'generation_path' in prompt_watch:
        snapshot['generation_path'] = prompt_watch.get('generation_path')
    if 'applied_context' in prompt_watch and isinstance(prompt_watch.get('applied_context'), dict):
        applied_context = prompt_watch['applied_context']
        snapshot['applied_context_counts'] = {
            'lore': len(applied_context.get('lore', []) or []),
            'memories': len(applied_context.get('memories', []) or []),
            'relationships': len(applied_context.get('relationships', []) or []),
            'scene_keys': sorted(applied_context.get('scene', {}).keys()) if isinstance(applied_context.get('scene'), dict) else [],
        }
    return snapshot


def _extract_error_info(body: Any) -> Dict[str, Optional[str]]:
    if not isinstance(body, dict):
        return {'error_code': None, 'failure_reason': None}
    return {
        'error_code': str(body.get('error_code') or '').strip() or None,
        'failure_reason': str(body.get('failure_reason') or '').strip() or None,
    }


def _is_missing_narration_warning(status_code: Optional[int], body: Any) -> bool:
    error_info = _extract_error_info(body)
    return bool(
        status_code == 422
        and error_info['error_code'] in NARRATION_ERROR_CODES
        and error_info['failure_reason'] in NARRATION_FAILURE_REASONS
    )


def _build_admin_chat_payload(session_id: int, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        'session_id': session_id,
        'question': DEFAULT_QUESTION,
        'stream': False,
        'audience': 'admin',
        'user_profile_id': 'user_char_01',
        'character_id': 'bot_char_01',
        'scene_id': 'scene_default',
        'world_id': 'default',
        'lore_topics': ['IPC'],
    }
    if overrides:
        payload.update(overrides)
    return payload


def _build_user_chat_payload(session_id: int, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        'session_id': session_id,
        'question': DEFAULT_QUESTION,
        'stream': False,
        'audience': 'user',
        'user_profile_id': 'user_char_01',
        'character_id': 'bot_char_01',
        'scene_id': 'scene_default',
        'world_id': 'default',
        'lore_topics': ['IPC'],
    }
    if overrides:
        payload.update(overrides)
    return payload


def _check_catalog_list(client: SmokeClient, requested_catalog_id: Optional[str]) -> Tuple[CheckResult, Optional[Dict[str, Any]]]:
    status_code, body, error = client.request_json('GET', '/models/catalog')
    details: Dict[str, Any] = {'session_id': None, 'http_status': status_code}
    if error is not None:
        details['error'] = error
        return _make_check('catalog_list', 'core', 'hard', 'failed', details), None
    if status_code != 200 or not isinstance(body, list):
        details['response_preview'] = body
        return _make_check('catalog_list', 'core', 'hard', 'failed', details), None
    details['count'] = len(body)
    details['ids'] = [item.get('id') for item in body if isinstance(item, dict)]
    if not body:
        details['error'] = 'active catalog list is empty'
        return _make_check('catalog_list', 'core', 'hard', 'failed', details), None

    selected = None
    if requested_catalog_id:
        for item in body:
            if isinstance(item, dict) and item.get('id') == requested_catalog_id:
                selected = item
                break
        if selected is None:
            details['error'] = f'requested catalog_id not found in active catalog list: {requested_catalog_id}'
            return _make_check('catalog_list', 'core', 'hard', 'failed', details), None
    else:
        selected = next((item for item in body if isinstance(item, dict)), None)

    selected = selected or {}
    details['selected_catalog'] = {
        'id': selected.get('id'),
        'label': selected.get('label'),
        'role_tags': selected.get('role_tags'),
        'status': selected.get('status'),
    }
    ok = bool(
        selected.get('id')
        and selected.get('label')
        and isinstance(selected.get('role_tags'), list)
        and selected.get('status') == 'active'
    )
    return _make_check('catalog_list', 'core', 'hard', 'passed' if ok else 'failed', details), selected


def _check_catalog_select(client: SmokeClient, catalog_item: Optional[Dict[str, Any]], session_id: Optional[int]) -> Tuple[CheckResult, Optional[int]]:
    details: Dict[str, Any] = {
        'session_id': session_id,
        'selected_catalog_id': catalog_item.get('id') if isinstance(catalog_item, dict) else None,
    }
    if not isinstance(catalog_item, dict) or not catalog_item.get('id'):
        details['error'] = 'catalog selection skipped because no active catalog item was resolved'
        return _make_check('catalog_select', 'core', 'hard', 'failed', details), None

    select_payload: Dict[str, Any] = {'selection': {'catalog_id': catalog_item['id']}}
    if session_id is not None:
        select_payload['session_id'] = session_id

    select_status, select_body, select_error = client.request_json('POST', '/models/select', payload=select_payload)
    details['select_http_status'] = select_status
    if select_error is not None:
        details['error'] = select_error
        return _make_check('catalog_select', 'core', 'hard', 'failed', details), None
    details['select_response'] = select_body
    if select_status != 200 or not isinstance(select_body, dict):
        return _make_check('catalog_select', 'core', 'hard', 'failed', details), None

    resolved_session_id = select_body.get('session_id')
    details['session_id'] = resolved_session_id
    session_status, session_body, session_error = client.request_json('GET', f'/models/sessions/{resolved_session_id}')
    details['session_http_status'] = session_status
    if session_error is not None:
        details['error'] = session_error
        return _make_check('catalog_select', 'core', 'hard', 'failed', details), resolved_session_id
    details['session_response'] = session_body

    admin_status, admin_body, admin_error = client.request_json(
        'POST',
        '/chat/ask',
        payload=_build_admin_chat_payload(resolved_session_id, {'catalog_id': catalog_item['id']}),
    )
    details['admin_chat_http_status'] = admin_status
    details['admin_chat_error'] = admin_error
    prompt_watch = admin_body.get('prompt_watch') if isinstance(admin_body, dict) else None
    details['admin_prompt_watch'] = _snapshot_prompt_watch(prompt_watch)
    details['admin_prompt_exposure'] = _forbidden_prompt_exposure(prompt_watch)
    details['admin_has_retrieval_debug'] = isinstance(admin_body, dict) and 'retrieval_debug' in admin_body
    details['admin_has_rp_debug'] = isinstance(admin_body, dict) and 'rp_debug' in admin_body

    selected = session_body.get('selected') if isinstance(session_body, dict) else {}
    ok = bool(
        session_status == 200
        and isinstance(selected, dict)
        and selected.get('catalog_id') == catalog_item['id']
        and selected.get('label')
        and isinstance(selected.get('role_tags'), list)
        and selected.get('status')
        and admin_status == 200
        and isinstance(prompt_watch, dict)
        and prompt_watch.get('model', {}).get('source') == 'catalog'
        and details['admin_prompt_exposure']['ok']
    )
    return _make_check('catalog_select', 'core', 'hard', 'passed' if ok else 'failed', details), resolved_session_id


def _check_explicit_select(client: SmokeClient, catalog_item: Optional[Dict[str, Any]]) -> Tuple[CheckResult, Optional[int], Optional[Dict[str, Any]]]:
    details: Dict[str, Any] = {'session_id': None}
    if not isinstance(catalog_item, dict) or not catalog_item.get('provider') or not catalog_item.get('model'):
        details['error'] = 'explicit selection skipped because catalog item is unavailable'
        return _make_check('explicit_select', 'core', 'hard', 'failed', details), None, None

    explicit_payload = {
        'provider': catalog_item['provider'],
        'model': catalog_item['model'],
        'mode': catalog_item.get('default_mode') or 'fast',
    }
    details['explicit_selection'] = explicit_payload

    select_status, select_body, select_error = client.request_json(
        'POST',
        '/models/select',
        payload={'selection': explicit_payload},
    )
    details['select_http_status'] = select_status
    if select_error is not None:
        details['error'] = select_error
        return _make_check('explicit_select', 'core', 'hard', 'failed', details), None, explicit_payload
    details['select_response'] = select_body
    if select_status != 200 or not isinstance(select_body, dict):
        return _make_check('explicit_select', 'core', 'hard', 'failed', details), None, explicit_payload

    session_id = select_body.get('session_id')
    details['session_id'] = session_id
    session_status, session_body, session_error = client.request_json('GET', f'/models/sessions/{session_id}')
    details['session_http_status'] = session_status
    if session_error is not None:
        details['error'] = session_error
        return _make_check('explicit_select', 'core', 'hard', 'failed', details), session_id, explicit_payload
    details['session_response'] = session_body

    admin_status, admin_body, admin_error = client.request_json(
        'POST',
        '/chat/ask',
        payload=_build_admin_chat_payload(session_id, explicit_payload),
    )
    details['admin_chat_http_status'] = admin_status
    details['admin_chat_error'] = admin_error
    prompt_watch = admin_body.get('prompt_watch') if isinstance(admin_body, dict) else None
    details['admin_prompt_watch'] = _snapshot_prompt_watch(prompt_watch)
    details['admin_prompt_exposure'] = _forbidden_prompt_exposure(prompt_watch)
    details['admin_has_retrieval_debug'] = isinstance(admin_body, dict) and 'retrieval_debug' in admin_body
    details['admin_has_rp_debug'] = isinstance(admin_body, dict) and 'rp_debug' in admin_body

    selected = session_body.get('selected') if isinstance(session_body, dict) else {}
    ok = bool(
        session_status == 200
        and isinstance(selected, dict)
        and selected.get('catalog_id') is None
        and selected.get('provider') == explicit_payload['provider']
        and selected.get('model') == explicit_payload['model']
        and selected.get('mode') == explicit_payload['mode']
        and admin_status == 200
        and isinstance(prompt_watch, dict)
        and prompt_watch.get('model', {}).get('source') == 'explicit_request'
        and details['admin_prompt_exposure']['ok']
    )
    return _make_check('explicit_select', 'core', 'hard', 'passed' if ok else 'failed', details), session_id, explicit_payload


def _check_explicit_user_compact(client: SmokeClient, session_id: Optional[int], explicit_payload: Optional[Dict[str, Any]]) -> CheckResult:
    details: Dict[str, Any] = {'session_id': session_id, 'explicit_selection': explicit_payload}
    if session_id is None or not explicit_payload:
        details['error'] = 'explicit user compact check skipped because explicit session is unavailable'
        return _make_check('explicit_user_compact', 'content', 'soft', 'skipped', details)

    user_status, user_body, user_error = client.request_json(
        'POST',
        '/chat/ask',
        payload=_build_user_chat_payload(session_id, explicit_payload),
    )
    details['http_status'] = user_status
    details['request_error'] = user_error
    if user_error is not None:
        details['error'] = user_error
        return _make_check('explicit_user_compact', 'content', 'soft', 'failed', details)

    if _is_missing_narration_warning(user_status, user_body):
        details.update(_extract_error_info(user_body))
        details['warning'] = 'content-dependent validation failure observed; core explicit path verified via admin response'
        return _make_check('explicit_user_compact', 'content', 'soft', 'warning', details)

    prompt_watch = user_body.get('prompt_watch') if isinstance(user_body, dict) else None
    details['prompt_watch'] = _snapshot_prompt_watch(prompt_watch)
    details['prompt_exposure'] = _forbidden_prompt_exposure(prompt_watch)
    ok = bool(
        user_status == 200
        and isinstance(prompt_watch, dict)
        and 'applied_context' not in prompt_watch
        and 'generation_path' not in prompt_watch
        and prompt_watch.get('model', {}).get('source') == 'explicit_request'
        and details['prompt_exposure']['ok']
    )
    return _make_check('explicit_user_compact', 'content', 'soft', 'passed' if ok else 'failed', details)


def _check_prompt_watch_admin_detail(client: SmokeClient, session_id: Optional[int]) -> CheckResult:
    details: Dict[str, Any] = {'session_id': session_id}
    if session_id is None:
        details['error'] = 'prompt_watch admin detail skipped because catalog session is unavailable'
        return _make_check('prompt_watch_admin_detail', 'core', 'hard', 'failed', details)

    admin_status, admin_body, admin_error = client.request_json(
        'POST',
        '/chat/ask',
        payload=_build_admin_chat_payload(session_id),
    )
    details['http_status'] = admin_status
    details['request_error'] = admin_error
    if admin_error is not None:
        details['error'] = admin_error
        return _make_check('prompt_watch_admin_detail', 'core', 'hard', 'failed', details)

    prompt_watch = admin_body.get('prompt_watch') if isinstance(admin_body, dict) else None
    details['prompt_watch'] = _snapshot_prompt_watch(prompt_watch)
    details['prompt_exposure'] = _forbidden_prompt_exposure(prompt_watch)
    details['has_retrieval_debug'] = isinstance(admin_body, dict) and 'retrieval_debug' in admin_body
    details['has_rp_debug'] = isinstance(admin_body, dict) and 'rp_debug' in admin_body

    ok = bool(
        admin_status == 200
        and isinstance(prompt_watch, dict)
        and 'applied_context' in prompt_watch
        and 'generation_path' in prompt_watch
        and prompt_watch.get('model', {}).get('source') == 'session'
        and details['has_retrieval_debug']
        and details['has_rp_debug']
        and details['prompt_exposure']['ok']
    )
    return _make_check('prompt_watch_admin_detail', 'core', 'hard', 'passed' if ok else 'failed', details)


def _check_prompt_watch_user_compact(client: SmokeClient, session_id: Optional[int]) -> CheckResult:
    details: Dict[str, Any] = {'session_id': session_id}
    if session_id is None:
        details['error'] = 'prompt_watch user compact skipped because catalog session is unavailable'
        return _make_check('prompt_watch_user_compact', 'content', 'soft', 'skipped', details)

    user_status, user_body, user_error = client.request_json(
        'POST',
        '/chat/ask',
        payload=_build_user_chat_payload(session_id),
    )
    details['http_status'] = user_status
    details['request_error'] = user_error
    if user_error is not None:
        details['error'] = user_error
        return _make_check('prompt_watch_user_compact', 'content', 'soft', 'failed', details)

    if _is_missing_narration_warning(user_status, user_body):
        details.update(_extract_error_info(user_body))
        details['warning'] = 'content-dependent validation failure observed; core session/detail path verified via admin response'
        return _make_check('prompt_watch_user_compact', 'content', 'soft', 'warning', details)

    prompt_watch = user_body.get('prompt_watch') if isinstance(user_body, dict) else None
    details['prompt_watch'] = _snapshot_prompt_watch(prompt_watch)
    details['prompt_exposure'] = _forbidden_prompt_exposure(prompt_watch)
    ok = bool(
        user_status == 200
        and isinstance(prompt_watch, dict)
        and 'applied_context' not in prompt_watch
        and 'generation_path' not in prompt_watch
        and prompt_watch.get('model', {}).get('source') == 'session'
        and details['prompt_exposure']['ok']
    )
    return _make_check('prompt_watch_user_compact', 'content', 'soft', 'passed' if ok else 'failed', details)


def _build_summary(checks: List[CheckResult]) -> Dict[str, int]:
    core_checks = [item for item in checks if item.category == 'core']
    content_checks = [item for item in checks if item.category == 'content']
    return {
        'core_total': len(core_checks),
        'core_passed': sum(1 for item in core_checks if item.status == 'passed'),
        'core_failed': sum(1 for item in core_checks if item.status == 'failed'),
        'content_total': len(content_checks),
        'content_passed': sum(1 for item in content_checks if item.status == 'passed'),
        'content_failed': sum(1 for item in content_checks if item.status == 'failed'),
        'warnings': sum(1 for item in checks if item.status == 'warning'),
        'skipped': sum(1 for item in checks if item.status == 'skipped'),
    }


def _build_report(base_url: str, selected_catalog_id: Optional[str], primary_session_id: Optional[int], checks: List[CheckResult]) -> Dict[str, Any]:
    return {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'base_url': base_url,
        'session_id': primary_session_id,
        'selected_catalog_id': selected_catalog_id,
        'prompt': DEFAULT_QUESTION,
        'checks': [asdict(item) for item in checks],
        'summary': _build_summary(checks),
    }


def _write_json_report(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _status_icon(status: str) -> str:
    return {
        'passed': 'PASS',
        'failed': 'FAIL',
        'warning': 'WARN',
        'skipped': 'SKIP',
    }.get(status, status.upper())


def _write_markdown_report(path: Path, payload: Dict[str, Any]) -> None:
    checks = payload['checks']
    summary = payload['summary']
    core_checks = [item for item in checks if item['category'] == 'core']
    content_checks = [item for item in checks if item['category'] == 'content']
    warning_checks = [item for item in checks if item['status'] == 'warning']
    lines = [
        '# Model Catalog + Prompt Watch Smoke Report',
        '',
        '## 실행 정보',
        '',
        f"- timestamp: {payload['timestamp']}",
        f"- base_url: {payload['base_url']}",
        f"- primary session_id: {payload.get('session_id')}",
        f"- selected_catalog_id: {payload.get('selected_catalog_id')}",
        f"- prompt: {payload.get('prompt')}",
        '',
        '## 최종 요약',
        '',
        f"- Core checks passed: {summary['core_passed']}/{summary['core_total']}",
        f"- Content-dependent checks passed: {summary['content_passed']}/{summary['content_total']}",
        f"- Core failures: {summary['core_failed']}",
        f"- Content failures: {summary['content_failed']}",
        f"- Warnings: {summary['warnings']}",
        f"- Skipped: {summary['skipped']}",
        '',
        '## Core Checks',
        '',
    ]
    for check in core_checks:
        lines.append(f"- [{_status_icon(check['status'])}] {check['name']} (session_id={check['details'].get('session_id')})")
    lines.extend(['', '## Content-Dependent Checks', ''])
    for check in content_checks:
        lines.append(f"- [{_status_icon(check['status'])}] {check['name']} (session_id={check['details'].get('session_id')})")
    lines.extend(['', '## Warnings', ''])
    if warning_checks:
        for check in warning_checks:
            lines.append(
                f"- {check['name']}: {check['details'].get('failure_reason') or check['details'].get('warning') or 'warning'}"
            )
    else:
        lines.append('- 없음')

    lines.extend(['', '## 시나리오별 결과', ''])
    for check in checks:
        details = check['details']
        lines.extend(
            [
                f"### {check['name']}",
                f"- category: {check['category']}",
                f"- severity: {check['severity']}",
                f"- status: {check['status']}",
                f"- session_id: {details.get('session_id')}",
                f"- note: {details.get('error') or details.get('warning') or 'ok'}",
                '',
            ]
        )
        if check['name'] == 'catalog_list':
            lines.extend(
                [
                    '- snapshot: active catalog list and selected model metadata',
                    f"- active_count: {details.get('count')}",
                    f"- ids: {', '.join(details.get('ids', [])) or '-'}",
                    f"- selected_catalog: {json.dumps(details.get('selected_catalog', {}), ensure_ascii=False)}",
                    '',
                ]
            )
        elif check['name'] in {'catalog_select', 'explicit_select'}:
            lines.extend(
                [
                    '- snapshot: session-selected metadata and admin prompt_watch model',
                    f"- session_selected: {json.dumps((details.get('session_response') or {}).get('selected', {}), ensure_ascii=False)}",
                    f"- admin_prompt_watch: {json.dumps(details.get('admin_prompt_watch', {}), ensure_ascii=False)}",
                    f"- forbidden_exposure: {json.dumps(details.get('admin_prompt_exposure', {}), ensure_ascii=False)}",
                    '',
                ]
            )
        else:
            lines.extend(
                [
                    '- snapshot: prompt_watch and exposure result',
                    f"- prompt_watch: {json.dumps(details.get('prompt_watch', {}), ensure_ascii=False)}",
                    f"- prompt_exposure: {json.dumps(details.get('prompt_exposure', {}) or details.get('user_prompt_exposure', {}), ensure_ascii=False)}",
                    '',
                ]
            )

    admin_compare = next((item for item in checks if item['name'] == 'prompt_watch_admin_detail'), None)
    user_compare = next((item for item in checks if item['name'] == 'prompt_watch_user_compact'), None)
    lines.extend(['## User/Admin 응답 비교 요약', ''])
    if admin_compare:
        lines.append(f"- admin source: {(admin_compare['details'].get('prompt_watch') or {}).get('model', {}).get('source')}")
        lines.append(f"- admin retrieval_debug preserved: {admin_compare['details'].get('has_retrieval_debug')}")
        lines.append(f"- admin rp_debug preserved: {admin_compare['details'].get('has_rp_debug')}")
    if user_compare:
        lines.append(f"- user status: {user_compare['status']}")
        if user_compare['status'] == 'passed':
            lines.append(f"- user source: {(user_compare['details'].get('prompt_watch') or {}).get('model', {}).get('source')}")
        else:
            lines.append(
                f"- user validation note: {user_compare['details'].get('failure_reason') or user_compare['details'].get('warning') or user_compare['details'].get('error') or '-'}"
            )

    lines.extend(['', '## Warning 상세', ''])
    if warning_checks:
        for check in warning_checks:
            lines.append(f"- {check['name']}: http_status={check['details'].get('http_status')} error_code={check['details'].get('error_code')} failure_reason={check['details'].get('failure_reason')}")
    else:
        lines.append('- 없음')

    core_failed = summary['core_failed']
    lines.extend(['', '## 최종 판정', ''])
    if core_failed == 0:
        lines.append('- Core functionality verified successfully.')
        if summary['warnings'] > 0 or summary['content_failed'] > 0:
            lines.append('- User RP response validation failed for this prompt, but core model_catalog/prompt_watch integration remains healthy.')
            lines.append('- See warnings for content-dependent failures.')
    else:
        lines.append('- Core functionality verification failed.')
        lines.append('- Review failed core checks before trusting this environment.')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    args = _parse_args()
    client = SmokeClient(
        base_url=args.base_url,
        timeout=args.timeout,
        x_user=f'smoke_{uuid.uuid4().hex[:8]}',
    )

    checks: List[CheckResult] = []
    catalog_check, catalog_item = _check_catalog_list(client, args.catalog_id)
    checks.append(catalog_check)

    selected_catalog_id = catalog_item.get('id') if isinstance(catalog_item, dict) else None
    catalog_select_check, catalog_session_id = _check_catalog_select(client, catalog_item, args.session_id)
    checks.append(catalog_select_check)

    explicit_select_check, explicit_session_id, explicit_payload = _check_explicit_select(client, catalog_item)
    checks.append(explicit_select_check)

    checks.append(_check_explicit_user_compact(client, explicit_session_id, explicit_payload))
    checks.append(_check_prompt_watch_admin_detail(client, catalog_session_id))
    checks.append(_check_prompt_watch_user_compact(client, catalog_session_id))

    report = _build_report(
        base_url=args.base_url,
        selected_catalog_id=selected_catalog_id,
        primary_session_id=catalog_session_id,
        checks=checks,
    )
    report['explicit_session_id'] = explicit_session_id

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / 'model_catalog_prompt_watch_smoke.json'
    md_path = output_dir / 'model_catalog_prompt_watch_smoke.md'
    _write_json_report(json_path, report)
    _write_markdown_report(md_path, report)

    print(f'json: {json_path}')
    print(f'markdown: {md_path}')
    print(json.dumps(report['summary'], ensure_ascii=False))
    return 0 if report['summary']['core_failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
