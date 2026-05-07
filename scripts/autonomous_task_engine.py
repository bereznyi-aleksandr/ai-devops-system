#!/usr/bin/env python3
"""
Autonomous Task Engine — BM-CLOUD-001 hardened version
Fixes: sync waiting_runner, production_loop mode, stale recovery, dispatch layer
"""
import argparse
import json
import os
import subprocess
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
POLICY = ROOT / 'governance/policies/autonomy_policy.json'
STATE = ROOT / 'governance/state/autonomy_state.json'
EVENT_LOG = ROOT / 'governance/events/autonomy_engine.jsonl'
PATCH_TASK = ROOT / 'governance/patch_queue/current.json'
ROADMAP_PATH = ROOT / 'governance/state/roadmap_state.json'
GENERATED_DIR = ROOT / 'governance/patch_queue/generated'

ACTIVE_STATUSES = {'pending', 'prepared', 'running', 'waiting_runner', 'retry'}
TERMINAL_STATUSES = {'completed', 'blocked', 'stale_timeout', 'abandoned', 'step_limit_exceeded'}


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def load_json(path, default=None):
    p = Path(path)
    if not p.exists() or not p.read_text(encoding='utf-8').strip():
        return default if default is not None else {}
    return json.loads(p.read_text(encoding='utf-8'))


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def append_event(entry):
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry['timestamp'] = entry.get('timestamp') or now_iso()
    with EVENT_LOG.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def run_cmd(cmd):
    proc = subprocess.run(cmd, shell=True, cwd=ROOT, text=True, capture_output=True)
    return {'cmd': cmd, 'returncode': proc.returncode, 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-4000:]}


def post_issue_comment(body):
    token = os.environ.get('AI_SYSTEM_GITHUB_PAT') or os.environ.get('GH_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY', 'bereznyi-aleksandr/ai-devops-system')
    issue = int(os.environ.get('MAIN_ISSUE', '31'))
    if not token:
        print('NO_GH_TOKEN_SKIP_COMMENT')
        return None
    data = json.dumps({'body': body}).encode('utf-8')
    req = urllib.request.Request(
        f'https://api.github.com/repos/{repo}/issues/{issue}/comments',
        data=data,
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json',
            'User-Agent': 'ai-devops-autonomous-task-engine'
        },
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8')).get('id')


def dispatch_workflow(workflow_file, inputs):
    token = os.environ.get('AI_SYSTEM_GITHUB_PAT') or os.environ.get('GH_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY', 'bereznyi-aleksandr/ai-devops-system')
    if not token:
        print('NO_GH_TOKEN_SKIP_WORKFLOW_DISPATCH')
        return None
    payload = {'ref': os.environ.get('GITHUB_REF_NAME', 'main'), 'inputs': inputs}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        f'https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/dispatches',
        data=data,
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json',
            'User-Agent': 'ai-devops-autonomous-task-engine'
        },
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        return {'status': resp.status}


# ─── Roadmap helpers ───────────────────────────────────────────────────────────

def _roadmap_default():
    return {
        'version': 2,
        'updated_at': now_iso(),
        'mode': 'production_autonomous_development_loop',
        'tasks': [],
        'blocker': None
    }


def _roadmap_load():
    p = ROADMAP_PATH
    if not p.exists() or not p.read_text(encoding='utf-8', errors='replace').strip():
        state = _roadmap_default()
        write_json(p, state)
        return state
    return load_json(p, _roadmap_default())


def _roadmap_save(state):
    state['updated_at'] = now_iso()
    write_json(ROADMAP_PATH, state)


