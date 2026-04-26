#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
TASK_ID = 'TASK-GHA-E2E-002'
TASK_PATH = ROOT / 'governance' / 'runtime' / 'tasks' / f'{TASK_ID}.json'
RESULT_PATH = ROOT / 'governance' / 'runtime' / 'results' / 'auditor_materialize_result.gha-e2e-002.json'
PROOF_PATH = ROOT / 'governance' / 'audit' / 'e2e-domain-verification-002-latest.json'


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def run_script(name: str) -> None:
    script = ROOT / 'governance' / 'scripts' / name
    proc = subprocess.run([sys.executable, str(script)], cwd=ROOT, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end='')
    if proc.stderr:
        print(proc.stderr, end='', file=sys.stderr)
    if proc.returncode != 0:
        raise SystemExit(f'{name} failed with rc={proc.returncode}')


def seed() -> None:
    write_json(TASK_PATH, {
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
        'error_class': '',
        'error_details': '',
        'last_failure_ts': '',
        'last_failure_from_state': '',
        'is_terminal': False,
        'closed_by_system': False,
        'events': [],
    })
    write_json(RESULT_PATH, {
        'result_manifest_version': 'v1',
        'task_id': TASK_ID,
        'role': 'AUDITOR',
        'result': 'SUCCESS',
        'ts_utc': '2026-04-26T00:00:01Z',
        'summary': 'Auditor approved TASK-GHA-E2E-002 via GitHub Actions domain verification',
        'reviewed_ref': f'governance/decisions/IMPLEMENTATION_COMPLETED-{TASK_ID}.json',
        'reviewed_commit_sha': 'LOCAL',
        'produced_artifact_type': 'verification_decision',
        'produced_artifact_path': f'governance/decisions/AUDIT-{TASK_ID}-AUTO-0001.json',
    })
    write_json(ROOT / 'governance' / 'decisions' / f'IMPLEMENTATION_COMPLETED-{TASK_ID}.json', {
        'artifact_type': 'implementation_result',
        'task_id': TASK_ID,
        'summary': 'implementation completed artifact for gha e2e 002',
    })
    write_json(ROOT / 'governance' / 'decisions' / f'AUDIT-{TASK_ID}-AUTO-0001.json', {
        'artifact_type': 'verification_decision',
        'task_id': TASK_ID,
        'summary': 'auditor verification decision for gha e2e 002',
    })


def prepare_completed_for_close() -> None:
    data = read_json(TASK_PATH)
    if str(data.get('current_state', '')).strip() != 'COMPLETED':
        raise SystemExit(f"close phase precheck failed: current_state={data.get('current_state')!r}")
    data['last_event_ts'] = '2000-01-01T00:00:00Z'
    write_json(TASK_PATH, data)


def verify() -> dict:
    data = read_json(TASK_PATH)
    events = data.get('events', [])
    if not isinstance(events, list):
        raise SystemExit('events is not a list')
    checks = {
        'current_state': str(data.get('current_state', '')).strip(),
        'last_event_type': str(data.get('last_event_type', '')).strip(),
        'next_role': str(data.get('next_role', '')).strip(),
        'next_action': str(data.get('next_action', '')).strip(),
        'latest_result_manifest': str(data.get('latest_result_manifest', '')).strip(),
        'events_count': len(events),
    }
    expected = {
        'current_state': 'COMPLETED_CLOSED',
        'last_event_type': 'SYSTEM_CLOSE_TIMEOUT',
        'next_role': '',
        'next_action': '',
    }
    for key, value in expected.items():
        if checks[key] != value:
            raise SystemExit(f"domain check failed: {key}={checks[key]!r}, expected {value!r}")
    if not checks['latest_result_manifest']:
        raise SystemExit('domain check failed: latest_result_manifest empty')
    if checks['events_count'] < 2:
        raise SystemExit(f"domain check failed: events_count={checks['events_count']} < 2")
    proof = {'bem': 'BEM-345', 'task_id': TASK_ID, 'result': 'SUCCESS', 'domain_verification': 'PASS', 'checks': checks}
    write_json(PROOF_PATH, proof)
    return proof


def main() -> int:
    seed()
    run_script('system_index_consistency_check_v1.py')
    run_script('system_entrypoint_v1.py')
    run_script('system_entrypoint_v1.py')
    prepare_completed_for_close()
    run_script('system_terminal_watchdog_v1.py')
    run_script('system_apply_result_guarded_v1.py')
    proof = verify()
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
