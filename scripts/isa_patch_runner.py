#!/usr/bin/env python3
import argparse
import fnmatch
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
POLICY_PATH = ROOT / 'governance/policies/patch_runner_allowlist.json'
EVENT_LOG = ROOT / 'governance/events/patch_runner.jsonl'
SUPPORTED_OPS = ('create_or_update', 'delete', 'replace')


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def append_event(entry):
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry['timestamp'] = entry.get('timestamp') or now_iso()
    with EVENT_LOG.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def path_allowed(path, policy):
    p = path.replace('\\', '/')
    for blocked in policy.get('blocked_paths', []):
        b = blocked.rstrip('/')
        if p == b or p.startswith(b + '/') or fnmatch.fnmatch(p, blocked):
            return False, 'blocked_path'
    for allowed in policy.get('allowed_paths', []):
        a = allowed.rstrip('/')
        if allowed.endswith('/'):
            if p.startswith(allowed):
                return True, 'allowed_prefix'
        elif p == a or fnmatch.fnmatch(p, allowed):
            return True, 'allowed_exact'
    return False, 'not_in_allowlist'


def validate_task(task, policy):
    errors = []
    files = task.get('files', [])
    if not isinstance(files, list):
        return ['files must be list']
    for item in files:
        path = item.get('path', '')
        ok, reason = path_allowed(path, policy)
        if not ok:
            errors.append(f'{path}: {reason}')
        op = item.get('operation')
        if op not in SUPPORTED_OPS:
            errors.append(f'{path}: unsupported operation {op}')
        if op == 'replace':
            if 'old' not in item or 'new' not in item:
                errors.append(f'{path}: replace requires old and new')
    return errors


def apply_files(task):
    for item in task.get('files', []):
        rel = item['path']
        dest = ROOT / rel
        op = item.get('operation')
        if op == 'delete':
            if dest.exists():
                dest.unlink()
            continue
        if op == 'replace':
            text = dest.read_text(encoding='utf-8', errors='replace')
            old = item['old']
            new = item['new']
            count = int(item.get('count', 1))
            if old not in text:
                raise RuntimeError(f'replace target not found: {rel}')
            dest.write_text(text.replace(old, new, count), encoding='utf-8')
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(item.get('content', ''), encoding='utf-8')


def run_checks(task):
    results = []
    for cmd in task.get('checks', []):
        env = os.environ.copy()
        env['ISA_PATCH_RUNNER_ACTIVE'] = '1'
        proc = subprocess.run(cmd, shell=True, cwd=ROOT, text=True, capture_output=True, env=env)
        results.append({'cmd': cmd, 'returncode': proc.returncode, 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-4000:]})
        if proc.returncode != 0:
            return False, results
    return True, results


def run_git(cmd, check=True):
    proc = subprocess.run(cmd, shell=True, cwd=ROOT, text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f'git command failed rc={proc.returncode}: {cmd}\n'
            f'STDOUT:\n{proc.stdout[-2000:]}\nSTDERR:\n{proc.stderr[-2000:]}'
        )
    return proc


def git_push_with_recovery(max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        print(f'BEM-ISA-PATCH-RUNNER | PUSH_ATTEMPT_{attempt}')
        append_event({'event': 'PATCH_RUNNER_PUSH_ATTEMPT', 'attempt': attempt})
        run_git('git pull --rebase --autostash origin main')
        proc = run_git('git push origin HEAD:main', check=False)
        if proc.returncode == 0:
            append_event({'event': 'PATCH_RUNNER_PUSH_OK', 'attempt': attempt})
            print('BEM-ISA-PATCH-RUNNER | PUSH_OK')
            return 'pushed'
        append_event({
            'event': 'PATCH_RUNNER_PUSH_RETRY',
            'attempt': attempt,
            'returncode': proc.returncode,
            'stdout': proc.stdout[-2000:],
            'stderr': proc.stderr[-2000:]
        })
        time.sleep(2)
    append_event({'event': 'PATCH_RUNNER_PUSH_FAILED_AFTER_RETRY', 'attempts': max_attempts})
    print('BEM-ISA-PATCH-RUNNER | PUSH_FAILED_AFTER_RETRY')
    raise RuntimeError('git push failed after retry')


def git_commit(message):
    subprocess.run('git status --short', shell=True, cwd=ROOT, check=False)
    subprocess.run('git add .', shell=True, cwd=ROOT, check=True)
    diff = subprocess.run('git diff --cached --quiet', shell=True, cwd=ROOT)
    if diff.returncode == 0:
        return 'no_changes'
    # FIX: кавычки вокруг значений user.email и user.name
    subprocess.run(['git', 'config', 'user.email', 'isa-patch-runner@ai-devops-system'], cwd=ROOT, check=True)
    subprocess.run(['git', 'config', 'user.name', 'ISA Patch Runner'], cwd=ROOT, check=True)
    subprocess.run(['git', 'commit', '-m', message], cwd=ROOT, check=True)
    return git_push_with_recovery()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--task-file', required=True)
    parser.add_argument('--mode', default='dry_run', choices=['dry_run', 'apply', 'apply_and_commit', 'report_only'])
    args = parser.parse_args()

    task = load_json(args.task_file)
    policy = load_json(POLICY_PATH)
    errors = validate_task(task, policy)
    append_event({'event': 'PATCH_RUNNER_START', 'task_id': task.get('task_id'), 'mode': args.mode, 'errors': errors})

    print('BEM-ISA-PATCH-RUNNER | START')
    print('TASK_ID=' + str(task.get('task_id')))
    print('MODE=' + args.mode)

    if errors:
        print('VALIDATION=FAILED')
        for e in errors:
            print('ERROR=' + e)
        append_event({'event': 'PATCH_RUNNER_VALIDATION_FAILED', 'task_id': task.get('task_id'), 'errors': errors})
        return 2

    if args.mode in ('dry_run', 'report_only'):
        print('VALIDATION=OK')
        print('DRY_RUN=OK')
        append_event({'event': 'PATCH_RUNNER_DRY_RUN_OK', 'task_id': task.get('task_id')}))
        return 0

    try:
        apply_files(task)
    except Exception as exc:
        print('APPLY=FAILED')
        print('ERROR=' + str(exc))
        append_event({'event': 'PATCH_RUNNER_APPLY_FAILED', 'task_id': task.get('task_id'), 'error': str(exc)})
        return 5

    checks_ok, check_results = run_checks(task)
    append_event({'event': 'PATCH_RUNNER_CHECKS', 'task_id': task.get('task_id'), 'ok': checks_ok, 'checks': check_results})
    if not checks_ok:
        print('CHECKS=FAILED')
        return 3

    if args.mode == 'apply_and_commit':
        if not task.get('owner_approved_commit'):
            print('COMMIT=BLOCKED_OWNER_APPROVED_COMMIT_MISSING')
            return 4
        status = git_commit(task.get('commit_message') or ('ISA PATCH: ' + str(task.get('title', 'update'))))
        print('COMMIT=' + status)
        append_event({'event': 'PATCH_RUNNER_COMMIT', 'task_id': task.get('task_id'), 'status': status})
    else:
        print('APPLY=OK_NO_COMMIT')

    print('BEM-ISA-PATCH-RUNNER | DONE')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
