#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WRITER = ROOT / 'governance' / 'scripts' / 'system_packet_writer_v1.py'
EXECUTOR_RUNNER = ROOT / 'governance' / 'scripts' / 'run_executor_codex_v2.sh'
AUDITOR_RUNNER = ROOT / 'governance' / 'scripts' / 'run_auditor_codex_v1.sh'
MARK_PROCESSED = ROOT / 'governance' / 'scripts' / 'system_notify_mark_processed_v1.py'
NOTIFY_DIR = ROOT / 'governance' / 'runtime' / 'notifications'


class RoleLauncherError(RuntimeError):
    pass


def run_packet_writer() -> dict:
    proc = subprocess.run(
        [sys.executable, str(WRITER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
    )
    if proc.returncode != 0:
        raise RoleLauncherError(proc.stderr.strip() or proc.stdout.strip() or 'system_packet_writer_v1 failed')
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RoleLauncherError(f'Packet writer output is not valid JSON: {e}') from e


def select_runner(next_role: str) -> Path:
    if next_role == 'EXECUTOR':
        runner = EXECUTOR_RUNNER
    elif next_role == 'AUDITOR':
        runner = AUDITOR_RUNNER
    else:
        raise RoleLauncherError(f'Unsupported next_role: {next_role}')

    if not runner.exists():
        raise RoleLauncherError(f'Missing runner: {runner.relative_to(ROOT)}')

    return runner


def build_runner_command(next_role: str) -> str:
    runner = select_runner(next_role)
    return f'bash {runner.relative_to(ROOT)}'


def maybe_mark_notify_processed(next_role: str, current_task_id: str) -> str:
    if not current_task_id:
        return ''

    notify_path = NOTIFY_DIR / next_role.lower() / f'{current_task_id}.notify.json'
    if not notify_path.exists():
        return ''

    proc = subprocess.run(
        [sys.executable, str(MARK_PROCESSED), str(notify_path), next_role],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
    )
    if proc.returncode != 0:
        raise RoleLauncherError(proc.stderr.strip() or proc.stdout.strip() or 'system_notify_mark_processed_v1 failed')

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RoleLauncherError(f'notify mark processed output is not valid JSON: {e}') from e

    return result.get('processed_notification_path', '')


def main() -> int:
    try:
        writer_result = run_packet_writer()
        next_role = writer_result.get('next_role', '')
        next_action = writer_result.get('next_action', '')
        current_task_id = writer_result.get('current_task_id', '')
        runner = select_runner(next_role)
        runner_command = f'bash {runner.relative_to(ROOT)}'
        processed_notify_path = maybe_mark_notify_processed(next_role, current_task_id)
        gha_mode = os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('CI') == 'true'

        result = {
            'system_role_launcher_version': 'v2',
            'result': 'READY',
            'mode': 'GHA_SAFE_AUTO_EXECUTE' if gha_mode else 'TTY_SAFE_MANUAL_LAUNCH',
            'next_role': next_role,
            'next_action': next_action,
            'written_packet_path': writer_result.get('written_packet_path', ''),
            'current_event_id': writer_result.get('current_event_id', ''),
            'current_task_id': current_task_id,
            'processed_notify_path': processed_notify_path,
            'runner_command': runner_command,
            'github_actions': os.environ.get('GITHUB_ACTIONS', ''),
            'ci': os.environ.get('CI', ''),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))

        if gha_mode:
            print('GITHUB_ACTIONS=true path taken')
            proc = subprocess.run(['bash', str(runner)], cwd=ROOT)
            return proc.returncode

        print('Run the runner_command manually in the current interactive terminal so Codex gets a real TTY.')
        return 0
    except Exception as e:
        print(json.dumps({
            'system_role_launcher_version': 'v2',
            'result': 'BLOCKED',
            'error': str(e),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
