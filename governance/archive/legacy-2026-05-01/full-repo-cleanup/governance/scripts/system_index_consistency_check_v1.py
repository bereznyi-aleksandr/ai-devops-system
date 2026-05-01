import json
from pathlib import Path

ROOT = Path.cwd()
TASKS_DIR = ROOT / 'governance' / 'runtime' / 'tasks'
INDEX_PATH = TASKS_DIR / 'index.json'


def infer_status_bucket(data):
    current_state = str(data.get('current_state', '')).strip()
    next_role = str(data.get('next_role', '')).strip()
    is_terminal = bool(data.get('is_terminal', False))
    closed_by_system = bool(data.get('closed_by_system', False))

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


def build_index_doc():
    items = []

    for path in sorted(TASKS_DIR.glob('*.json')):
        if path.name == 'index.json':
            continue

        data = json.loads(path.read_text(encoding='utf-8'))
        task_id = str(data.get('task_id', '')).strip()
        if not task_id:
            continue

        item = {
            'task_id': task_id,
            'registry_path': str(path.relative_to(ROOT)),
            'current_state': str(data.get('current_state', '')).strip(),
            'last_event_type': str(data.get('last_event_type', '')).strip(),
            'next_role': str(data.get('next_role', '')).strip(),
            'next_action': str(data.get('next_action', '')).strip(),
            'is_terminal': bool(data.get('is_terminal', False)),
            'closed_by_system': bool(data.get('closed_by_system', False)),
            'last_event_ts': str(data.get('last_event_ts', '')).strip(),
        }
        item['status_bucket'] = infer_status_bucket(data)
        items.append(item)

    items.sort(
        key=lambda x: (str(x.get('last_event_ts', '')), str(x.get('task_id', ''))),
        reverse=True,
    )

    summary = {}
    for item in items:
        bucket = item['status_bucket']
        summary[bucket] = summary.get(bucket, 0) + 1
    summary['TOTAL'] = len(items)

    return {
        'system_task_index_version': 'v1',
        'result': 'SUCCESS',
        'tasks_dir': str(TASKS_DIR.relative_to(ROOT)),
        'index_path': str(INDEX_PATH.relative_to(ROOT)),
        'summary': summary,
        'items': items,
    }


def normalize(doc):
    return json.dumps(doc, ensure_ascii=False, sort_keys=True)


def main() -> int:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    rebuilt = build_index_doc()

    if not INDEX_PATH.exists():
        INDEX_PATH.write_text(json.dumps(rebuilt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({
            'system_index_consistency_check_version': 'v1',
            'result': 'REBUILT',
            'reason': 'INDEX_MISSING',
            'index_path': str(INDEX_PATH.relative_to(ROOT)),
            'summary': rebuilt['summary'],
        }, ensure_ascii=False, indent=2))
        return 0

    current = json.loads(INDEX_PATH.read_text(encoding='utf-8'))

    if normalize(current) != normalize(rebuilt):
        INDEX_PATH.write_text(json.dumps(rebuilt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({
            'system_index_consistency_check_version': 'v1',
            'result': 'REBUILT',
            'reason': 'INDEX_OUT_OF_SYNC',
            'index_path': str(INDEX_PATH.relative_to(ROOT)),
            'summary': rebuilt['summary'],
        }, ensure_ascii=False, indent=2))
        return 0

    print(json.dumps({
        'system_index_consistency_check_version': 'v1',
        'result': 'CONSISTENT',
        'index_path': str(INDEX_PATH.relative_to(ROOT)),
        'summary': rebuilt['summary'],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
