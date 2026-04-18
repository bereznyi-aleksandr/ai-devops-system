#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
TASKS_DIR = ROOT / 'governance' / 'runtime' / 'tasks'


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def infer_status_bucket(item: dict) -> str:
    current_state = str(item.get('current_state', '')).strip()
    next_role = str(item.get('next_role', '')).strip()
    is_terminal = bool(item.get('is_terminal', False))
    closed_by_system = bool(item.get('closed_by_system', False))

    if current_state == 'SUPERSEDED':
        return 'SUPERSEDED'
    if is_terminal and closed_by_system:
        return 'COMPLETED_CLOSED'
    if is_terminal:
        return 'COMPLETED_OPEN_TERMINAL'
    if next_role == 'SYSTEM':
        return 'AWAITING_SYSTEM'
    if next_role == 'AUDITOR':
        return 'AWAITING_AUDITOR'
    if next_role == 'EXECUTOR':
        return 'AWAITING_EXECUTOR'
    if current_state.endswith('PENDING'):
        return 'IN_PROGRESS'
    if current_state.endswith('APPROVED'):
        return 'APPROVED'
    if current_state.endswith('BLOCKED') or current_state == 'BLOCKED':
        return 'BLOCKED'
    return 'UNKNOWN'


def append_event(registry: dict) -> None:
    events = registry.get('events', [])
    if not isinstance(events, list):
        events = []
    events.append({
        'event_id': str(registry.get('last_event_id', '')).strip(),
        'parent_event_id': str(registry.get('last_parent_event_id', '')).strip(),
        'event_type': str(registry.get('last_event_type', '')).strip(),
        'actor_role': str(registry.get('last_actor_role', '')).strip(),
        'event_ts': str(registry.get('last_event_ts', '')).strip(),
        'summary': str(registry.get('last_summary', '')).strip(),
        'current_state': str(registry.get('current_state', '')).strip(),
        'next_role': str(registry.get('next_role', '')).strip(),
        'next_action': str(registry.get('next_action', '')).strip(),
        'latest_result_value': str(registry.get('latest_result_value', '')).strip(),
        'latest_result_manifest': str(registry.get('latest_result_manifest', '')).strip(),
    })
    registry['events'] = events


def main() -> int:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    updated = []

    for path in sorted(TASKS_DIR.glob('*.json')):
        if path.name == 'index.json':
            continue

        data = json.loads(path.read_text(encoding='utf-8'))
        task_id = str(data.get('task_id', '')).strip()
        if not task_id:
            continue

        bucket = infer_status_bucket(data)
        if bucket != 'UNKNOWN':
            continue

        prev_state = str(data.get('current_state', '')).strip()
        data['current_state'] = 'BLOCKED'
        data['last_event_id'] = f'TASK_INVALID_STATE::{task_id}'
        data['last_parent_event_id'] = str(data.get('last_event_id', '')).strip()
        data['last_event_type'] = 'TASK_INVALID_STATE'
        data['last_actor_role'] = 'SYSTEM'
        data['last_event_ts'] = now
        data['last_summary'] = f'Invalid task state detected and blocked by system for task_id={task_id}'
        data['next_role'] = 'AUDITOR'
        data['next_action'] = 'REVIEW_INVALID_TASK'
        data['latest_result_value'] = 'BLOCKED'
        data['error_class'] = 'INVALID_TASK_STATE'
        data['error_details'] = f'Unknown status bucket derived from current_state={prev_state!r}'
        data['last_failure_ts'] = now
        data['last_failure_from_state'] = prev_state
        data['is_terminal'] = False
        data['closed_by_system'] = False

        append_event(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        updated.append(str(path.relative_to(ROOT)))

    print(json.dumps({
        'system_invalid_task_watchdog_version': 'v1',
        'result': 'SUCCESS',
        'updated_count': len(updated),
        'updated_tasks': updated,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