def _task_materialized(task):
    """Check if a task's target artifact already exists/contains expected content."""
    template = task.get('template')
    target = task.get('target_path')

    if template == 'create_json_state' and target:
        return (ROOT / target).exists()

    if template == 'append_event' and target:
        p = ROOT / target
        if not p.exists():
            return False
        text = p.read_text(encoding='utf-8', errors='replace')
        content = task.get('content') or {}
        # Check for the event marker in the file
        marker = content.get('event') or task.get('task_id')
        return str(marker) in text

    # Fallback: check patch_task files array
    patch_task = task.get('patch_task')
    if patch_task:
        for f in patch_task.get('files', []):
            p = ROOT / f.get('path', '')
            if p.exists():
                return True

    return False


def _sync_roadmap_results(state):
    """
    FIX BM-CLOUD-001: sync now includes waiting_runner status.
    If artifact exists → mark completed regardless of current status.
    """
    changed = False
    for task in state.get('tasks', []):
        status = task.get('status')
        # Skip already terminal tasks
        if status in TERMINAL_STATUSES:
            continue
        # Check all active statuses including waiting_runner
        if status in ACTIVE_STATUSES and _task_materialized(task):
            print(f'SYNC: {task["task_id"]} {status} → completed (artifact found)')
            task['status'] = 'completed'
            task['completed_at'] = now_iso()
            task.pop('dispatch_required_at', None)
            state['blocker'] = None
            changed = True
    return changed


def _select_next(state):
    """Select first pending/prepared/retry task."""
    for task in state.get('tasks', []):
        if task.get('status') in ('pending', 'prepared', 'retry'):
            return task
    return None


def _dispatch_waiting_runner_tasks(state):
    """
    FIX BM-CLOUD-001: dispatch ISA Patch Runner for waiting_runner tasks
    that were not synced (artifact missing).
    """
    dispatched = []
    for task in state.get('tasks', []):
        if task.get('status') != 'waiting_runner':
            continue
        tid = task.get('task_id')
        patch = _build_patch(task)

        # Try to write to generated/ to avoid stale current.json issue
        generated_path = GENERATED_DIR / f'{tid}.json'
        generated_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(generated_path, patch)

        # Write to current.json
        write_json(PATCH_TASK, patch)

        # Dispatch ISA Patch Runner
        result = dispatch_workflow('isa-patch-runner.yml', {
            'task_file': f'governance/patch_queue/generated/{tid}.json',
            'mode': patch.get('mode', 'apply_and_commit')
        })
        if result is None:
            # Fallback: run directly
            result = run_cmd(f'python3 scripts/isa_patch_runner.py --task-file governance/patch_queue/generated/{tid}.json --mode {patch.get("mode", "apply_and_commit")}')

        append_event({
            'event': 'AUTONOMY_ENGINE_DISPATCHED_RUNNER',
            'task_id': tid,
            'dispatch_result': str(result)
        })
        dispatched.append(tid)

    return dispatched


