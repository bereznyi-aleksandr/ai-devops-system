#!/usr/bin/env python3
"""
GPT Developer Runner — BEM-402
Версия: v2.0 | 2026-05-14

Anti-hang contract:
- Один atomic step за запуск. Никаких бесконечных циклов.
- После каждого шага — BEM report.
- Ошибка → blocker, не silent wait.
- Emergency stop проверяется перед каждым шагом.
- State lock защищает от параллельных запусков.
- Duplicate trace_id guard предотвращает дубли.
- Retry policy для transient errors (max 3 попытки).
- Permissions check перед стартом.
- Secrets никогда не пишутся в файлы.
"""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SESSION_FILE   = ROOT / 'governance/state/gpt_dev_session.json'
LOCK_FILE      = ROOT / 'governance/state/gpt_dev_lock.json'
EMERGENCY_STOP = ROOT / 'governance/state/emergency_stop.json'
EVENTS_FILE    = ROOT / 'governance/events/gpt_dev_runner.jsonl'
EXCHANGE_FILE  = ROOT / 'governance/exchange.jsonl'

LOCK_TTL_MINUTES   = 10
MAX_STEP_ATTEMPTS  = 3

TRANSIENT_ERRORS = (
    '5xx', 'temporary', 'timeout', 'connection', 'checkout', 'push conflict',
    'repository_dispatch temporary', 'urlopen error'
)

VALID_PRESETS = ('developer_runner_selftest', 'fix_internal_contour')

# ─── Helpers ─────────────────────────────────────────────────────────────────

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


# ─── Permissions check ────────────────────────────────────────────────────────

def check_permissions():
    """Проверяет наличие обязательных секретов и переменных среды."""
    token = os.environ.get('AI_SYSTEM_GITHUB_PAT') or os.environ.get('GH_TOKEN')
    if not token:
        return 'missing_permissions: AI_SYSTEM_GITHUB_PAT not set'
    return None


# ─── Emergency stop ───────────────────────────────────────────────────────────

def check_emergency_stop():
    es = load_json(EMERGENCY_STOP, {})
    if es.get('enabled'):
        return es.get('reason') or 'emergency_stop_active'
    return None


# ─── State lock ───────────────────────────────────────────────────────────────

def load_lock():
    return load_json(LOCK_FILE, {
        'locked': False, 'session_id': None, 'trace_id': None,
        'locked_at': None, 'expires_at': None, 'owner': None, 'reason': None
    })


def save_lock(lock):
    save_json(LOCK_FILE, lock)


