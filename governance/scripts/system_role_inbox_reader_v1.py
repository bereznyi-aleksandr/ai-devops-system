#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTIFICATIONS_DIR = ROOT / 'governance' / 'runtime' / 'notifications'
MARK_PROCESSED = ROOT / 'governance' / 'scripts' / 'system_notify_mark_processed_v1.py'


class RoleInboxError(RuntimeError):
    pass


def main() -> int:
    try:
        if len(sys.argv) < 2:
            raise RoleInboxError('Usage: system_role_inbox_reader_v1.py <ROLE>')

        role = str(sys.argv[1]).strip().upper()
        if role not in {'AUDITOR', 'EXECUTOR', 'SYSTEM'}:
            raise RoleInboxError(f'Unsupported role: {role}')

        role_dir = NOTIFICATIONS_DIR / role.lower()
        role_dir.mkdir(parents=True, exist_ok=True)

        active = sorted(role_dir.glob('*.notify.json'))
        if not active:
            print(json.dumps({
                'system_role_inbox_reader_version': 'v1',
                'result': 'NO_NOTIFY',
                'role': role,
                'active_count': 0,
            }, ensure_ascii=False, indent=2))
            return 0

        notify_path = active[0]
        payload = json.loads(notify_path.read_text(encoding='utf-8'))

        proc = subprocess.run(
            [sys.executable, str(MARK_PROCESSED), str(notify_path), role],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RoleInboxError(proc.stderr.strip() or 'mark_processed failed')

        processed_info = json.loads(proc.stdout)

        print(json.dumps({
            'system_role_inbox_reader_version': 'v1',
            'result': 'SUCCESS',
            'role': role,
            'task_id': str(payload.get('task_id', '')).strip(),
            'next_action': str(payload.get('next_action', '')).strip(),
            'source_notify_path': str(payload.get('notification_path', '')).strip(),
            'processed_notification_path': processed_info.get('processed_notification_path', ''),
        }, ensure_ascii=False, indent=2))
        return 0

    except Exception as e:
        print(json.dumps({
            'system_role_inbox_reader_version': 'v1',
            'result': 'BLOCKED',
            'error': str(e),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
