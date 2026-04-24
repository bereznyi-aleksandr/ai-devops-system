import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path.cwd()
TASKS_DIR = ROOT / 'governance' / 'runtime' / 'tasks'
RESULTS_DIR = ROOT / 'governance' / 'runtime' / 'results'
TIMEOUT_MINUTES = 15


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


def close_manifest_payload(task_id: str, ts_utc: str):
    return {
        'result_manifest_version': 'v1',
        'task_id': task_id,
        'role': 'SYSTEM',
        'result': 'SUCCESS',
        'ts_utc': ts_utc,
        'summary': 'Watchdog auto-closed COMPLETED_OPEN_TERMINAL task after timeout',
        'event_type': 'SYSTEM_CLOSE_TIMEOUT',
    }


def main() -> int:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=TIMEOUT_MINUTES)
    generated = []

    for path in sorted(TASKS_DIR.glob('*.json')):
        if path.name == 'index.json':
            continue

        data = json.loads(path.read_text(encoding='utf-8'))
        task_id = str(data.get('task_id', '')).strip()
        is_terminal = bool(data.get('is_terminal', False))
        closed_by_system = bool(data.get('closed_by_system', False))
        current_state = str(data.get('current_state', '')).strip()
        last_event_ts = parse_ts(str(data.get('last_event_ts', '')).strip())

        if not task_id or is_terminal or closed_by_system:
            continue
        should_close_timeout = (
            current_state == 'BLOCKED'
            and str(data.get('next_role', '')).strip().upper() == 'SYSTEM'
            and str(data.get('next_action', '')).strip().upper() == 'CLOSE_TIMEOUT'
        )
        should_close_completed = (current_state == 'COMPLETED')
        if not (should_close_timeout or should_close_completed):
            continue
        if should_close_timeout:
            pass
        elif last_event_ts is None or last_event_ts > cutoff:
            continue
        elif last_event_ts is None or last_event_ts > cutoff:
            continue

        out_path = RESULTS_DIR / f'system_close_result_{task_id}.json'
        payload = close_manifest_payload(task_id, now.replace(microsecond=0).isoformat().replace('+00:00', 'Z'))
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        generated.append(str(out_path.relative_to(ROOT)))

    print(json.dumps({
        'system_terminal_watchdog_version': 'v1',
        'result': 'SUCCESS',
        'timeout_minutes': TIMEOUT_MINUTES,
        'generated_count': len(generated),
        'generated_manifests': generated,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