def acquire_lock(session_id, trace_id, reason='session_active'):
    lock = load_lock()
    now = datetime.now(timezone.utc)

    if lock.get('locked'):
        # Check if stale (TTL exceeded)
        expires_at = lock.get('expires_at')
        if expires_at:
            try:
                exp = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if now < exp:
                    # Lock active and not expired
                    return False, f'lock_held by session={lock.get("session_id")} trace={lock.get("trace_id")}'
            except Exception:
                pass
        # Stale lock — clean up
        print(f'BEM-402: stale lock detected, cleaning up (was: {lock.get("session_id")})')

    lock = {
        'locked': True,
        'session_id': session_id,
        'trace_id': trace_id,
        'locked_at': now_iso(),
        'expires_at': (now + timedelta(minutes=LOCK_TTL_MINUTES)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'owner': 'gpt_dev_runner',
        'reason': reason
    }
    save_lock(lock)
    return True, 'lock_acquired'


def release_lock(session_id):
    lock = load_lock()
    if lock.get('session_id') == session_id:
        save_lock({
            'locked': False, 'session_id': None, 'trace_id': None,
            'locked_at': None, 'expires_at': None, 'owner': None, 'reason': None
        })


# ─── Session ──────────────────────────────────────────────────────────────────

def load_session():
    return load_json(SESSION_FILE, {
        'version': 1, 'session_id': None, 'trace_id': None,
        'status': 'idle', 'cursor': None, 'queue': [],
        'current_step': None, 'attempts': 0, 'step_attempts': 0,
        'last_report': None, 'blocker': None, 'updated_at': None
    })


def save_session(session):
    session['updated_at'] = now_iso()
    save_json(SESSION_FILE, session)


def bem_report(session, result, error=None):
    report = {
        'type': 'BEM-GPT-DEV-RUNNER',
        'session_id': session.get('session_id'),
        'trace_id': session.get('trace_id'),
        'status': session.get('status'),
        'current_step': session.get('current_step'),
        'cursor': session.get('cursor'),
        'attempts': session.get('attempts'),
        'step_attempts': session.get('step_attempts', 0),
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


# ─── Step handlers ────────────────────────────────────────────────────────────

def step_read_state(step, session):
    target = step.get('target')
    if not target:
        return False, 'read_state: target required'
    data = load_json(ROOT / target)
    if data is None:
        return False, f'read_state: file not found: {target}'
    return True, f'read_state OK: {target} ({len(json.dumps(data))} bytes)'


def step_enqueue_patch_task(step, session):
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
    import urllib.request
    event_type = step.get('event_type', 'gpt-dev-runner')
    payload = step.get('payload') or {}
    payload['session_id'] = session.get('session_id')
    payload['trace_id']   = session.get('trace_id')
    payload['source']     = 'gpt_dev_runner'
    payload['timestamp']  = now_iso()

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
    target = step.get('target')
    if not target:
        return False, 'verify_file: target required'
    exists = (ROOT / target).exists()
    if exists:
        return True, f'verify_file OK: {target} exists'
    return False, f'verify_file FAIL: {target} not found'


def step_verify_state(step, session):
    target   = step.get('target')
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
    'read_state':         step_read_state,
    'enqueue_patch_task': step_enqueue_patch_task,
    'dispatch_workflow':  step_dispatch_workflow,
    'verify_file':        step_verify_file,
    'verify_state':       step_verify_state,
    'write_report':       step_write_report,
}


# ─── Retry helpers ────────────────────────────────────────────────────────────

def is_transient_error(msg):
    msg_lower = str(msg).lower()
    return any(t in msg_lower for t in TRANSIENT_ERRORS)


# ─── Session management ───────────────────────────────────────────────────────

def init_session(trace_id, queue):
    """Инициализирует новую dev сессию с lock и duplicate guard."""

    # Permissions check
    perm_err = check_permissions()
    if perm_err:
        print(f'BEM-GPT-DEV-RUNNER | BLOCKED: {perm_err}')
        return None, perm_err

    # Emergency stop check
    stop_reason = check_emergency_stop()
    if stop_reason:
        print(f'BEM-GPT-DEV-RUNNER | BLOCKED: emergency_stop: {stop_reason}')
        return None, f'emergency_stop: {stop_reason}'

    # Duplicate-run guard
    existing = load_session()
    if existing.get('trace_id') == trace_id and existing.get('status') in ('queued', 'running'):
        print(f'BEM-GPT-DEV-RUNNER | DUPLICATE: trace_id={trace_id} already {existing["status"]}')
        return existing, None  # Return existing session — not an error

    if existing.get('trace_id') == trace_id and existing.get('status') == 'completed':
        print(f'BEM-GPT-DEV-RUNNER | NOTE: trace_id={trace_id} already completed, allowing new init')

    session_id = f'gds_{uuid.uuid4().hex[:12]}'

    # Acquire lock
    ok, lock_msg = acquire_lock(session_id, trace_id)
    if not ok:
        print(f'BEM-GPT-DEV-RUNNER | BLOCKED: {lock_msg}')
        return None, lock_msg

    session = {
        'version': 1,
        'session_id': session_id,
        'trace_id': trace_id,
        'status': 'queued',
        'cursor': 0,
        'queue': queue,
        'current_step': None,
        'attempts': 0,
        'step_attempts': 0,
        'last_report': None,
        'blocker': None,
        'updated_at': now_iso()
    }
    save_session(session)
    append_jsonl(EVENTS_FILE, {
        'type': 'GPT_DEV_SESSION_INIT',
        'session_id': session_id,
        'trace_id': trace_id,
        'queue_length': len(queue)
    })
    return session, None


def execute_one_step(session):
    """
    Выполняет ровно один шаг из очереди.
    Anti-hang: нет циклов, нет ожидания, нет long-running.
    Retry policy: max MAX_STEP_ATTEMPTS для transient errors.
    """
    # Emergency stop
    stop_reason = check_emergency_stop()
    if stop_reason:
        session['status']  = 'blocked'
        session['blocker'] = f'emergency_stop: {stop_reason}'
        save_session(session)
        release_lock(session.get('session_id'))
        bem_report(session, 'blocked_by_emergency_stop')
        return session, 'blocked'

    queue  = session.get('queue') or []
    cursor = session.get('cursor') or 0

    if cursor >= len(queue):
        session['status'] = 'completed'
        save_session(session)
        release_lock(session.get('session_id'))
        bem_report(session, 'all_steps_completed')
        return session, 'completed'

    step      = queue[cursor]
    step_type = step.get('type')
    session['current_step'] = step_type
    session['status']       = 'running'
    session['attempts']     = session.get('attempts', 0) + 1
    save_session(session)

    handler = STEP_HANDLERS.get(step_type)
    if not handler:
        session['status']       = 'blocked'
        session['blocker']      = f'unknown_step_type: {step_type}'
        session['step_attempts'] = 0
        save_session(session)
        release_lock(session.get('session_id'))
        bem_report(session, f'blocked: unknown step type {step_type}')
        return session, 'blocked'

    try:
        ok, result = handler(step, session)
    except Exception as e:
        ok, result = False, str(e)

    if ok:
        session['cursor']        = cursor + 1
        session['step_attempts'] = 0
        session['last_report']   = result
        if session['cursor'] >= len(queue):
            session['status'] = 'completed'
            release_lock(session.get('session_id'))
        else:
            session['status'] = 'queued'
        save_session(session)
        bem_report(session, result)
        return session, 'step_done'
    else:
        step_attempts = session.get('step_attempts', 0) + 1
        session['step_attempts'] = step_attempts
        max_att = MAX_STEP_ATTEMPTS

        if is_transient_error(result) and step_attempts < max_att:
            # Transient error — allow retry on next run
            session['status']      = 'queued'
            session['last_report'] = f'retry {step_attempts}/{max_att}: {result}'
            save_session(session)
            bem_report(session, f'transient_retry_{step_attempts}', error=result)
            return session, 'step_retry'
        else:
            # Non-transient or max attempts reached
            session['status']       = 'blocked'
            session['blocker']      = {
                'reason':        result,
                'stage':         step_type,
                'error_excerpt': str(result)[:200],
                'attempt':       step_attempts
            }
            session['step_attempts'] = 0
            save_session(session)
            release_lock(session.get('session_id'))
            bem_report(session, 'step_failed', error=result)
            return session, 'blocked'


# ─── Watchdog ─────────────────────────────────────────────────────────────────

def check_stale_session(session):
    """Детектирует зависшую сессию по updated_at."""
    updated = session.get('updated_at')
    if not updated:
        return False
    try:
        upd_dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc) - upd_dt).total_seconds() / 60
        return age > LOCK_TTL_MINUTES and session.get('status') == 'running'
    except Exception:
        return False


