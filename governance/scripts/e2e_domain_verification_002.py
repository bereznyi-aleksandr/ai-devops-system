#!/usr/bin/env python3
# BEM-370 force autonomy-entrypoint retrigger after ROLE LAUNCHER patch
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
TASK_ID = 'TASK-GHA-E2E-002'
TASK = ROOT / 'governance/runtime/tasks' / f'{TASK_ID}.json'
RESULTS = ROOT / 'governance/runtime/results'
AUDITOR_RESULT = RESULTS / 'auditor_materialize_result.gha-e2e-002.json'
SYSTEM_RESULT = RESULTS / f'system_close_result_{TASK_ID}.json'
PROOF = ROOT / 'governance/audit/e2e-domain-verification-002-latest.json'


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def run(name: str) -> None:
    proc = subprocess.run([sys.executable, str(ROOT / 'governance/scripts' / name)], cwd=ROOT, text=True, capture_output=True)
    print(proc.stdout, end='')
    print(proc.stderr, end='', file=sys.stderr)
    if proc.returncode != 0:
        raise SystemExit(f'{name} failed rc={proc.returncode}')


def seed() -> None:
    write_json(TASK, {
        'task_id': TASK_ID,
        'current_state': 'REVIEW_PENDING',
        'last_event_id': f'IMPLEMENTATION_COMPLETED:{TASK_ID}',
        'last_parent_event_id': '',
        'last_event_type': 'IMPLEMENTATION_COMPLETED',
        'last_actor_role': 'EXECUTOR',
        'last_event_ts': '2026-04-26T00:00:00Z',
        'last_summary': 'seed for gha domain e2e 002',
        'next_role': 'AUDITOR',
        'next_action': 'REVIEW_CODE',
        'latest_result_value': '',
        'latest_result_manifest': '',
        'is_terminal': False,
        'closed_by_system': False,
        'events': [],
    })
    write_json(AUDITOR_RESULT, {
        'result_manifest_version': 'v1',
        'task_id': TASK_ID,
        'role': 'AUDITOR',
        'result': 'SUCCESS',
        'ts_utc': '2026-04-26T00:00:01Z',
        'summary': 'Auditor approved TASK-GHA-E2E-002 via GHA',
        'reviewed_ref': f'governance/decisions/IMPLEMENTATION_COMPLETED-{TASK_ID}.json',
        'produced_artifact_path': f'governance/decisions/AUDIT-{TASK_ID}-AUTO-0001.json',
    })


def system_close() -> None:
    data = read_json(TASK)
    state = str(data.get('current_state', '')).strip()
    role = str(data.get('next_role', '')).strip()
    action = str(data.get('next_action', '')).strip()
    if state not in {'COMPLETED', 'COMPLETED_OPEN_TERMINAL'} or role != 'SYSTEM' or action != 'CLOSE_TASK':
        raise SystemExit(f'close precheck failed: state={state!r} role={role!r} action={action!r}')
    write_json(SYSTEM_RESULT, {
        'result_manifest_version': 'v1',
        'task_id': TASK_ID,
        'role': 'SYSTEM',
        'result': 'SUCCESS',
        'ts_utc': '2026-04-26T00:00:02Z',
        'summary': 'System closed TASK-GHA-E2E-002 during GHA domain verification',
        'event_type': 'SYSTEM_CLOSE_TIMEOUT',
    })


def verify() -> dict:
    data = read_json(TASK)
    events = data.get('events', [])
    checks = {
        'current_state': str(data.get('current_state', '')).strip(),
        'last_event_type': str(data.get('last_event_type', '')).strip(),
        'next_role': str(data.get('next_role', '')).strip(),
        'next_action': str(data.get('next_action', '')).strip(),
        'latest_result_manifest': str(data.get('latest_result_manifest', '')).strip(),
        'events_count': len(events) if isinstance(events, list) else -1,
    }
    expected_manifest = str(SYSTEM_RESULT.relative_to(ROOT))
    assert checks['current_state'] == 'COMPLETED_CLOSED', checks
    assert checks['last_event_type'] == 'SYSTEM_CLOSE_TIMEOUT', checks
    assert checks['next_role'] == '', checks
    assert checks['next_action'] == '', checks
    assert checks['latest_result_manifest'] == expected_manifest, checks
    assert checks['events_count'] >= 3, checks
    proof = {'bem': 'BEM-349', 'task_id': TASK_ID, 'result': 'SUCCESS', 'domain_verification': 'PASS', 'checks': checks}
    write_json(PROOF, proof)
    return proof


def main() -> int:
    seed()
    run('system_index_consistency_check_v1.py')
    run('system_entrypoint_v1.py')
    run('system_entrypoint_v1.py')
    system_close()
    run('system_apply_result_guarded_v1.py')
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