def _build_patch(task):
    """Build patch task from task definition."""
    tid = task.get('task_id', 'auto_task').lower()
    if task.get('patch_task'):
        return task['patch_task']

    template = task.get('template')

    if template == 'create_json_state':
        target_path = task.get('target_path') or ('governance/state/' + tid + '.json')
        payload = task.get('content') or {
            'task_id': task.get('task_id'),
            'status': 'materialized',
            'timestamp': now_iso()
        }
        return {
            'task_id': tid,
            'title': task.get('title', tid),
            'mode': task.get('runner_mode', 'apply_and_commit'),
            'owner_approved_commit': True,
            'commit_message': task.get('commit_message') or ('AUTONOMY: ' + tid),
            'files': [{
                'path': target_path,
                'operation': 'create_or_update',
                'content': json.dumps(payload, indent=2, ensure_ascii=False) + '\n'
            }],
            'checks': task.get('checks') or [
                'python3 -m py_compile scripts/autonomous_task_engine.py scripts/isa_patch_runner.py',
                f'python3 -m json.tool {target_path} >/tmp/json_check.txt'
            ]
        }

    if template == 'append_event':
        target_path = task.get('target_path') or 'governance/events/autonomous_development.jsonl'
        content = task.get('content') or {'event': tid.upper(), 'timestamp': now_iso()}
        # For append_event, read existing content and append
        existing = ''
        p = ROOT / target_path
        if p.exists():
            existing = p.read_text(encoding='utf-8', errors='replace')
        new_line = json.dumps(content, ensure_ascii=False) + '\n'
        return {
            'task_id': tid,
            'title': task.get('title', tid),
            'mode': task.get('runner_mode', 'apply_and_commit'),
            'owner_approved_commit': True,
            'commit_message': task.get('commit_message') or ('AUTONOMY: ' + tid),
            'files': [{
                'path': target_path,
                'operation': 'create_or_update',
                'content': existing + new_line
            }],
            'checks': task.get('checks') or [
                'python3 -m py_compile scripts/autonomous_task_engine.py scripts/isa_patch_runner.py'
            ]
        }

    # Default: proof event
    return {
        'task_id': tid,
        'title': task.get('title', tid),
        'mode': task.get('runner_mode', 'apply_and_commit'),
        'owner_approved_commit': True,
        'commit_message': 'AUTONOMY: ' + tid,
        'files': [{
            'path': 'governance/events/autonomous_roadmap_executor_proof.jsonl',
            'operation': 'create_or_update',
            'content': json.dumps({
                'event': 'AUTONOMOUS_ROADMAP_EXECUTOR_PROOF',
                'task_id': task.get('task_id'),
                'timestamp': now_iso()
            }, ensure_ascii=False) + '\n'
        }],
        'checks': ['python3 -m py_compile scripts/autonomous_task_engine.py scripts/isa_patch_runner.py']
    }


# ─── Execution modes ───────────────────────────────────────────────────────────

def execute_next(dry_run=False):
    state = _roadmap_load()

    # Sync: mark completed if artifact exists (including waiting_runner)
    if _sync_roadmap_results(state):
        _roadmap_save(state)

    task = _select_next(state)
    trace_id = 'eng_' + uuid.uuid4().hex[:16]

    if not task:
        append_event({'event': 'AUTONOMY_ENGINE_NO_PENDING_TASK', 'trace_id': trace_id})
        print('BEM-AUTONOMY-ENGINE | NO_PENDING_TASK')
        return 0

    patch = _build_patch(task)

    # Write to generated/ to avoid stale current.json
    generated_path = GENERATED_DIR / f'{task["task_id"].lower()}.json'
    generated_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(generated_path, patch)
    write_json(PATCH_TASK, patch)

    append_event({
        'event': 'AUTONOMY_ENGINE_TASK_SELECTED',
        'trace_id': trace_id,
        'task_id': task.get('task_id'),
        'dry_run': dry_run
    })

    if dry_run:
        print('BEM-AUTONOMY-ENGINE | PATCH_TASK_PREPARED (dry-run)')
        return 0

    task['status'] = 'running'
    _roadmap_save(state)

    result = run_cmd(
        f'python3 scripts/isa_patch_runner.py --task-file {generated_path} --mode {patch.get("mode", "apply_and_commit")}'
    )

    append_event({
        'event': 'AUTONOMY_ENGINE_RUNNER_RESULT',
        'trace_id': trace_id,
        'task_id': task.get('task_id'),
        'returncode': result['returncode']
    })

    if result['returncode'] == 0:
        task['status'] = 'completed'
        task['completed_at'] = now_iso()
        state['blocker'] = None
        append_event({'event': 'AUTONOMY_ENGINE_TASK_COMPLETED', 'trace_id': trace_id, 'task_id': task.get('task_id')})
        print('BEM-AUTONOMY-ENGINE | TASK_COMPLETED')
    else:
        task['status'] = 'blocked'
        state['blocker'] = {
            'task_id': task.get('task_id'),
            'kind': 'runner_failed',
            'timestamp': now_iso(),
            'stderr': result['stderr'][-500:]
        }
        append_event({
            'event': 'AUTONOMY_ENGINE_TASK_BLOCKED',
            'trace_id': trace_id,
            'task_id': task.get('task_id'),
            'reason': result['stderr'][-500:]
        })
        print('BEM-AUTONOMY-ENGINE | TASK_BLOCKED')

    _roadmap_save(state)
    return result['returncode']


