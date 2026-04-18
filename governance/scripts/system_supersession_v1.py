import json
from pathlib import Path

ROOT = Path.cwd()
TASKS_DIR = ROOT / 'governance' / 'runtime' / 'tasks'


def main() -> int:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    groups = {}
    touched = []

    for path in sorted(TASKS_DIR.glob('*.json')):
        if path.name == 'index.json':
            continue

        data = json.loads(path.read_text(encoding='utf-8'))
        task_id = str(data.get('task_id', '')).strip()
        parent_task_id = str(data.get('parent_task_id', '')).strip()
        current_state = str(data.get('current_state', '')).strip()

        if not task_id or not parent_task_id:
            continue
        if current_state in {'COMPLETED', 'COMPLETED_CLOSED', 'COMPLETED_OPEN_TERMINAL'}:
            continue

        groups.setdefault(parent_task_id, []).append((task_id, path, data))

    for parent_task_id, items in groups.items():
        if len(items) < 2:
            continue

        items.sort(
            key=lambda x: (
                str(x[2].get('last_event_ts', '')).strip(),
                x[0],
            ),
            reverse=True,
        )

        winner_task_id, _, _ = items[0]

        for task_id, path, data in items[1:]:
            if str(data.get('current_state', '')).strip() == 'SUPERSEDED':
                continue

            data['current_state'] = 'SUPERSEDED'
            data['last_event_type'] = 'TASK_SUPERSEDED'
            data['last_actor_role'] = 'SYSTEM'
            data['last_summary'] = f'Task superseded by newer sibling task {winner_task_id}'
            data['next_role'] = ''
            data['next_action'] = ''
            data['error_class'] = ''
            data['error_details'] = ''
            data['is_terminal'] = True
            data['closed_by_system'] = True
            data['terminal_reason'] = 'SUPERSEDED'
            data['superseded_by_task_id'] = winner_task_id

            events = data.get('events', [])
            if not isinstance(events, list):
                events = []
            events.append({
                'event_id': f'TASK_SUPERSEDED::{task_id}',
                'event_type': 'TASK_SUPERSEDED',
                'actor_role': 'SYSTEM',
                'event_ts': str(data.get('last_event_ts', '')).strip(),
                'summary': data['last_summary'],
                'current_state': 'SUPERSEDED',
                'next_role': '',
                'next_action': '',
            })
            data['events'] = events

            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            touched.append(str(path.relative_to(ROOT)))

    print(json.dumps({
        'system_supersession_version': 'v1',
        'result': 'SUCCESS',
        'updated_count': len(touched),
        'updated_tasks': touched,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
