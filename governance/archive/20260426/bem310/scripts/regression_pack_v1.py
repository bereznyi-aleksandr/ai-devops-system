#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
GOV = ROOT / 'governance'
RUNTIME = GOV / 'runtime'
TASKS = RUNTIME / 'tasks'
RESULTS = RUNTIME / 'results'
NOTIFS = RUNTIME / 'notifications'
DECISIONS = GOV / 'decisions'
SCRIPTS = GOV / 'scripts'

APPLY = SCRIPTS / 'system_apply_result_v1.py'
STALL = SCRIPTS / 'system_stalled_task_watchdog_v1.py'
SUPER = SCRIPTS / 'system_supersession_v1.py'
ROLE_NOTIFY = SCRIPTS / 'system_role_notify_v1.py'
MARK_PROCESSED = SCRIPTS / 'system_notify_mark_processed_v1.py'

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

def run(cmd, cwd=ROOT):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))

def infer_status_bucket(data: dict) -> str:
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
    if current_state == 'SUPERSEDED':
        return 'SUPERSEDED'
    return 'UNKNOWN'

def rebuild_index():
    TASKS.mkdir(parents=True, exist_ok=True)
    index_path = TASKS / 'index.json'

    latest = {}
    for path in sorted(TASKS.glob('*.json')):
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
            'status_bucket': infer_status_bucket(data),
        }

        prev = latest.get(task_id)
        key = (item['last_event_ts'], item['task_id'])
        if prev is None or key >= (prev['last_event_ts'], prev['task_id']):
            latest[task_id] = item

    items = sorted(
        latest.values(),
        key=lambda x: (x['last_event_ts'], x['task_id']),
        reverse=True,
    )

    summary = {}
    for item in items:
        bucket = item['status_bucket']
        summary[bucket] = summary.get(bucket, 0) + 1
    summary['TOTAL'] = len(items)

    index_doc = {
        'system_task_index_version': 'v1',
        'result': 'SUCCESS',
        'task_dir': str(TASKS.relative_to(ROOT)),
        'index_path': str(index_path.relative_to(ROOT)),
        'summary': summary,
        'items': items,
    }
    write_json(index_path, index_doc)

def clean_runtime():
    if RUNTIME.exists():
        shutil.rmtree(RUNTIME)
    if DECISIONS.exists():
        shutil.rmtree(DECISIONS)
    TASKS.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    NOTIFS.mkdir(parents=True, exist_ok=True)
    DECISIONS.mkdir(parents=True, exist_ok=True)

def seed_task(task_id: str, **overrides):
    data = {
        'task_id': task_id,
        'current_state': 'IMPLEMENTATION_PENDING',
        'last_event_id': f'PLAN_APPROVED:{task_id}',
        'last_parent_event_id': '',
        'last_event_type': 'PLAN_APPROVED',
        'last_actor_role': 'AUDITOR',
        'last_event_ts': '2026-04-19T10:00:00Z',
        'last_summary': 'seed',
        'next_role': 'EXECUTOR',
        'next_action': 'IMPLEMENT_TASK',
        'latest_result_value': '',
        'latest_result_manifest': '',
        'error_class': '',
        'error_details': '',
        'last_failure_ts': '',
        'last_failure_from_state': '',
        'is_terminal': False,
        'closed_by_system': False,
        'stall_count': 0,
        'events': [],
    }
    data.update(overrides)
    write_json(TASKS / f'{task_id}.json', data)

def test_failure_path_local():
    clean_runtime()
    task_id = 'TASK-FAIL-LOCAL-001'
    seed_task(task_id)
    rebuild_index()

    write_json(RESULTS / 'executor_failure_result.local.json', {
        'result_manifest_version': 'v1',
        'task_id': task_id,
        'role': 'EXECUTOR',
        'result': 'BLOCKED',
        'ts_utc': utc_now(),
        'summary': 'executor blocked task',
        'error_class': 'EXECUTOR_BLOCKED',
        'error_details': 'local failure path test',
        'produced_artifact_path': '',
    })

    p = run([sys.executable, str(APPLY)])
    reg = read_json(TASKS / f'{task_id}.json')
    ok = (
        p.returncode == 0
        and reg.get('current_state') == 'BLOCKED'
        and reg.get('next_role') == 'AUDITOR'
        and reg.get('next_action') == 'REVIEW_STALL'
        and reg.get('latest_result_value') == 'BLOCKED'
        and len(reg.get('events', [])) >= 1
    )
    return {
        'test': 'R-05_FAILURE_PATH_LOCAL',
        'ok': ok,
        'details': {
            'returncode': p.returncode,
            'current_state': reg.get('current_state'),
            'next_role': reg.get('next_role'),
            'next_action': reg.get('next_action'),
            'latest_result_value': reg.get('latest_result_value'),
            'events_count': len(reg.get('events', [])),
            'stdout_tail': p.stdout.strip().splitlines()[-20:],
            'stderr_tail': p.stderr.strip().splitlines()[-20:],
        },
    }

def test_supersession_local():
    clean_runtime()
    parent = 'PARENT-001'
    seed_task('TASK-SUPER-001', parent_task_id=parent, last_event_ts='2026-04-19T10:00:00Z')
    seed_task('TASK-SUPER-002', parent_task_id=parent, last_event_ts='2026-04-19T10:00:01Z')
    rebuild_index()

    p = run([sys.executable, str(SUPER), 'TASK-SUPER-002'])
    reg = read_json(TASKS / 'TASK-SUPER-001.json')
    ok = (
        p.returncode == 0
        and reg.get('current_state') == 'SUPERSEDED'
        and reg.get('superseded_by_task_id') == 'TASK-SUPER-002'
        and len(reg.get('events', [])) >= 1
    )
    return {
        'test': 'R-06_SUPERSESSION_LOCAL',
        'ok': ok,
        'details': {
            'returncode': p.returncode,
            'current_state': reg.get('current_state'),
            'superseded_by_task_id': reg.get('superseded_by_task_id'),
            'events_count': len(reg.get('events', [])),
            'stdout_tail': p.stdout.strip().splitlines()[-20:],
            'stderr_tail': p.stderr.strip().splitlines()[-20:],
        },
    }