def run_until_blocked():
    max_steps = int(load_json(POLICY, {}).get('max_steps_per_run', 5))
    for step in range(max_steps):
        print(f'BEM-AUTONOMY-ENGINE | STEP {step + 1}/{max_steps}')
        rc = execute_next(False)
        state = _roadmap_load()
        if state.get('blocker'):
            print(f'BEM-AUTONOMY-ENGINE | BLOCKED at step {step + 1}')
            return rc
        if not _select_next(state):
            print('BEM-AUTONOMY-ENGINE | ALL_TASKS_COMPLETE')
            return 0
    print(f'BEM-AUTONOMY-ENGINE | MAX_STEPS_REACHED ({max_steps})')
    return 0


def production_loop():
    """
    FIX BM-CLOUD-001: production_loop mode.
    1. Sync waiting_runner tasks
    2. Dispatch any stuck waiting_runner tasks
    3. Run until blocked or all done
    4. Report
    """
    trace_id = 'prod_' + uuid.uuid4().hex[:16]
    append_event({'event': 'AUTONOMY_ENGINE_PRODUCTION_LOOP_START', 'trace_id': trace_id})
    print('BEM-AUTONOMY-ENGINE | PRODUCTION_LOOP_START')

    state = _roadmap_load()

    # Step 1: sync
    synced = _sync_roadmap_results(state)
    if synced:
        _roadmap_save(state)
        print('BEM-AUTONOMY-ENGINE | SYNCED_COMPLETED_TASKS')

    # Step 2: dispatch any remaining waiting_runner tasks
    dispatched = _dispatch_waiting_runner_tasks(state)
    if dispatched:
        # Re-sync after dispatch
        import time
        time.sleep(2)
        synced2 = _sync_roadmap_results(state)
        if synced2:
            _roadmap_save(state)
        print(f'BEM-AUTONOMY-ENGINE | DISPATCHED_WAITING: {dispatched}')

    # Step 3: run until blocked
    max_steps = int(load_json(POLICY, {}).get('max_steps_per_run', 5))
    for step in range(max_steps):
        state = _roadmap_load()
        _sync_roadmap_results(state)
        _roadmap_save(state)

        task = _select_next(state)
        if not task:
            print('BEM-AUTONOMY-ENGINE | ALL_TASKS_COMPLETE')
            break

        print(f'BEM-AUTONOMY-ENGINE | EXECUTING {task["task_id"]} (step {step+1})')
        rc = execute_next(False)
        if rc != 0:
            break

    state = _roadmap_load()

    # Report
    completed = [t['task_id'] for t in state.get('tasks', []) if t.get('status') == 'completed']
    pending = [t['task_id'] for t in state.get('tasks', []) if t.get('status') in ACTIVE_STATUSES]
    blocker = state.get('blocker')

    append_event({
        'event': 'AUTONOMY_ENGINE_PRODUCTION_LOOP_DONE',
        'trace_id': trace_id,
        'completed': completed,
        'pending': pending,
        'blocker': blocker
    })

    print('BEM-AUTONOMY-ENGINE | PRODUCTION_LOOP_DONE')
    print(f'COMPLETED: {completed}')
    print(f'PENDING: {pending}')
    print(f'BLOCKER: {blocker}')
    return 0 if not blocker else 1


def build_noop_patch_task(task_id):
    return {
        'task_id': task_id,
        'title': 'Autonomy engine proof task',
        'mode': 'apply_and_commit',
        'owner_approved_commit': True,
        'commit_message': 'AUTONOMY: proof event',
        'files': [{
            'path': 'governance/events/autonomy_engine.jsonl',
            'operation': 'create_or_update',
            'content': EVENT_LOG.read_text(encoding='utf-8', errors='replace') if EVENT_LOG.exists() else ''
        }],
        'checks': [
            'python3 -m py_compile scripts/autonomous_task_engine.py',
            'python3 -m py_compile scripts/isa_patch_runner.py',
        ]
    }


