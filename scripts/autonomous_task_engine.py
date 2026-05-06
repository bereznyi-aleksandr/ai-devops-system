#!/usr/bin/env python3
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


def run(cmd):
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


def build_e3_full_cycle_comment(trace_id):
    return '\n'.join([
        '@curator',
        '',
        'TASK: E3_FULL_AUTONOMOUS_CYCLE_ANALYST_PROOF',
        'ROLE: analyst',
        '',
        'CYCLE: E3_FULL',
        f'TRACE_ID: {trace_id}',
        '',
        'Прочитать governance/MASTER_PLAN.md и активный state layer.',
        'Выполнить роль ANALYST в первом полном автономном цикле.',
        'Ничего не менять. Только read/report.',
        'В отчёте подтвердить TRACE_ID и предложить следующий шаг для auditor.'
    ])


def build_noop_patch_task(task_id):
    return {
        'task_id': task_id,
        'title': 'Autonomy engine low-risk proof task',
        'mode': 'apply_and_commit',
        'owner_approved_commit': True,
        'commit_message': 'C-08: autonomy engine proof event',
        'files': [
            {
                'path': 'governance/events/autonomy_engine.jsonl',
                'operation': 'create_or_update',
                'content': EVENT_LOG.read_text(encoding='utf-8', errors='replace') if EVENT_LOG.exists() else ''
            }
        ],
        'checks': [
            'python3 -m py_compile scripts/autonomous_task_engine.py',
            'python3 -m py_compile scripts/isa_patch_runner.py',
            'python3 -m py_compile scripts/curator_entrypoint.py',
            'python3 -m py_compile scripts/curator_router.py'
        ]
    }


def _roadmap_path():
    return ROOT / 'governance/state/roadmap_state.json'

def _roadmap_default():
    return {'version': 1, 'updated_at': now_iso(), 'tasks': [
        {'task_id': 'A1_A8_AUTONOMOUS_ROADMAP_EXECUTOR', 'status': 'completed'},
        {'task_id': 'E5_001_PROVIDER_FAILOVER', 'status': 'completed'},
        {'task_id': 'AUTO_HEARTBEAT_PROOF', 'status': 'pending', 'runner_mode': 'apply_and_commit'}
    ], 'blocker': None}

def _roadmap_load():
    p = _roadmap_path()
    if not p.exists() or not p.read_text(encoding='utf-8', errors='replace').strip():
        state = _roadmap_default()
        write_json(p, state)
        return state
    return load_json(p, _roadmap_default())

def _roadmap_save(state):
    state['updated_at'] = now_iso()
    write_json(_roadmap_path(), state)

def _proof_event_exists(task_id):
    path = ROOT / 'governance/events/autonomous_roadmap_executor_proof.jsonl'
    if not path.exists():
        return False
    return str(task_id) in path.read_text(encoding='utf-8', errors='replace')

def _sync_roadmap_results(state):
    changed = False
    for task in state.get('tasks', []):
        if task.get('task_id') == 'AUTO_HEARTBEAT_PROOF' and task.get('status') in ('pending', 'prepared', 'running', 'waiting_runner', 'retry'):
            if _proof_event_exists(task.get('task_id')):
                task['status'] = 'completed'
                task['completed_at'] = now_iso()
                state['blocker'] = None
                changed = True
    return changed

def _select_next(state):
    for task in state.get('tasks', []):
        if task.get('status') in ('pending', 'prepared', 'retry'):
            return task
    return None