def test_tie_break_equal_ts():
    clean_runtime()
    ts = '2026-04-19T10:00:00Z'
    parent = 'PARENT-TIE-001'
    seed_task('TASK-TIE-001', parent_task_id=parent, last_event_ts=ts)
    seed_task('TASK-TIE-002', parent_task_id=parent, last_event_ts=ts)
    rebuild_index()

    idx = read_json(TASKS / 'index.json')
    items = idx.get('items', [])
    top = items[0]['task_id'] if items else ''
    ok = top == 'TASK-TIE-002'
    return {
        'test': 'R-07_TIE_BREAK_EQUAL_TS',
        'ok': ok,
        'details': {
            'top_task_id': top,
            'items_head': items[:5],
        },
    }

def test_max_stall_cycles_exhaustion():
    clean_runtime()
    task_id = 'TASK-STALL-EXHAUST-001'
    seed_task(
        task_id,
        current_state='IMPLEMENTATION_PENDING',
        next_role='EXECUTOR',
        next_action='IMPLEMENT_TASK',
        last_event_ts='2026-04-17T00:00:00Z',
        stall_count=2,
    )
    rebuild_index()

    p = run([sys.executable, str(STALL)])
    reg = read_json(TASKS / f'{task_id}.json')
    ok = (
        p.returncode == 0
        and reg.get('current_state') == 'BLOCKED'
        and reg.get('error_class') == 'STALL_CYCLES_EXHAUSTED'
        and int(reg.get('stall_count', 0)) >= 3
    )
    return {
        'test': 'R-08_MAX_STALL_CYCLES_EXHAUSTION',
        'ok': ok,
        'details': {
            'returncode': p.returncode,
            'current_state': reg.get('current_state'),
            'error_class': reg.get('error_class'),
            'stall_count': reg.get('stall_count'),
            'stdout_tail': p.stdout.strip().splitlines()[-20:],
            'stderr_tail': p.stderr.strip().splitlines()[-20:],
        },
    }

def test_notify_processed_roundtrip():
    clean_runtime()
    task_id = 'TASK-NOTIFY-ROUNDTRIP-001'
    seed_task(task_id)
    rebuild_index()

    p1 = run([sys.executable, str(ROLE_NOTIFY)])
    j1 = json.loads(p1.stdout)
    active = ROOT / j1['notification_path']

    p2 = run([sys.executable, str(ROLE_NOTIFY)])
    j2 = json.loads(p2.stdout)

    p3 = run([sys.executable, str(MARK_PROCESSED), str(active), 'EXECUTOR'])
    j3 = json.loads(p3.stdout)

    processed = ROOT / j3['processed_notification_path']
    active_exists_immediately_after_mark = active.exists()

    p4 = run([sys.executable, str(ROLE_NOTIFY)])
    j4 = json.loads(p4.stdout)

    ok = (
        p1.returncode == 0
        and p2.returncode == 0
        and p3.returncode == 0
        and p4.returncode == 0
        and j1.get('notification_created') is True
        and j2.get('notification_created') is False
        and j2.get('reason') == 'active_notify_exists'
        and processed.exists()
        and active_exists_immediately_after_mark is False
        and j4.get('notification_created') is True
    )
    return {
        'test': 'R-09_NOTIFY_PROCESSED_ROUNDTRIP',
        'ok': ok,
        'details': {
            'first_created': j1.get('notification_created'),
            'second_created': j2.get('notification_created'),
            'second_reason': j2.get('reason'),
            'processed_exists': processed.exists(),
            'active_exists_immediately_after_mark': active_exists_immediately_after_mark,
            'third_created': j4.get('notification_created'),
        },
    }

def main():
    backup_dir = Path(tempfile.mkdtemp(prefix='regpack_v1_'))
    runtime_backup = backup_dir / 'runtime_backup'
    decisions_backup = backup_dir / 'decisions_backup'
    try:
        if RUNTIME.exists():
            shutil.copytree(RUNTIME, runtime_backup)
        if DECISIONS.exists():
            shutil.copytree(DECISIONS, decisions_backup)

        tests = [
            test_failure_path_local,
            test_supersession_local,
            test_tie_break_equal_ts,
            test_max_stall_cycles_exhaustion,
            test_notify_processed_roundtrip,
        ]

        results = []
        for fn in tests:
            try:
                results.append(fn())
            except Exception as e:
                results.append({'test': fn.__name__.upper(), 'ok': False, 'details': {'error': str(e)}})

        passed = sum(1 for x in results if x['ok'])
        print(json.dumps({
            'suite': 'ABP-025 local regression pack',
            'passed': passed,
            'total': len(results),
            'ok': passed == len(results),
            'tests': results,
        }, ensure_ascii=False, indent=2))
        return 0 if passed == len(results) else 1
    finally:
        if RUNTIME.exists():
            shutil.rmtree(RUNTIME)
        if runtime_backup.exists():
            shutil.copytree(runtime_backup, RUNTIME)
        if DECISIONS.exists():
            shutil.rmtree(DECISIONS)
        if decisions_backup.exists():
            shutil.copytree(decisions_backup, DECISIONS)
        shutil.rmtree(backup_dir, ignore_errors=True)

if __name__ == '__main__':
    raise SystemExit(main())
