#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path.cwd()
TASKS_DIR = ROOT / 'governance' / 'runtime' / 'tasks'
FAILURE_WRITER = ROOT / 'governance' / 'scripts' / 'system_failure_result_writer_v1.py'
APPLY_GUARDED = ROOT / 'governance' / 'scripts' / 'system_apply_result_guarded_v1.py'

MAX_STALL_CYCLES = 3

DEFAULT_HOURS = {
    'IMPLEMENT_TASK': 24,
    'WRITE_PLAN': 24,
    'REVIEW_PLAN': 24,
    'REVIEW_TASK': 24,
    'REVIEW_CODE': 24,
    'VERIFY_RESULT': 24,
    'REVIEW_INVALID_TASK': 24,
    '__default__': 24,
}

def parse_ts(value: str):
    value = (value or '').strip()
    if not value:
        return None
    try:
        if value.endswith('Z'):
            value = value[:-1] + '+00:00'
        return datetime.fromisoformat(value)
    except Exception:
        return None

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

def main() -> int:
    updated = []
    now = datetime.now(timezone.utc)

    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    for path in sorted(TASKS_DIR.glob('*.json')):
        if path.name == 'index.json':
            continue

        data = json.loads(path.read_text(encoding='utf-8'))

        task_id = str(data.get('task_id', '')).strip()
        next_action = str(data.get('next_action', '')).strip()
        next_role = str(data.get('next_role', '')).strip()
        last_event_ts = parse_ts(str(data.get('last_event_ts', '')).strip())

        if not task_id or not next_role or last_event_ts is None:
            continue

        if next_action == 'REVIEW_STALL':
            continue

        hours = DEFAULT_HOURS.get(next_action, DEFAULT_HOURS['__default__'])
        cutoff = now - timedelta(hours=hours)
        if last_event_ts > cutoff:
            continue

        prev_state = str(data.get('current_state', '')).strip()

        data['current_state'] = 'BLOCKED'
        data['last_event_type'] = 'TASK_STALLED'
        data['last_actor_role'] = 'SYSTEM'
        data['last_event_ts'] = utc_now()
        data['last_summary'] = f'Task exceeded SLA for next_action={next_action}'
        data['next_role'] = 'AUDITOR'
        data['next_action'] = 'REVIEW_STALL'
        data['error_class'] = 'TASK_STALLED'
        data['error_details'] = f'Task exceeded SLA for next_action={next_action}'
        data['last_failure_ts'] = data['last_event_ts']
        data['last_failure_from_state'] = prev_state
        data['stall_count'] = int(data.get('stall_count', 0) or 0) + 1

        if data['stall_count'] >= MAX_STALL_CYCLES:
            data['error_class'] = 'STALL_CYCLES_EXHAUSTED'
            data['error_details'] = f'Max stall cycles exhausted: {data["stall_count"]}/{MAX_STALL_CYCLES}'

        events = data.get('events', [])
        if not isinstance(events, list):
            events = []

        events.append({
            'event_id': f'TASK_STALLED:{task_id}',
            'event_type': 'TASK_STALLED',
            'actor_role': 'SYSTEM',
            'event_ts': data['last_event_ts'],
            'summary': data['last_summary'],
            'current_state': 'BLOCKED',
            'next_role': 'AUDITOR',
            'next_action': 'REVIEW_STALL',
        })
        data['events'] = events

        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

        role = next_role or 'EXECUTOR'
        error_class = data.get('error_class', 'TASK_STALLED')
        error_details = data.get('error_details', f'Task exceeded SLA for next_action={next_action}')

        failure_proc = subprocess.run(
            [
                sys.executable,
                str(FAILURE_WRITER),
                role,
                task_id,
                error_details,
                error_class,
                'BLOCKED',
            ],
            capture_output=True,
            text=True,
        )
        if failure_proc.stdout:
            print(failure_proc.stdout, end='')
        if failure_proc.stderr:
            print(failure_proc.stderr, end='', file=sys.stderr)

        apply_proc = subprocess.run(
            [sys.executable, str(APPLY_GUARDED)],
            capture_output=True,
            text=True,
        )
        if apply_proc.stdout:
            print(apply_proc.stdout, end='')
        if apply_proc.stderr:
            print(apply_proc.stderr, end='', file=sys.stderr)

        updated.append(str(path.relative_to(ROOT)))

    print(json.dumps({
        'system_stalled_task_watchdog_version': 'v1',
        'result': 'SUCCESS',
        'updated_count': len(updated),
        'updated_tasks': updated,
    }, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