def _build_patch(task):
    tid = task.get('task_id', 'auto_task').lower()
    if task.get('patch_task'):
        return task['patch_task']
    template = task.get('template')
    if template == 'create_json_state':
        target_path = task.get('target_path') or ('governance/state/' + tid + '.json')
        payload = task.get('content') or {'task_id': task.get('task_id'), 'status': 'materialized', 'timestamp': now_iso()}
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
                'python3 -m json.tool ' + target_path + ' >/tmp/autonomy_template_json_check.txt'
            ]
        }
    if template == 'append_event':
        target_path = task.get('target_path') or 'governance/events/autonomous_development.jsonl'
        payload = task.get('content') or {'event': tid.upper(), 'timestamp': now_iso()}
        return {
            'task_id': tid,
            'title': task.get('title', tid),
            'mode': task.get('runner_mode', 'apply_and_commit'),
            'owner_approved_commit': True,
            'commit_message': task.get('commit_message') or ('AUTONOMY: ' + tid),
            'files': [{
                'path': target_path,
                'operation': 'create_or_update',
                'content': json.dumps(payload, ensure_ascii=False) + '\n'
            }],
            'checks': task.get('checks') or ['python3 -m py_compile scripts/autonomous_task_engine.py scripts/isa_patch_runner.py']
        }
    return {
        'task_id': tid,
        'title': task.get('title', tid),
        'mode': task.get('runner_mode', 'apply_and_commit'),
        'owner_approved_commit': True,
        'commit_message': 'AUTONOMY: ' + tid,
        'files': [{
            'path': 'governance/events/autonomous_roadmap_executor_proof.jsonl',
            'operation': 'create_or_update',
            'content': json.dumps({'event': 'AUTONOMOUS_ROADMAP_EXECUTOR_PROOF', 'task_id': task.get('task_id'), 'timestamp': now_iso()}, ensure_ascii=False) + '\n'
        }],
        'checks': ['python3 -m py_compile scripts/autonomous_task_engine.py scripts/isa_patch_runner.py']
    }

def execute_next(dry_run=False):
    state = _roadmap_load()
    if _sync_roadmap_results(state):
        _roadmap_save(state)
    task = _select_next(state)
    trace_id = 'eng_' + uuid.uuid4().hex[:16]
    if not task:
        append_event({'event': 'AUTONOMY_ENGINE_NO_PENDING_TASK', 'trace_id': trace_id})
        print('BEM-AUTONOMY-ENGINE | NO_PENDING_TASK')
        return 0
    patch = _build_patch(task)
    write_json(PATCH_TASK, patch)
    append_event({'event': 'AUTONOMY_ENGINE_TASK_SELECTED', 'trace_id': trace_id, 'task_id': task.get('task_id'), 'dry_run': dry_run})
    if dry_run:
        print('BEM-AUTONOMY-ENGINE | PATCH_TASK_PREPARED')
        return 0
    if os.environ.get('ISA_PATCH_RUNNER_ACTIVE') == '1':
        task['status'] = 'waiting_runner'
        task['dispatch_required_at'] = now_iso()
        _roadmap_save(state)
        append_event({'event': 'AUTONOMY_ENGINE_DISPATCH_REQUIRED', 'trace_id': trace_id, 'task_id': task.get('task_id')})
        print('BEM-AUTONOMY-ENGINE | DISPATCH_REQUIRED')
        return 0
    task['status'] = 'running'
    _roadmap_save(state)
    result = run('python3 scripts/isa_patch_runner.py --task-file governance/patch_queue/current.json --mode ' + patch.get('mode', 'apply_and_commit'))
    append_event({'event': 'AUTONOMY_ENGINE_RUNNER_RESULT', 'trace_id': trace_id, 'task_id': task.get('task_id'), 'result': result})
    task['status'] = 'completed' if result['returncode'] == 0 else 'blocked'
    if result['returncode'] != 0:
        state['blocker'] = {'task_id': task.get('task_id'), 'kind': 'runner_failed', 'timestamp': now_iso()}
    else:
        state['blocker'] = None
    _roadmap_save(state)
    print('BEM-AUTONOMY-ENGINE | ' + ('TASK_COMPLETED' if result['returncode'] == 0 else 'TASK_BLOCKED'))
    return result['returncode']