# ─── Presets ──────────────────────────────────────────────────────────────────

def _make_presets():
    import json as _json
    return {
        'developer_runner_selftest': lambda trace: [
            {'type': 'read_state',  'target': 'governance/state/system_state.json'},
            {'type': 'read_state',  'target': 'governance/state/routing.json'},
            {'type': 'verify_file', 'target': 'governance/INTERNAL_CONTOUR_REFERENCE.md'},
            {'type': 'enqueue_patch_task', 'task': {
                'task_id': f'gpt_dev_selftest_{trace}',
                'title':   'GPT Dev Runner selftest patch',
                'mode':    'apply_and_commit',
                'owner_approved_commit': True,
                'commit_message': f'BEM-402: GPT dev runner selftest [{trace}]',
                'files': [{
                    'path': f'governance/state/gpt_dev_runner_selftest_{trace}.json',
                    'operation': 'create_or_update',
                    'content': _json.dumps({
                        'version': 1, 'trace': trace,
                        'status': 'selftest_passed',
                        'created_by': 'gpt_dev_runner'
                    }, indent=2) + '\n'
                }]
            }},
            {'type': 'write_report'}
        ],
        'fix_internal_contour': lambda trace: [
            {'type': 'read_state',  'target': 'governance/state/role_cycle_state.json'},
            {'type': 'read_state',  'target': 'governance/state/roadmap_state.json'},
            {'type': 'read_state',  'target': 'governance/state/provider_status.json'},
            {'type': 'verify_file', 'target': 'governance/state/emergency_stop.json'},
            {'type': 'dispatch_workflow', 'event_type': 'autonomy-engine',
             'payload': {'mode': 'production_loop', 'trace_id': trace, 'source': 'gpt_dev_runner'}},
            {'type': 'write_report'}
        ]
    }