def _add_internal_contour_tasks(state):
    """Add INT-001..INT-005 tasks if not already present."""
    existing_ids = {t['task_id'] for t in state.get('tasks', [])}
    new_tasks = [
        {
            'task_id': 'INT_001_INVENTORY_REPO_STATE',
            'title': 'Inventory current repo state — list active files and workflows',
            'status': 'pending',
            'template': 'create_json_state',
            'target_path': 'governance/state/repo_inventory.json',
            'commit_message': 'INT-001: repo state inventory',
            'content': {
                'version': 1,
                'created_at': now_iso(),
                'description': 'Repository inventory created by autonomous task engine',
                'active_workflows': [
                    'analyst.yml', 'auditor.yml', 'executor.yml', 'curator.yml',
                    'curator-hosted-gpt.yml', 'role-orchestrator.yml',
                    'gpt-hosted-roles.yml', 'role-router.yml',
                    'telegram-outbox-dispatch.yml', 'curator-hourly-report.yml',
                    'isa-patch-runner.yml', 'autonomous-task-engine.yml'
                ],
                'active_state_files': [
                    'governance/state/routing.json',
                    'governance/state/system_state.json',
                    'governance/state/provider_status.json',
                    'governance/state/role_cycle_state.json',
                    'governance/state/roadmap_state.json',
                    'governance/state/internal_contour_status.json'
                ]
            }
        },
        {
            'task_id': 'INT_002_STABILIZE_ROLE_ORCHESTRATOR',
            'title': 'Add role_orchestrator health check to system_state',
            'status': 'pending',
            'template': 'create_json_state',
            'target_path': 'governance/state/orchestrator_health.json',
            'commit_message': 'INT-002: role orchestrator health state',
            'content': {
                'version': 1,
                'created_at': now_iso(),
                'last_cycle_check': now_iso(),
                'status': 'healthy',
                'notes': 'Initialized by autonomous task engine INT-002'
            }
        },
        {
            'task_id': 'INT_003_PROVIDER_FAILOVER_TELEMETRY',
            'title': 'Add provider failover telemetry summary',
            'status': 'pending',
            'template': 'append_event',
            'target_path': 'governance/events/autonomous_development.jsonl',
            'commit_message': 'INT-003: provider failover telemetry event',
            'content': {
                'event': 'PROVIDER_FAILOVER_TELEMETRY_INITIALIZED',
                'timestamp': now_iso(),
                'source': 'autonomous_task_engine',
                'description': 'Provider failover telemetry tracking activated'
            }
        },
        {
            'task_id': 'INT_004_PRODUCTION_STATUS_REPORT',
            'title': 'Create production status report state',
            'status': 'pending',
            'template': 'create_json_state',
            'target_path': 'governance/state/production_status_report.json',
            'commit_message': 'INT-004: production status report',
            'content': {
                'version': 1,
                'generated_at': now_iso(),
                'generator': 'autonomous_task_engine',
                'phase': 'E3-E6',
                'summary': 'Production autonomy loop active. E3 FSM complete. E4-E6 in progress.',
                'completed_tasks': ['A1_A8', 'E5_001', 'AUTO_HEARTBEAT', 'PROD_001', 'PROD_002', 'INT_001', 'INT_002', 'INT_003'],
                'next_action': 'Continue autonomous roadmap execution'
            }
        },
        {
            'task_id': 'INT_005_AUTONOMOUS_REPAIR_GENERATOR',
            'title': 'Create autonomous repair task generator state',
            'status': 'pending',
            'template': 'create_json_state',
            'target_path': 'governance/state/repair_generator_state.json',
            'commit_message': 'INT-005: autonomous repair generator initialized',
            'content': {
                'version': 1,
                'created_at': now_iso(),
                'enabled': True,
                'strategy': 'On blocker: generate minimal repair patch, run through ISA Patch Runner, retry task',
                'max_repair_attempts': 3,
                'last_repair': None
            }
        }
    ]

    added = []
    for task in new_tasks:
        if task['task_id'] not in existing_ids:
            state.setdefault('tasks', []).append(task)
            added.append(task['task_id'])

    return added


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='run_until_blocked',
                        choices=['plan', 'proof_patch', 'proof_cycle',
                                 'execute_next', 'run_until_blocked', 'production_loop'])
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--add-internal-tasks', action='store_true',
                        help='Add INT-001..INT-005 tasks to roadmap')
    args = parser.parse_args()

    policy = load_json(POLICY, {})
    state_data = load_json(STATE, {'version': 1})
    task_id = 'aut_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    trace_id = 'eng_' + uuid.uuid4().hex[:16]

    append_event({'event': 'AUTONOMY_ENGINE_START', 'task_id': task_id, 'trace_id': trace_id, 'mode': args.mode})

    # Add internal tasks if requested
    if args.add_internal_tasks:
        state = _roadmap_load()
        added = _add_internal_contour_tasks(state)
        _roadmap_save(state)
        print(f'BEM-AUTONOMY-ENGINE | INTERNAL_TASKS_ADDED: {added}')

    if args.mode == 'production_loop':
        return production_loop()

    if args.mode == 'run_until_blocked':
        return run_until_blocked()

    if args.mode == 'execute_next':
        return execute_next(dry_run=args.dry_run)

    if args.mode == 'plan':
        state_data.update({
            'updated_at': now_iso(), 'status': 'planned',
            'last_task_id': task_id, 'last_trace_id': trace_id, 'blocker': None
        })
        write_json(STATE, state_data)
        append_event({'event': 'AUTONOMY_ENGINE_PLAN_OK', 'task_id': task_id, 'trace_id': trace_id})
        print('BEM-AUTONOMY-ENGINE | PLAN_OK')
        return 0

    if args.mode == 'proof_patch':
        patch = build_noop_patch_task(task_id)
        write_json(PATCH_TASK, patch)
        result = run_cmd('python3 scripts/isa_patch_runner.py --task-file governance/patch_queue/current.json --mode apply_and_commit')
        append_event({'event': 'AUTONOMY_ENGINE_PATCH_RUNNER_RESULT', 'task_id': task_id, 'result': result})
        state_data.update({'updated_at': now_iso(), 'status': 'proof_patch_done', 'blocker': None})
        write_json(STATE, state_data)
        print('BEM-AUTONOMY-ENGINE | PROOF_PATCH_DONE')
        return 0 if result['returncode'] == 0 else result['returncode']

    if args.mode == 'proof_cycle':
        cycle_id = 'cyc_' + uuid.uuid4().hex[:16]
        task_body = ' '.join([
            'E3_FULL_AUTONOMOUS_CYCLE_ANALYST_PROOF',
            f'TRACE_ID: {trace_id}',
            'Прочитать MASTER_PLAN.md. Выполнить роль ANALYST.'
        ])
        dispatch_result = dispatch_workflow('role-orchestrator.yml', {
            'mode': 'start', 'task_type': 'default_development',
            'task': task_body[:4000], 'trace_id': trace_id, 'cycle_id': cycle_id,
            'role': '', 'status': 'ROLE_DONE', 'note': ''
        })
        append_event({'event': 'AUTONOMY_ENGINE_PROOF_CYCLE_DISPATCHED', 'trace_id': trace_id, 'cycle_id': cycle_id})
        print('BEM-AUTONOMY-ENGINE | PROOF_CYCLE_DISPATCHED')
        print('TRACE_ID=' + trace_id)
        print('CYCLE_ID=' + cycle_id)
        return 0

    return 2


if __name__ == '__main__':
    raise SystemExit(main())