def run_until_blocked():
    max_steps = int(load_json(POLICY, {}).get('max_steps_per_run', 3))
    for _ in range(max_steps):
        rc = execute_next(False)
        if rc != 0 or not _select_next(_roadmap_load()):
            return rc
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', default='plan', choices=['plan', 'proof_patch', 'proof_cycle', 'execute_next', 'run_until_blocked'])
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    policy = load_json(POLICY, {})
    state = load_json(STATE, {'version': 1})
    task_id = 'aut_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    trace_id = 'eng_' + uuid.uuid4().hex[:16]

    append_event({'event': 'AUTONOMY_ENGINE_START', 'task_id': task_id, 'trace_id': trace_id, 'mode': args.mode})

    if args.mode == 'plan':
        state.update({'updated_at': now_iso(), 'status': 'planned', 'current_step': 'C-08', 'last_task_id': task_id, 'last_trace_id': trace_id, 'blocker': None})
        write_json(STATE, state)
        append_event({'event': 'AUTONOMY_ENGINE_PLAN_OK', 'task_id': task_id, 'trace_id': trace_id})
        print('BEM-AUTONOMY-ENGINE | PLAN_OK')
        print('TASK_ID=' + task_id)
        print('TRACE_ID=' + trace_id)
        return 0

    if args.mode == 'proof_patch':
        append_event({'event': 'AUTONOMY_ENGINE_PROOF_PATCH_PREPARED', 'task_id': task_id, 'trace_id': trace_id})
        patch = build_noop_patch_task(task_id)
        write_json(PATCH_TASK, patch)
        result = run('python3 scripts/isa_patch_runner.py --task-file governance/patch_queue/current.json --mode apply_and_commit')
        append_event({'event': 'AUTONOMY_ENGINE_PATCH_RUNNER_RESULT', 'task_id': task_id, 'trace_id': trace_id, 'result': result})
        state.update({'updated_at': now_iso(), 'status': 'proof_patch_done', 'current_step': 'C-08', 'last_task_id': task_id, 'last_trace_id': trace_id, 'blocker': None})
        write_json(STATE, state)
        print('BEM-AUTONOMY-ENGINE | PROOF_PATCH_DONE')
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['returncode'] == 0 else result['returncode']

    if args.mode == 'execute_next':
        return execute_next(dry_run=args.dry_run)

    if args.mode == 'run_until_blocked':
        return run_until_blocked()

    if args.mode == 'proof_cycle':
        cycle_id = 'cyc_' + uuid.uuid4().hex[:16]
        task = '\\n'.join([
            'E3_FULL_AUTONOMOUS_CYCLE_ANALYST_PROOF',
            'CYCLE: E3_FULL',
            f'TRACE_ID: {trace_id}',
            '',
            'Прочитать governance/MASTER_PLAN.md и активный state layer.',
            'Выполнить роль ANALYST в первом полном автономном цикле.',
            'Ничего не менять. Только read/report.',
            'Дальше последовательность ролей ведёт role_orchestrator FSM, не ISA/comment chaining.'
        ])
        dispatch_result = dispatch_workflow('role-orchestrator.yml', {
            'mode': 'start',
            'task_type': 'default_development',
            'task': task[:4000],
            'trace_id': trace_id,
            'cycle_id': cycle_id,
            'role': '',
            'status': 'ROLE_DONE',
            'note': ''
        })
        append_event({'event': 'AUTONOMY_ENGINE_PROOF_CYCLE_DISPATCHED', 'task_id': task_id, 'trace_id': trace_id, 'cycle_id': cycle_id, 'dispatch_result': dispatch_result})
        state.update({'updated_at': now_iso(), 'status': 'proof_cycle_dispatched_to_role_orchestrator', 'current_step': 'C-10', 'last_task_id': task_id, 'last_trace_id': trace_id, 'blocker': None})
        write_json(STATE, state)
        print('BEM-AUTONOMY-ENGINE | PROOF_CYCLE_DISPATCHED')
        print('TRACE_ID=' + trace_id)
        print('CYCLE_ID=' + cycle_id)
        print('DISPATCH_RESULT=' + str(dispatch_result))
        return 0

    return 2


if __name__ == '__main__':
    raise SystemExit(main())
