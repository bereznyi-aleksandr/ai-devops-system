#!/usr/bin/env python3
"""
GPT Developer Runner — BEM-395
Версия: v1.0 | 2026-05-13

Anti-hang contract:
- Один atomic step за запуск. Никаких бесконечных циклов.
- После каждого шага — BEM report.
- Ошибка → blocker, не silent wait.
- Emergency stop проверяется перед каждым шагом.
- Не более 1 write operation за шаг.
- Secrets никогда не пишутся в файлы.
"""
import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SESSION_FILE = ROOT / 'governance/state/gpt_dev_session.json'
EMERGENCY_STOP = ROOT / 'governance/state/emergency_stop.json'
EVENTS_FILE = ROOT / 'governance/events/gpt_dev_runner.jsonl'
EXCHANGE_FILE = ROOT / 'governance/exchange.jsonl'
ROADMAP_FILE = ROOT / 'governance/state/roadmap_state.json'


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return default


def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def append_jsonl(path, entry):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    entry['timestamp'] = entry.get('timestamp') or now_iso()
    with p.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def check_emergency_stop():
    es = load_json(EMERGENCY_STOP, {})
    if es.get('enabled'):
        return es.get('reason') or 'emergency_stop_active'
    return None


def load_session():
    return load_json(SESSION_FILE, {
        'version': 1, 'session_id': None, 'trace_id': None,
        'status': 'idle', 'cursor': None, 'queue': [],
        'current_step': None, 'attempts': 0,
        'last_report': None, 'blocker': None, 'updated_at': None
    })


def save_session(session):
    session['updated_at'] = now_iso()
    save_json(SESSION_FILE, session)


def bem_report(session, result, error=None):
    """Генерирует BEM report и пишет в events."""
    report = {
        'type': 'BEM-GPT-DEV-RUNNER',
        'session_id': session.get('session_id'),
        'trace_id': session.get('trace_id'),
        'status': session.get('status'),
        'current_step': session.get('current_step'),
        'cursor': session.get('cursor'),
        'attempts': session.get('attempts'),
        'result': result,
        'blocker': session.get('blocker'),
        'error': str(error) if error else None,
        'timestamp': now_iso()
    }
    append_jsonl(EVENTS_FILE, report)
    append_jsonl(EXCHANGE_FILE, {
        'event_id': f"gpt_dev_{session.get('session_id', 'unknown')}_{session.get('attempts', 0)}",
        'type': 'GPT_DEV_RUNNER_STEP',
        'source': 'gpt_dev_runner',
        'status': session.get('status'),
        'step': session.get('current_step'),
        'result': result
    })
    return report


# ─── Step handlers ──────────────────────────────────────────────────────────

def step_read_state(step, session):
    """Читает файл состояния и возвращает его содержимое в report."""
    target = step.get('target')
    if not target:
        return False, 'read_state: target required'
    data = load_json(ROOT / target)
    if data is None:
        return False, f'read_state: file not found: {target}'
    return True, f'read_state OK: {target} ({len(json.dumps(data))} bytes)'


def step_enqueue_patch_task(step, session):
    """Создаёт файл патч-задачи в patch_queue/generated/."""
    task = step.get('task')
    if not task:
        return False, 'enqueue_patch_task: task object required'
    task_id = task.get('task_id') or f"gpt_dev_{session.get('trace_id', 'unknown')}"
    safe_id = task_id.replace('/', '_').replace(' ', '_')[:60]
    path = ROOT / f'governance/patch_queue/generated/{safe_id}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(task, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return True, f'enqueue_patch_task OK: {path.relative_to(ROOT)}'


