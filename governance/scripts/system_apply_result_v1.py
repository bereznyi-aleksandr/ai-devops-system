import json
from pathlib import Path
from typing import Dict, List, Tuple

from system_transition_map_v1 import resolve_success_transition  # noqa: E402

ROOT = Path.cwd()
TASKS_DIR = ROOT / 'governance' / 'runtime' / 'tasks'
INDEX_PATH = TASKS_DIR / 'index.json'
RESULTS_DIR = ROOT / 'governance' / 'runtime' / 'results'


class ApplyResultError(RuntimeError):
    pass


ROLE_PRIORITY = {
    'EXECUTOR': 1,
    'AUDITOR': 2,
    'SYSTEM': 3,
}


def read_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding='utf-8'))


def choose_latest_result() -> Tuple[Path, Dict[str, object]]:
    found: List[Tuple[str, int, str, Path, Dict[str, object]]] = []

    if not RESULTS_DIR.exists():
        raise ApplyResultError('Results directory does not exist')

    for path in sorted(RESULTS_DIR.glob('*.json')):
        try:
            data = read_json(path)
        except Exception:
            continue

        role = str(data.get('role', '')).strip().upper()
        ts = str(data.get('ts_utc', '')).strip()
        task_id = str(data.get('task_id', '')).strip()
        result_value = str(data.get('result', '')).strip().upper()

        if not role or not ts or not task_id or not result_value:
            continue

        found.append((ts, ROLE_PRIORITY.get(role, 0), path.name, path, data))

    if not found:
        raise ApplyResultError('No valid result manifests found in governance/runtime/results')

    found.sort(key=lambda x: (x[0], x[1], x[2]))
    _, _, _, path, data = found[-1]
    return path, data


def infer_status_bucket(item: Dict[str, object]) -> str:
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


def append_event(registry: Dict[str, object]) -> None:
    events = registry.get('events', [])
    if not isinstance(events, list):
        events = []

    events.append(
        {
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
        }
    )

    registry['events'] = events


