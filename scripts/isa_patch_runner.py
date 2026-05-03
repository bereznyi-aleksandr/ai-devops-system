#!/usr/bin/env python3
import argparse
import fnmatch
import json
import os
import subprocess
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
        proc = subprocess.run(cmd, shell=True, cwd=ROOT, text=True, capture_output=True)
        results.append({'cmd': cmd, 'returncode': proc.returncode, 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-4000:]})
        if proc.returncode != 0:
            return False, results
    return True, results


def git_commit(message):
    subprocess.run('git status --short', shell=True, cwd=ROOT, check=False)
    subprocess.run('git add .', shell=True, cwd=ROOT, check=True)
    diff = subprocess.run('git diff --cached --quiet', shell=True, cwd=ROOT)
    if diff.returncode == 0:
        return 'no_changes'
    subprocess.run('git config user.email isa-patch-runner@ai-devops-system', shell=True, cwd=ROOT, check=True)
    subprocess.run('git config user.name ISA Patch Runner', shell=True, cwd=ROOT, check=True)
    subprocess.run(['git', 'commit', '-m', message], cwd=ROOT, check=True)
    subprocess.run(['git', 'push'], cwd=ROOT, check=True)
    return 'committed'


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
        append_event({'event': 'PATCH_RUNNER_DRY_RUN_OK', 'task_id': task.get('task_id')})
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