PRESETS = _make_presets()


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='GPT Developer Runner v2.0 — BEM-402')
    parser.add_argument('--mode', default='step',
                        choices=['step', 'init', 'status'],
                        help='step: execute one step | init: start new session | status: show session')
    parser.add_argument('--trace-id', default=None)
    parser.add_argument('--preset', default=None, choices=list(PRESETS.keys()))
    args = parser.parse_args()

    if args.mode == 'status':
        session = load_session()
        lock    = load_lock()
        print(json.dumps({'session': session, 'lock': lock}, indent=2, ensure_ascii=False))
        return 0

    if args.mode == 'init':
        trace_id = args.trace_id or f'gdr_{uuid.uuid4().hex[:12]}'

        if args.preset and args.preset not in PRESETS:
            print(f'BEM-GPT-DEV-RUNNER | BLOCKED: invalid preset={args.preset}')
            return 2

        queue = PRESETS[args.preset](trace_id) if args.preset else []
        session, err = init_session(trace_id, queue)

        if err:
            # Write blocked session to file so workflow can report it
            blocked = {
                'version': 1, 'session_id': None, 'trace_id': trace_id,
                'status': 'blocked', 'cursor': 0, 'queue': queue,
                'current_step': None, 'attempts': 0, 'step_attempts': 0,
                'last_report': None, 'blocker': err, 'updated_at': now_iso()
            }
            save_session(blocked)
            append_jsonl(EVENTS_FILE, {
                'type': 'GPT_DEV_SESSION_BLOCKED_AT_INIT',
                'trace_id': trace_id, 'blocker': err
            })
            return 2

        if session and session.get('status') in ('queued', 'running'):
            print(f'BEM-GPT-DEV-RUNNER | SESSION INIT')
            print(f'session_id={session["session_id"]}')
            print(f'trace_id={trace_id}')
            print(f'queue_length={len(queue)}')
            print(f'status={session["status"]}')
            return 0
        return 2

    # mode == 'step'
    session = load_session()

    # Watchdog: stale session detection
    if check_stale_session(session):
        session['status']  = 'blocked'
        session['blocker'] = {'reason': 'stale_step_timeout', 'stage': session.get('current_step')}
        save_session(session)
        release_lock(session.get('session_id'))
        bem_report(session, 'blocked_stale_session')
        print(f'BEM-GPT-DEV-RUNNER | WATCHDOG: stale session blocked')
        return 2

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
    print(f'step_attempts={session.get("step_attempts", 0)}')
    print(f'last_report={session.get("last_report")}')
    if session.get('blocker'):
        print(f'blocker={session["blocker"]}')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