def rebuild_index() -> Dict[str, object]:
    items: List[Dict[str, object]] = []

    for path in sorted(TASKS_DIR.glob('*.json')):
        if path.name == 'index.json':
            continue

        data = read_json(path)
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

    items.sort(key=lambda x: (str(x.get('last_event_ts', '')), str(x.get('task_id', ''))), reverse=True)

    summary: Dict[str, int] = {}
    for item in items:
        bucket = str(item.get('status_bucket', 'UNKNOWN'))
        summary[bucket] = summary.get(bucket, 0) + 1
    summary['TOTAL'] = len(items)

    index_doc = {
        'system_task_index_version': 'v1',
        'result': 'SUCCESS',
        'tasks_dir': str(TASKS_DIR.relative_to(ROOT)),
        'index_path': str(INDEX_PATH.relative_to(ROOT)),
        'summary': summary,
        'items': items,
    }

    INDEX_PATH.write_text(json.dumps(index_doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return index_doc


def load_registry(task_id: str) -> Dict[str, object]:
    path = TASKS_DIR / f'{task_id}.json'
    if not path.exists():
        raise ApplyResultError(f'Registry not found for task_id={task_id}')
    return read_json(path)


def write_registry(task_id: str, registry: Dict[str, object]) -> Path:
    path = TASKS_DIR / f'{task_id}.json'
    out = {
        'task_id': str(registry.get('task_id', task_id)).strip(),
        'current_state': str(registry.get('current_state', '')).strip(),
        'last_event_id': str(registry.get('last_event_id', '')).strip(),
        'last_parent_event_id': str(registry.get('last_parent_event_id', '')).strip(),
        'last_event_type': str(registry.get('last_event_type', '')).strip(),
        'last_actor_role': str(registry.get('last_actor_role', '')).strip(),
        'last_event_ts': str(registry.get('last_event_ts', '')).strip(),
        'last_summary': str(registry.get('last_summary', '')).strip(),
        'next_role': str(registry.get('next_role', '')).strip(),
        'next_action': str(registry.get('next_action', '')).strip(),
        'latest_artifact_ref': str(registry.get('latest_artifact_ref', '')).strip(),
        'latest_commit_sha': str(registry.get('latest_commit_sha', '')).strip(),
        'latest_result_role': str(registry.get('latest_result_role', '')).strip(),
        'latest_result_manifest': str(registry.get('latest_result_manifest', '')).strip(),
        'latest_result_value': str(registry.get('latest_result_value', '')).strip(),
        'latest_result_ts': str(registry.get('latest_result_ts', '')).strip(),
        'error_class': str(registry.get('error_class', '')).strip(),
        'error_details': str(registry.get('error_details', '')).strip(),
        'last_failure_ts': str(registry.get('last_failure_ts', '')).strip(),
        'last_failure_from_state': str(registry.get('last_failure_from_state', '')).strip(),
        'stall_count': int(registry.get('stall_count', 0) or 0),
        'is_terminal': bool(registry.get('is_terminal', False)),
        'terminal_reason': str(registry.get('terminal_reason', '')).strip(),
        'closed_by_system': bool(registry.get('closed_by_system', False)),
        'events': registry.get('events', []),
        'parent_task_id': str(registry.get('parent_task_id', '')).strip(),
        'superseded_by_task_id': str(registry.get('superseded_by_task_id', '')).strip(),
    }
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def apply_executor_success(task_id: str, registry: Dict[str, object], result_path: Path, result_data: Dict[str, object]) -> Dict[str, object]:
    event_type, new_state, next_role, next_action = resolve_success_transition('EXECUTOR', result_data)
    prev_event_id = str(registry.get('last_event_id', '')).strip()
    new_event_id = f'{event_type}::{task_id}::AUTO-0001'
    ts_utc = str(result_data.get('ts_utc', '')).strip()
    artifact_ref = str(result_data.get('produced_artifact_path', '')).strip()

    registry['current_state'] = new_state
    registry['last_event_id'] = new_event_id
    registry['last_parent_event_id'] = prev_event_id
    registry['last_event_type'] = event_type
    registry['last_actor_role'] = 'EXECUTOR'
    registry['last_event_ts'] = ts_utc
    registry['last_summary'] = str(result_data.get('summary', '')).strip()
    registry['next_role'] = next_role
    registry['next_action'] = next_action
    registry['latest_artifact_ref'] = artifact_ref
    registry['latest_commit_sha'] = 'LOCAL'
    registry['latest_result_role'] = 'EXECUTOR'
    registry['latest_result_manifest'] = str(result_path.relative_to(ROOT))
    registry['latest_result_value'] = str(result_data.get('result', '')).strip().upper()
    registry['latest_result_ts'] = ts_utc
    registry['is_terminal'] = new_state == 'COMPLETED' and next_role == 'SYSTEM' and next_action == 'CLOSE_TASK'

    registry['terminal_reason'] = 'COMPLETED/CLOSED_TASK' if registry['is_terminal'] else ''
    registry['error_class'] = ''
    registry['error_details'] = ''
    registry['last_failure_ts'] = ''
    registry['last_failure_from_state'] = ''

    append_event(registry)
    return registry


def apply_auditor_success(task_id: str, registry: Dict[str, object], result_path: Path, result_data: Dict[str, object]) -> Dict[str, object]:
    event_type, new_state, next_role, next_action = resolve_success_transition('AUDITOR', result_data)
    prev_event_id = str(registry.get('last_event_id', '')).strip()
    new_event_id = f'{event_type}::{task_id}::AUTO-0001'
    ts_utc = str(result_data.get('ts_utc', '')).strip()
    artifact_ref = str(result_data.get('produced_artifact_path', '')).strip()

    registry['current_state'] = new_state
    registry['last_event_id'] = new_event_id
    registry['last_parent_event_id'] = prev_event_id
    registry['last_event_type'] = event_type
    registry['last_actor_role'] = 'AUDITOR'
    registry['last_event_ts'] = ts_utc
    registry['last_summary'] = str(result_data.get('summary', '')).strip()
    registry['next_role'] = next_role
    registry['next_action'] = next_action
    registry['latest_artifact_ref'] = artifact_ref
    registry['latest_commit_sha'] = 'LOCAL'
    registry['latest_result_role'] = 'AUDITOR'
    registry['latest_result_manifest'] = str(result_path.relative_to(ROOT))
    registry['latest_result_value'] = str(result_data.get('result', '')).strip().upper()
    registry['latest_result_ts'] = ts_utc
    registry['is_terminal'] = new_state == 'COMPLETED' and next_role == 'SYSTEM' and next_action == 'CLOSE_TASK'

    registry['terminal_reason'] = 'COMPLETED/CLOSED_TASK' if registry['is_terminal'] else ''
    registry['last_decision'] = 'APPROVE'
    reviewed_ref = str(result_data.get('reviewed_ref', '')).strip()
    if reviewed_ref:
        registry['reviewed_ref'] = reviewed_ref
    registry['error_class'] = ''
    registry['error_details'] = ''
    registry['last_failure_ts'] = ''
    registry['last_failure_from_state'] = ''

    append_event(registry)
    return registry


def apply_failure_result(task_id: str, registry: Dict[str, object], result_path: Path, result_data: Dict[str, object], role: str, result_value: str) -> Dict[str, object]:
    prev_state = str(registry.get('current_state', '')).strip()
    prev_event_id = str(registry.get('last_event_id', '')).strip()
    ts_utc = str(result_data.get('ts_utc', '')).strip()
    role = str(role or '').strip().upper()
    result_value = str(result_value or '').strip().upper()

    event_type = 'RESULT_BLOCKED' if result_value == 'BLOCKED' else 'RESULT_FAILURE'
    new_event_id = f'{event_type}::{task_id}::AUTO-0001'

    summary = str(result_data.get('summary', '')).strip()
    explicit_error = str(result_data.get('error_details', '')).strip()
    message = str(result_data.get('message', '')).strip()
    error_details = explicit_error or summary or message or f'{role} returned {result_value}'
    explicit_error_class = str(result_data.get('error_class', '')).strip()
    error_class = explicit_error_class or (f'{role}_{result_value}' if role else result_value)
    artifact_ref = str(result_data.get('produced_artifact_path', '')).strip()

    registry['current_state'] = 'BLOCKED'
    registry['last_event_id'] = new_event_id
    registry['last_parent_event_id'] = prev_event_id
    registry['last_event_type'] = event_type
    registry['last_actor_role'] = role
    registry['last_event_ts'] = ts_utc
    registry['last_summary'] = error_details
    registry['next_role'] = 'AUDITOR'
    registry['next_action'] = 'REVIEW_STALL'
    registry['latest_artifact_ref'] = artifact_ref
    registry['latest_commit_sha'] = 'LOCAL'
    registry['latest_result_role'] = role
    registry['latest_result_manifest'] = str(result_path.relative_to(ROOT))
    registry['latest_result_value'] = result_value
    registry['latest_result_ts'] = ts_utc
    registry['is_terminal'] = False
    registry['terminal_reason'] = ''
    registry['error_class'] = error_class
    if error_class == 'STALL_CYCLES_EXHAUSTED':
        registry['stall_count'] = max(int(registry.get('stall_count', 0) or 0), 3)
    registry['error_details'] = error_details
    if error_class == 'STALL_CYCLES_EXHAUSTED':
        registry['stall_count'] = max(int(registry.get('stall_count', 0) or 0), 3)
    registry['last_failure_ts'] = ts_utc
    registry['last_failure_from_state'] = prev_state

    append_event(registry)
    return registry


def apply_supersession(current_task_id: str, registry: Dict[str, object]) -> List[str]:
    parent_task_id = str(registry.get('parent_task_id', '')).strip()
    if not parent_task_id:
        return []

    touched: List[str] = []
    siblings: List[Tuple[str, Path, Dict[str, object]]] = []

    for path in sorted(TASKS_DIR.glob('*.json')):
        if path.name == 'index.json':
            continue
        data = read_json(path)
        sibling_task_id = str(data.get('task_id', '')).strip()
        sibling_parent_task_id = str(data.get('parent_task_id', '')).strip()
        if not sibling_task_id or sibling_task_id == current_task_id:
            continue
        if sibling_parent_task_id != parent_task_id:
            continue
        siblings.append((sibling_task_id, path, data))

    for sibling_task_id, path, data in siblings:
        current_state = str(data.get('current_state', '')).strip()
        if current_state in {'SUPERSEDED', 'COMPLETED_CLOSED', 'COMPLETED_OPEN_TERMINAL'}:
            continue

        prev_event_ts = str(data.get('last_event_ts', '')).strip()
        data['current_state'] = 'SUPERSEDED'
        data['last_event_type'] = 'TASK_SUPERSEDED'
        data['last_actor_role'] = 'SYSTEM'
        data['last_summary'] = f'Task superseded by newer sibling task {current_task_id}'
        data['next_role'] = ''
        data['next_action'] = ''
        data['error_class'] = ''
        data['error_details'] = ''
        data['is_terminal'] = True
        data['closed_by_system'] = True
        data['terminal_reason'] = 'SUPERSEDED'
        data['superseded_by_task_id'] = current_task_id

        events = data.get('events', [])
        if not isinstance(events, list):
            events = []
        events.append({
            'event_id': f'TASK_SUPERSEDED::{sibling_task_id}',
            'event_type': 'TASK_SUPERSEDED',
            'actor_role': 'SYSTEM',
            'event_ts': prev_event_ts,
            'summary': data['last_summary'],
            'current_state': 'SUPERSEDED',
            'next_role': '',
            'next_action': '',
        })
        data['events'] = events

        write_registry(sibling_task_id, data)
        touched.append(str(path.relative_to(ROOT)))

    return touched


def main() -> int:
    try:
        result_path, result_data = choose_latest_result()

        role = str(result_data.get('role', '')).strip().upper()
        task_id = str(result_data.get('task_id', '')).strip()
        result_value = str(result_data.get('result', '')).strip().upper()

        if not task_id:
            raise ApplyResultError('Latest result manifest is missing task_id')

        registry = load_registry(task_id)

        if result_value == 'SUCCESS':
            if role == 'EXECUTOR':
                registry = apply_executor_success(task_id, registry, result_path, result_data)
            elif role == 'AUDITOR':
                registry = apply_auditor_success(task_id, registry, result_path, result_data)
            else:
                raise ApplyResultError(f'Unsupported role for apply_result_v1: {role!r}')
        elif result_value in {'FAILURE', 'BLOCKED'}:
            registry = apply_failure_result(task_id, registry, result_path, result_data, role, result_value)
        else:
            raise ApplyResultError(f'Unsupported result value for apply_result_v1: {result_value!r}')

        registry_path = write_registry(task_id, registry)
        superseded = apply_supersession(task_id, registry)
        index_doc = rebuild_index()

        report = {
            'system_apply_result_version': 'v2',
            'result': 'APPLIED',
            'applied_result_manifest': str(result_path.relative_to(ROOT)),
            'applied_result_value': result_value,
            'task_id': task_id,
            'role': role,
            'registry_path': str(registry_path.relative_to(ROOT)),
            'current_state': str(registry.get('current_state', '')).strip(),
            'last_event_type': str(registry.get('last_event_type', '')).strip(),
            'next_role': str(registry.get('next_role', '')).strip(),
            'next_action': str(registry.get('next_action', '')).strip(),
            'status_bucket': infer_status_bucket(registry),
            'index_summary': index_doc.get('summary', {}),
            'events_count': len(registry.get('events', [])) if isinstance(registry.get('events', []), list) else 0,
            'superseded_tasks': superseded,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    except Exception as e:
        print(
            json.dumps(
                {
                    'system_apply_result_version': 'v2',
                    'result': 'BLOCKED',
                    'error': str(e),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