def step_dispatch_workflow(step, session):
    """Триггерит GitHub Actions workflow через repository_dispatch."""
    import urllib.request
    event_type = step.get('event_type', 'gpt-dev-runner')
    payload = step.get('payload') or {}
    payload['session_id'] = session.get('session_id')
    payload['trace_id'] = session.get('trace_id')
    payload['source'] = 'gpt_dev_runner'
    payload['timestamp'] = now_iso()

    gh_token = os.environ.get('AI_SYSTEM_GITHUB_PAT') or os.environ.get('GH_TOKEN')
    if not gh_token:
        return False, 'dispatch_workflow: GH_TOKEN not set'

    repo = os.environ.get('GITHUB_REPOSITORY', 'bereznyi-aleksandr/ai-devops-system')
    data = json.dumps({'event_type': event_type, 'client_payload': payload}).encode()
    req = urllib.request.Request(
        f'https://api.github.com/repos/{repo}/dispatches',
        data=data,
        headers={
            'Authorization': f'Bearer {gh_token}',
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
        if status == 204:
            return True, f'dispatch_workflow OK: {event_type}'
        return False, f'dispatch_workflow HTTP {status}'
    except Exception as e:
        return False, f'dispatch_workflow error: {e}'


def step_verify_file(step, session):
    """Проверяет существование файла."""
    target = step.get('target')
    if not target:
        return False, 'verify_file: target required'
    exists = (ROOT / target).exists()
    if exists:
        return True, f'verify_file OK: {target} exists'
    return False, f'verify_file FAIL: {target} not found'


def step_verify_state(step, session):
    """Проверяет что JSON файл содержит ожидаемые поля."""
    target = step.get('target')
    expected = step.get('expected') or {}
    if not target:
        return False, 'verify_state: target required'
    data = load_json(ROOT / target)
    if data is None:
        return False, f'verify_state: {target} not found'
    for key, val in expected.items():
        actual = data.get(key)
        if actual != val:
            return False, f'verify_state FAIL: {key}={actual!r} expected {val!r}'
    return True, f'verify_state OK: {target}'


def step_write_report(step, session):
    """Записывает итоговый отчёт сессии в файл."""
    trace = session.get('trace_id', 'unknown')
    report_path = ROOT / f'governance/state/gpt_dev_runner_selftest_{trace}.json'
    report = {
        'session_id': session.get('session_id'),
        'trace_id': trace,
        'status': session.get('status'),
        'steps_completed': session.get('attempts'),
        'blocker': session.get('blocker'),
        'generated_at': now_iso()
    }
    save_json(report_path, report)
    return True, f'write_report OK: {report_path.relative_to(ROOT)}'


STEP_HANDLERS = {
    'read_state': step_read_state,
    'enqueue_patch_task': step_enqueue_patch_task,
    'dispatch_workflow': step_dispatch_workflow,
    'verify_file': step_verify_file,
    'verify_state': step_verify_state,
    'write_report': step_write_report,
}


# ─── Session management ──────────────────────────────────────────────────────

def init_session(trace_id, queue):
    """Инициализирует новую dev сессию."""
    session = {
        'version': 1,
        'session_id': f'gds_{uuid.uuid4().hex[:12]}',
        'trace_id': trace_id,
        'status': 'queued',
        'cursor': 0,
        'queue': queue,
        'current_step': None,
        'attempts': 0,
        'last_report': None,
        'blocker': None,
        'updated_at': now_iso()
    }
    save_session(session)
    append_jsonl(EVENTS_FILE, {
        'type': 'GPT_DEV_SESSION_INIT',
        'session_id': session['session_id'],
        'trace_id': trace_id,
        'queue_length': len(queue)
    })
    return session


def execute_one_step(session):
    """
    Выполняет ровно один шаг из очереди.
    Anti-hang: нет циклов, нет ожидания, нет long-running.
    """
    # Emergency stop
    stop_reason = check_emergency_stop()
    if stop_reason:
        session['status'] = 'blocked'
        session['blocker'] = f'emergency_stop: {stop_reason}'
        save_session(session)
        bem_report(session, 'blocked_by_emergency_stop')
        return session, 'blocked'

    queue = session.get('queue') or []
    cursor = session.get('cursor') or 0

    if cursor >= len(queue):
        session['status'] = 'completed'
        save_session(session)
        bem_report(session, 'all_steps_completed')
        return session, 'completed'

    step = queue[cursor]
    step_type = step.get('type')
    session['current_step'] = step_type
    session['status'] = 'running'
    session['attempts'] = session.get('attempts', 0) + 1
    save_session(session)

    handler = STEP_HANDLERS.get(step_type)
    if not handler:
        session['status'] = 'blocked'
        session['blocker'] = f'unknown_step_type: {step_type}'
        save_session(session)
        bem_report(session, f'blocked: unknown step type {step_type}')
        return session, 'blocked'

    try:
        ok, result = handler(step, session)
    except Exception as e:
        ok, result = False, str(e)

    if ok:
        session['cursor'] = cursor + 1
        session['last_report'] = result
        # Если это был последний шаг
        if session['cursor'] >= len(queue):
            session['status'] = 'completed'
        else:
            session['status'] = 'queued'
        save_session(session)
        bem_report(session, result)
        return session, 'step_done'
    else:
        session['status'] = 'blocked'
        session['blocker'] = result
        save_session(session)
        bem_report(session, f'step_failed', error=result)
        return session, 'blocked'


# ─── Presets ─────────────────────────────────────────────────────────────────

PRESETS = {
    'developer_runner_selftest': lambda trace: [
        {'type': 'read_state', 'target': 'governance/state/system_state.json'},
        {'type': 'read_state', 'target': 'governance/state/routing.json'},
        {'type': 'verify_file', 'target': 'governance/INTERNAL_CONTOUR_REFERENCE.md'},
        {'type': 'enqueue_patch_task', 'task': {
            'task_id': f'gpt_dev_selftest_{trace}',
            'title': 'GPT Dev Runner selftest patch',
            'mode': 'apply_and_commit',
            'owner_approved_commit': True,
            'commit_message': f'BEM-395: GPT dev runner selftest [{trace}]',
            'files': [{
                'path': f'governance/state/gpt_dev_runner_selftest_{trace}.json',
                'operation': 'create_or_update',
                'content': json.dumps({
                    'version': 1, 'trace': trace,
                    'status': 'selftest_passed',
                    'created_by': 'gpt_dev_runner'
                }, indent=2) + '\n'
            }]
        }},
        {'type': 'write_report'}
    ],
    'fix_internal_contour': lambda trace: [
        {'type': 'read_state', 'target': 'governance/state/role_cycle_state.json'},
        {'type': 'read_state', 'target': 'governance/state/roadmap_state.json'},
        {'type': 'read_state', 'target': 'governance/state/provider_status.json'},
        {'type': 'verify_file', 'target': 'governance/state/emergency_stop.json'},
        {'type': 'dispatch_workflow', 'event_type': 'autonomy-engine',
         'payload': {'mode': 'production_loop', 'trace_id': trace, 'source': 'gpt_dev_runner'}},
        {'type': 'write_report'}
    ]
}


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='GPT Developer Runner — one atomic step per run')
    parser.add_argument('--mode', default='step',
                        choices=['step', 'init', 'status'],
                        help='step: execute one step | init: start new session | status: show session')
    parser.add_argument('--trace-id', default=None)
    parser.add_argument('--preset', default=None, choices=list(PRESETS.keys()))
    parser.add_argument('--session-id', default=None)
    args = parser.parse_args()

    if args.mode == 'status':
        session = load_session()
        print(json.dumps(session, indent=2, ensure_ascii=False))
        return 0

    if args.mode == 'init':
        trace_id = args.trace_id or f'gdr_{uuid.uuid4().hex[:12]}'
        if args.preset:
            queue = PRESETS[args.preset](trace_id)
        else:
            queue = []
        session = init_session(trace_id, queue)
        print(f'BEM-GPT-DEV-RUNNER | SESSION INIT')
        print(f'session_id={session["session_id"]}')
        print(f'trace_id={trace_id}')
        print(f'queue_length={len(queue)}')
        return 0

    # mode == 'step'
    session = load_session()

    if session.get('status') in ('completed', 'blocked'):
        print(f'BEM-GPT-DEV-RUNNER | SESSION ALREADY {session["status"].upper()}')
        print(f'blocker={session.get("blocker")}')
        return 0

    if not session.get('session_id') or session.get('status') == 'idle':
        print('BEM-GPT-DEV-RUNNER | NO ACTIVE SESSION — use --mode init first')
        return 1

    session, outcome = execute_one_step(session)
    print(f'BEM-GPT-DEV-RUNNER | STEP OUTCOME: {outcome.upper()}')
    print(f'session_id={session["session_id"]}')
    print(f'cursor={session["cursor"]}/{len(session.get("queue", []))}')
    print(f'status={session["status"]}')
    print(f'last_report={session.get("last_report")}')
    if session.get('blocker'):
        print(f'blocker={session["blocker"]}')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
