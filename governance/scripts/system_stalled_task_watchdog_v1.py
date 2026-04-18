import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path.cwd()
TASKS_DIR = ROOT / 'governance' / 'runtime' / 'tasks'

SLA_HOURS = {
    'REVIEW_CODE': 2,
    'IMPLEMENT_TASK': 4,
}

DEFAULT_HOURS = 4


def parse_ts(value: str):
    value = str(value or '').strip()
    if not value:
        return None
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def main() -> int:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    updated = []

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

        hours = SLA_HOURS.get(next_action, DEFAULT_HOURS)
        cutoff = now - timedelta(hours=hours)

        if last_event_ts > cutoff:
            continue

        data['current_state'] = 'BLOCKED'
        data['last_event_type'] = 'TASK_STALLED'
        data['last_actor_role'] = 'SYSTEM'
        data['last_event_ts'] = now.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        data['last_summary'] = f'Task exceeded SLA for next_action={next_action}'
        data['next_role'] = 'AUDITOR'
        data['next_action'] = 'REVIEW_STALL'
        data['error_class'] = 'TASK_STALLED'
        data['error_details'] = f'SLA exceeded for next_action={next_action}'
        data['last_failure_ts'] = data['last_event_ts']
        data['last_failure_from_state'] = str(data.get('current_state', '')).strip()

        events = data.get('events', [])
        if not isinstance(events, list):
            events = []
        events.append({
            'event_id': f"TASK_STALLED::{task_id}",
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
