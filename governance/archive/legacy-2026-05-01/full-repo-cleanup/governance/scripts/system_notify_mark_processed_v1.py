#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class NotifyProcessError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def main() -> int:
    try:
        if len(sys.argv) < 2:
            raise NotifyProcessError(
                'Usage: system_notify_mark_processed_v1.py <NOTIFY_PATH> [PROCESSED_BY]'
            )

        src_arg = str(sys.argv[1]).strip()
        processed_by = str(sys.argv[2]).strip() if len(sys.argv) >= 3 else 'SYSTEM'

        if not src_arg:
            raise NotifyProcessError('NOTIFY_PATH is empty')

        src = Path(src_arg)
        if not src.is_absolute():
            src = ROOT / src

        if not src.exists():
            raise NotifyProcessError(f'Notify file not found: {src}')

        data = json.loads(src.read_text(encoding='utf-8'))
        role = str(data.get('role', '')).strip().lower()
        task_id = str(data.get('task_id', '')).strip()

        if not role:
            raise NotifyProcessError('role is missing in notify payload')
        if not task_id:
            raise NotifyProcessError('task_id is missing in notify payload')

        processed_dir = src.parent / 'processed'
        processed_dir.mkdir(parents=True, exist_ok=True)

        ts = utc_now()
        dst = processed_dir / f'{task_id}.{ts.replace(":", "-")}.notify.json'

        data['processed_at'] = ts
        data['processed_by'] = processed_by
        data['source_notify_path'] = str(src.relative_to(ROOT))
        data['processed_notification_path'] = str(dst.relative_to(ROOT))

        dst.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        src.unlink()

        print(json.dumps({
            'system_notify_mark_processed_version': 'v1',
            'result': 'SUCCESS',
            'role': role.upper(),
            'task_id': task_id,
            'processed_by': processed_by,
            'source_notify_path': str(src.relative_to(ROOT)),
            'processed_notification_path': str(dst.relative_to(ROOT)),
        }, ensure_ascii=False, indent=2))
        return 0

    except Exception as e:
        print(json.dumps({
            'system_notify_mark_processed_version': 'v1',
            'result': 'BLOCKED',
            'error': str(e),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
